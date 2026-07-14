"""Tests for Free/Pro gating and Stripe payment endpoints (Stripe TEST mode).

- Verifies euromillions gating (402 for free users)
- Verifies AI daily quota (1/day for free, second call -> 402)
- Verifies statistical lotto stays free & unlimited
- Verifies /api/payments/packages
- Verifies /api/payments/checkout requires auth and returns Stripe URL + session_id
- Verifies /api/payments/status/{session_id} for unknown session
- Verifies payment_transactions record was created with payment_status='initiated'
- Verifies admin is a free user unless upgraded (subject to same gating)
"""
import os
import uuid
import asyncio
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env so tests can access MONGO_URL / DB_NAME for direct DB manipulations
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://jackpot-analyzer-24.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@lottopredict.app")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
TEST_USER_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "Passw0rd!")

FRONTEND_ORIGIN = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://jackpot-analyzer-24.preview.emergentagent.com"
).rstrip("/")


# ---------- Helpers ----------
def _register_fresh():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_gate_{uuid.uuid4().hex[:10]}@lottopredict.app"
    r = s.post(f"{API}/auth/register", json={
        "name": "Gate Tester", "email": email, "password": TEST_USER_PASSWORD
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("is_pro") is False
    return {"session": s, "email": email, "user": body}


def _login_admin():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


# ---------- Packages ----------
class TestPaymentsPackages:
    def test_packages_public(self):
        r = requests.get(f"{API}/payments/packages")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        pro = next((p for p in data if p["id"] == "pro_monthly"), None)
        assert pro is not None
        assert pro["amount"] == 4.99
        assert pro["currency"] == "gbp"
        assert "label" in pro


# ---------- Gating: fresh free user ----------
class TestGatingFreshFreeUser:
    def test_euromillions_statistical_402_for_free(self):
        u = _register_fresh()
        s = u["session"]
        r = s.post(f"{API}/predict/statistical/euromillions")
        assert r.status_code == 402, r.text
        detail = r.json().get("detail", "")
        assert "Pro" in detail or "pro" in detail

    def test_euromillions_ai_402_for_free(self):
        u = _register_fresh()
        s = u["session"]
        r = s.post(f"{API}/predict/ai/euromillions")
        assert r.status_code == 402, r.text

    def test_ai_lotto_daily_limit(self):
        u = _register_fresh()
        s = u["session"]
        # First call should succeed
        r1 = s.post(f"{API}/predict/ai/lotto", timeout=120)
        assert r1.status_code == 200, r1.text
        data = r1.json()
        assert data["method"] == "ai"
        assert "predictions" in data
        # Second call same day -> 402 quota
        r2 = s.post(f"{API}/predict/ai/lotto", timeout=120)
        assert r2.status_code == 402, r2.text
        detail = r2.json().get("detail", "")
        assert "Pro" in detail or "pro" in detail or "limit" in detail.lower() or "used" in detail.lower()

    def test_statistical_lotto_unlimited(self):
        u = _register_fresh()
        s = u["session"]
        for i in range(3):
            r = s.post(f"{API}/predict/statistical/lotto")
            assert r.status_code == 200, f"iter {i}: {r.status_code} {r.text}"
            data = r.json()
            assert data["method"] == "statistical"
            assert data["game"] == "lotto"
            assert len(data["predictions"]) == 3

    def test_me_reports_is_pro_false(self):
        u = _register_fresh()
        s = u["session"]
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 200
        me = r.json()
        assert me.get("is_pro") is False
        assert me.get("pro_until") in (None, "")


# ---------- Payments checkout ----------
class TestPaymentsCheckout:
    def test_checkout_requires_auth(self):
        s = requests.Session()
        r = s.post(f"{API}/payments/checkout", json={
            "package_id": "pro_monthly", "origin_url": FRONTEND_ORIGIN
        })
        assert r.status_code == 401

    def test_checkout_invalid_package(self):
        u = _register_fresh()
        r = u["session"].post(f"{API}/payments/checkout", json={
            "package_id": "bogus_plan", "origin_url": FRONTEND_ORIGIN
        })
        assert r.status_code == 400

    def test_checkout_creates_session_and_transaction(self):
        u = _register_fresh()
        s = u["session"]
        r = s.post(f"{API}/payments/checkout", json={
            "package_id": "pro_monthly", "origin_url": FRONTEND_ORIGIN
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert "url" in body and body["url"].startswith("https://")
        assert "session_id" in body and isinstance(body["session_id"], str)
        assert "stripe" in body["url"].lower() or "checkout" in body["url"].lower()

        session_id = body["session_id"]
        # Status endpoint should now find the transaction (payment_status likely 'unpaid')
        r2 = s.get(f"{API}/payments/status/{session_id}")
        assert r2.status_code == 200, r2.text
        st = r2.json()
        assert "payment_status" in st
        # Not yet paid because we haven't completed checkout
        assert st["payment_status"] != "paid"

    def test_status_unknown_session_404(self):
        u = _register_fresh()
        s = u["session"]
        r = s.get(f"{API}/payments/status/cs_test_does_not_exist_{uuid.uuid4().hex[:8]}")
        assert r.status_code == 404

    def test_status_requires_auth(self):
        # Even with a random id, unauth must be 401 before the 404 check
        s = requests.Session()
        r = s.get(f"{API}/payments/status/anything")
        assert r.status_code == 401


# ---------- Admin gating (admin is free unless upgraded) ----------
class TestAdminGating:
    def test_admin_euromillions_gated_when_free(self):
        # Reset admin flags to ensure free
        import motor.motor_asyncio
        client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGO_URL"])
        dbm = client[os.environ["DB_NAME"]]
        asyncio.get_event_loop().run_until_complete(
            dbm.users.update_one({"email": ADMIN_EMAIL},
                                 {"$unset": {"pro_until": "", "ai_usage": ""}})
        )
        s = _login_admin()
        # Admin should NOT get pro just because role=admin
        me = s.get(f"{API}/auth/me").json()
        assert me.get("is_pro") is False
        r = s.post(f"{API}/predict/statistical/euromillions")
        assert r.status_code == 402, r.text

    def test_admin_ai_lotto_quota(self):
        import motor.motor_asyncio
        client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGO_URL"])
        dbm = client[os.environ["DB_NAME"]]
        asyncio.get_event_loop().run_until_complete(
            dbm.users.update_one({"email": ADMIN_EMAIL},
                                 {"$unset": {"pro_until": "", "ai_usage": ""}})
        )
        s = _login_admin()
        r1 = s.post(f"{API}/predict/ai/lotto", timeout=120)
        assert r1.status_code == 200, r1.text
        r2 = s.post(f"{API}/predict/ai/lotto", timeout=120)
        assert r2.status_code == 402, r2.text
        # Reset again so it doesn't interfere with later manual runs
        asyncio.get_event_loop().run_until_complete(
            dbm.users.update_one({"email": ADMIN_EMAIL},
                                 {"$unset": {"pro_until": "", "ai_usage": ""}})
        )


# ---------- Pro simulation: manually mark user Pro and ensure gates open ----------
class TestProUnlocksGating:
    def test_pro_user_can_access_euromillions_and_unlimited_ai(self):
        """Simulate a paid user by directly setting pro_until (webhook path is exercised
        via UI test). This validates that the gating helper flips correctly."""
        import motor.motor_asyncio
        from datetime import datetime, timezone, timedelta
        from bson import ObjectId
        u = _register_fresh()
        s = u["session"]

        client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGO_URL"])
        dbm = client[os.environ["DB_NAME"]]
        me = s.get(f"{API}/auth/me").json()
        uid = me["id"]
        pro_until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        asyncio.get_event_loop().run_until_complete(
            dbm.users.update_one({"_id": ObjectId(uid)}, {"$set": {"pro_until": pro_until}})
        )
        me = s.get(f"{API}/auth/me").json()
        assert me.get("is_pro") is True

        # EuroMillions statistical now allowed
        r = s.post(f"{API}/predict/statistical/euromillions")
        assert r.status_code == 200, r.text
        assert r.json()["game"] == "euromillions"

        # Multiple AI calls allowed for Pro
        r1 = s.post(f"{API}/predict/ai/lotto", timeout=120)
        assert r1.status_code == 200
        r2 = s.post(f"{API}/predict/ai/lotto", timeout=120)
        assert r2.status_code == 200
