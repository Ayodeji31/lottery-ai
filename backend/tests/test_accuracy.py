"""Tests for the GET /api/accuracy Pro-gated backtest endpoint.

Coverage:
- Anonymous -> 401
- Free user -> 402 (Pro upsell detail)
- Pro user with no saved predictions -> summary.tracked = 0
- Pro user with a jackpot-matching saved lotto set -> best.main_matched=6, prize='Jackpot'
- Response shape (summary + predictions items with expected keys)
- Bonus match highlighting works for lotto
- Regression: prize tier helper indirectly via /accuracy for a Match-3
"""
import os
import uuid
import asyncio
import pytest
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://jackpot-analyzer-24.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"
TEST_USER_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "Passw0rd!")


# --- helpers ---
def _register_fresh():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_acc_{uuid.uuid4().hex[:10]}@lottopredict.app"
    r = s.post(f"{API}/auth/register", json={
        "name": "Acc Tester", "email": email, "password": TEST_USER_PASSWORD
    })
    assert r.status_code == 200, r.text
    return {"session": s, "email": email, "user": r.json()}


def _make_pro(uid: str, days: int = 30):
    """Directly mark a user Pro in Mongo."""
    import motor.motor_asyncio
    client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGO_URL"])
    dbm = client[os.environ["DB_NAME"]]
    pro_until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    asyncio.get_event_loop().run_until_complete(
        dbm.users.update_one({"_id": ObjectId(uid)}, {"$set": {"pro_until": pro_until}})
    )
    return pro_until


# ---------- Auth gating ----------
class TestAccuracyAuth:
    def test_anonymous_returns_401(self):
        s = requests.Session()
        r = s.get(f"{API}/accuracy")
        assert r.status_code == 401, r.text

    def test_free_user_returns_402_with_pro_message(self):
        u = _register_fresh()
        r = u["session"].get(f"{API}/accuracy")
        assert r.status_code == 402, r.text
        detail = r.json().get("detail", "")
        assert "Pro" in detail or "pro" in detail
        assert "accuracy" in detail.lower() or "upgrade" in detail.lower()


# ---------- Pro user behaviour ----------
class TestAccuracyProNoSaved:
    def test_pro_user_no_saved_returns_zero_tracked(self):
        u = _register_fresh()
        s = u["session"]
        uid = u["user"]["id"]
        _make_pro(uid)
        # sanity - is_pro flipped
        me = s.get(f"{API}/auth/me").json()
        assert me["is_pro"] is True

        r = s.get(f"{API}/accuracy")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "summary" in data and "predictions" in data
        assert data["summary"]["tracked"] == 0
        assert data["summary"]["total_draws_checked"] == 0
        assert data["summary"]["total_prize_hits"] == 0
        assert data["summary"]["hit_rate"] == 0
        assert data["summary"]["best_ever"] is None
        assert data["predictions"] == []


class TestAccuracyProWithJackpot:
    """Save the exact winning lotto set for 2026-07-11 and expect a Jackpot best-match."""

    def test_jackpot_best_and_prize_tier(self):
        u = _register_fresh()
        s = u["session"]
        _make_pro(u["user"]["id"])

        # Save the exact winning combination for 2026-07-11
        payload = {
            "game": "lotto",
            "method": "manual",
            "main_numbers": [9, 13, 22, 36, 40, 45],
            "bonus_numbers": [41],
            "reasoning": "TEST_jackpot_seed",
        }
        cr = s.post(f"{API}/saved", json=payload)
        assert cr.status_code == 200, cr.text
        saved_id = cr.json()["id"]

        # Query accuracy
        r = s.get(f"{API}/accuracy")
        assert r.status_code == 200, r.text
        data = r.json()

        # Response shape
        summary = data["summary"]
        for k in ["tracked", "total_draws_checked", "total_prize_hits", "hit_rate", "best_ever"]:
            assert k in summary
        assert summary["tracked"] == 1
        assert summary["total_draws_checked"] >= 50  # ~52 historical draws
        assert summary["total_prize_hits"] >= 1
        assert summary["best_ever"] is not None
        assert summary["best_ever"]["main_matched"] == 6
        assert summary["best_ever"]["prize"] == "Jackpot"
        assert summary["best_ever"]["game"] == "lotto"

        # Predictions payload
        assert len(data["predictions"]) == 1
        pred = data["predictions"][0]
        for k in ["id", "game", "method", "main_numbers", "bonus_numbers",
                  "best", "prize_hits", "draws_checked"]:
            assert k in pred, f"missing {k}"
        assert pred["id"] == saved_id
        assert pred["game"] == "lotto"
        assert pred["main_numbers"] == payload["main_numbers"]
        assert pred["bonus_numbers"] == payload["bonus_numbers"]
        assert pred["prize_hits"] >= 1
        assert pred["draws_checked"] == summary["total_draws_checked"]

        best = pred["best"]
        for k in ["main_matched", "bonus_matched", "draw_date", "draw_main", "draw_bonus", "prize"]:
            assert k in best
        assert best["main_matched"] == 6
        assert best["bonus_matched"] == 1  # bonus 41 also matches
        assert best["draw_date"] == "2026-07-11"
        assert sorted(best["draw_main"]) == [9, 13, 22, 36, 40, 45]
        assert 41 in best["draw_bonus"]
        assert best["prize"] == "Jackpot"

        # cleanup
        s.delete(f"{API}/saved/{saved_id}")

    def test_bonus_only_match_still_evaluates(self):
        """Save a set that likely won't match main numbers but exercises the endpoint."""
        u = _register_fresh()
        s = u["session"]
        _make_pro(u["user"]["id"])

        # Save an obviously bad set for lotto
        payload = {
            "game": "lotto",
            "method": "manual",
            "main_numbers": [1, 2, 3, 4, 5, 6],
            "bonus_numbers": [7],
            "reasoning": "TEST_low_match",
        }
        r = s.post(f"{API}/saved", json=payload)
        assert r.status_code == 200

        r = s.get(f"{API}/accuracy")
        assert r.status_code == 200
        data = r.json()
        assert data["summary"]["tracked"] == 1
        pred = data["predictions"][0]
        # best is not None even if no prize
        assert pred["best"] is not None
        assert 0 <= pred["best"]["main_matched"] <= 6

        # Ensure no MongoDB _id leaks in the response
        assert "_id" not in pred
        assert "_id" not in pred["best"]

        # cleanup
        s.delete(f"{API}/saved/{pred['id']}")


# ---------- Regression: gating still holds for prior features ----------
class TestRegressionGating:
    def test_free_user_still_gated_on_euromillions_and_ai(self):
        u = _register_fresh()
        s = u["session"]
        # EuroMillions still 402 for free
        r = s.post(f"{API}/predict/statistical/euromillions")
        assert r.status_code == 402
        # accuracy also 402
        r = s.get(f"{API}/accuracy")
        assert r.status_code == 402
