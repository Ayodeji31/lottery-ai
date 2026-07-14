"""Notification + auto-refresh integration tests.

Covers:
  1. Data integrity: real draws (no 'sample' flag), expected latest draws.
  2. /api/notifications requires auth (401 anon).
  3. Pro user with matching saved set gets exactly ONE Jackpot notification after
     deleting the newest draw and running /api/admin/refresh-now.
  4. Non-matching set produces no notification.
  5. Idempotency: re-running /admin/refresh-now (no deletion) creates 0 new notifs.
  6. FREE user gets NO notifications (even with a matching saved set).
  7. Mark-one-read and mark-all-read behaviour + 404 for unknown id.
  8. new_draws count is small (1-2) after single-deletion refresh (regression guard
     against the sample-data-flood bug).
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from bson import ObjectId

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://jackpot-analyzer-24.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@lottopredict.app")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
PASSWORD = "Passw0rd!"

JACKPOT_MAIN = [9, 13, 22, 36, 40, 45]
JACKPOT_BONUS = [41]
NON_MATCH_MAIN = [1, 2, 3, 4, 5, 6]
NON_MATCH_BONUS = [7]


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return s


def _register(email_prefix):
    s = requests.Session()
    email = f"TEST_{email_prefix}_{uuid.uuid4().hex[:8]}@lottopredict.app"
    r = s.post(f"{API}/auth/register", json={"name": email_prefix, "email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    data = r.json()
    return {"session": s, "email": email, "id": data["id"]}


def _make_pro(mongo, user_id, days=30):
    until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    mongo.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"pro_until": until}})


# ---------- 1. Data integrity ----------
class TestDataIntegrity:
    """Real data present, no 'sample' flag, latest matches expectations."""

    def test_lotto_real_data(self, mongo):
        draws = list(mongo.draws.find({"game": "lotto"}))
        assert len(draws) >= 100, f"Only {len(draws)} lotto draws; expected 150+"
        assert all(not d.get("sample") for d in draws), "Sample data found in lotto draws"

    def test_euromillions_real_data(self, mongo):
        draws = list(mongo.draws.find({"game": "euromillions"}))
        assert len(draws) >= 100, f"Only {len(draws)} euromillions draws; expected 150+"
        assert all(not d.get("sample") for d in draws), "Sample data found in euromillions draws"

    def test_latest_lotto_draw(self):
        r = requests.get(f"{API}/draws/lotto?limit=1")
        assert r.status_code == 200
        d = r.json()[0]
        assert d["draw_date"] == "2026-07-11", d
        assert d["main_numbers"] == JACKPOT_MAIN
        assert d["bonus_numbers"] == JACKPOT_BONUS

    def test_latest_euromillions_draw(self):
        r = requests.get(f"{API}/draws/euromillions?limit=1")
        assert r.status_code == 200
        d = r.json()[0]
        assert d["draw_date"] == "2026-07-10"
        assert d["main_numbers"] == [2, 14, 28, 33, 48]
        assert d["bonus_numbers"] == [8, 10]


# ---------- 2. Auth on notifications endpoints ----------
class TestNotificationAuth:
    def test_list_notifications_requires_auth(self):
        r = requests.get(f"{API}/notifications")
        assert r.status_code == 401

    def test_mark_read_requires_auth(self):
        r = requests.post(f"{API}/notifications/some-id/read")
        assert r.status_code == 401

    def test_mark_all_read_requires_auth(self):
        r = requests.post(f"{API}/notifications/read-all")
        assert r.status_code == 401


# ---------- 3-8. End-to-end notification flow ----------
class TestNotificationFlow:
    """Full flow: pro user, matching + non-matching set, delete latest, refresh, verify one Jackpot."""

    @pytest.fixture(scope="class")
    def flow(self, mongo, admin_session):
        # Create Pro user with matching + non-matching sets
        pro = _register("pro_notif")
        _make_pro(mongo, pro["id"])

        # Save the matching (jackpot) set
        r = pro["session"].post(f"{API}/saved", json={
            "game": "lotto", "method": "manual",
            "main_numbers": JACKPOT_MAIN, "bonus_numbers": JACKPOT_BONUS,
        })
        assert r.status_code == 200
        pro_match_pid = r.json()["id"]

        # Save the non-matching set
        r = pro["session"].post(f"{API}/saved", json={
            "game": "lotto", "method": "manual",
            "main_numbers": NON_MATCH_MAIN, "bonus_numbers": NON_MATCH_BONUS,
        })
        assert r.status_code == 200
        pro_nomatch_pid = r.json()["id"]

        # Create Free user with a matching set (should NOT receive notifications)
        free = _register("free_notif")
        r = free["session"].post(f"{API}/saved", json={
            "game": "lotto", "method": "manual",
            "main_numbers": JACKPOT_MAIN, "bonus_numbers": JACKPOT_BONUS,
        })
        assert r.status_code == 200

        # Clear any prior notifications for these users
        mongo.notifications.delete_many({"user_id": {"$in": [pro["id"], free["id"]]}})

        # Snapshot latest lotto draw, delete it so refresh re-inserts it as "new"
        latest = mongo.draws.find_one({"game": "lotto", "draw_number": "20260711"})
        assert latest is not None, "Latest lotto draw (20260711) missing from DB"
        mongo.draws.delete_one({"_id": latest["_id"]})

        # Trigger refresh
        r = admin_session.post(f"{API}/admin/refresh-now")
        assert r.status_code == 200, r.text
        refresh_result = r.json()

        yield {
            "pro": pro,
            "pro_match_pid": pro_match_pid,
            "pro_nomatch_pid": pro_nomatch_pid,
            "free": free,
            "refresh_result": refresh_result,
        }

        # cleanup
        mongo.saved_predictions.delete_many({"user_id": {"$in": [pro["id"], free["id"]]}})
        mongo.notifications.delete_many({"user_id": {"$in": [pro["id"], free["id"]]}})
        mongo.users.delete_many({"_id": {"$in": [ObjectId(pro["id"]), ObjectId(free["id"])]}})

    def test_refresh_new_draws_is_small(self, flow):
        """CRITICAL regression guard: new_draws must be 1 (or maybe 2), NOT hundreds."""
        r = flow["refresh_result"]
        assert r["new_draws"] >= 1, r
        assert r["new_draws"] <= 5, f"new_draws={r['new_draws']} - sample-data flood regression!"

    def test_pro_user_gets_one_jackpot_notification(self, flow):
        s = flow["pro"]["session"]
        r = s.get(f"{API}/notifications")
        assert r.status_code == 200, r.text
        data = r.json()
        jp = [n for n in data["notifications"]
              if n["game"] == "lotto" and n["draw_number"] == "20260711" and n["prize"] == "Jackpot"]
        assert len(jp) == 1, f"Expected exactly 1 Jackpot notif, got {len(jp)}: {data}"
        n = jp[0]
        assert n["title"].startswith("You would have won")
        assert "Jackpot" in n["title"]
        assert n["read"] is False
        assert n["prediction_id"] == flow["pro_match_pid"]

    def test_non_matching_set_no_notification(self, flow):
        s = flow["pro"]["session"]
        r = s.get(f"{API}/notifications")
        data = r.json()
        for n in data["notifications"]:
            assert n["prediction_id"] != flow["pro_nomatch_pid"], \
                f"Non-matching set produced notif: {n}"

    def test_unread_count_reflects_notifications(self, flow):
        s = flow["pro"]["session"]
        r = s.get(f"{API}/notifications")
        data = r.json()
        assert data["unread_count"] == sum(1 for n in data["notifications"] if not n["read"])
        assert data["unread_count"] >= 1

    def test_free_user_gets_no_notifications(self, flow):
        s = flow["free"]["session"]
        r = s.get(f"{API}/notifications")
        assert r.status_code == 200
        data = r.json()
        assert data["unread_count"] == 0
        assert data["notifications"] == []

    def test_idempotency_no_new_notifications_on_repeat_refresh(self, flow, admin_session, mongo):
        pro_id = flow["pro"]["id"]
        before = mongo.notifications.count_documents({"user_id": pro_id})
        r = admin_session.post(f"{API}/admin/refresh-now")
        assert r.status_code == 200, r.text
        # No draw deleted, so no new draws / no new notifications
        assert r.json()["notifications_created"] == 0
        after = mongo.notifications.count_documents({"user_id": pro_id})
        assert after == before, f"Idempotency broken: {before} -> {after}"

    def test_mark_one_read(self, flow):
        s = flow["pro"]["session"]
        r = s.get(f"{API}/notifications")
        unread = [n for n in r.json()["notifications"] if not n["read"]]
        assert unread, "No unread notifs to test mark-read"
        n_id = unread[0]["id"]
        r = s.post(f"{API}/notifications/{n_id}/read")
        assert r.status_code == 200
        # verify
        r = s.get(f"{API}/notifications")
        got = next(n for n in r.json()["notifications"] if n["id"] == n_id)
        assert got["read"] is True

    def test_mark_read_unknown_404(self, flow):
        s = flow["pro"]["session"]
        r = s.post(f"{API}/notifications/does-not-exist-xyz/read")
        assert r.status_code == 404

    def test_mark_all_read(self, flow):
        s = flow["pro"]["session"]
        r = s.post(f"{API}/notifications/read-all")
        assert r.status_code == 200
        r = s.get(f"{API}/notifications")
        data = r.json()
        assert data["unread_count"] == 0
        assert all(n["read"] for n in data["notifications"])
