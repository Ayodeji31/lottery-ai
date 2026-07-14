"""Tests for in-app subscription management endpoints.

- GET /api/payments/subscription for anonymous -> 401
- GET /api/payments/subscription for a fresh (non-pro) user -> {is_pro:false, status:'none', auto_renew:false, days_remaining:0, price:4.99}
- POST /api/payments/subscription/cancel and /resume:
    * 401 for anon
    * 400 for user with no subscription object
    * cancel -> auto_renew:false, status:'canceled', still is_pro:true
    * resume -> auto_renew:true, status:'active'
- Pro user (subscription seeded directly in Mongo) GET returns correct
  is_pro=true, status='active', auto_renew=true, days_remaining ~30, renews_at set.
"""
import os
import uuid
import asyncio
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://jackpot-analyzer-24.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"

TEST_USER_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "Passw0rd!")


def _register_fresh():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_sub_{uuid.uuid4().hex[:10]}@lottopredict.app"
    r = s.post(f"{API}/auth/register", json={
        "name": "Sub Tester", "email": email, "password": TEST_USER_PASSWORD
    })
    assert r.status_code == 200, r.text
    return {"session": s, "email": email, "user": r.json()}


def _make_pro(uid: str, days: int = 30, auto_renew: bool = True):
    """Directly set pro_until + subscription object in Mongo."""
    import motor.motor_asyncio
    from bson import ObjectId
    client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGO_URL"])
    dbm = client[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    until = (now + timedelta(days=days)).isoformat()
    asyncio.get_event_loop().run_until_complete(
        dbm.users.update_one(
            {"_id": ObjectId(uid)},
            {"$set": {
                "pro_until": until,
                "subscription": {
                    "status": "active" if auto_renew else "canceled",
                    "auto_renew": auto_renew,
                    "plan": "pro_monthly",
                    "started_at": now.isoformat(),
                    "renews_at": until,
                    "canceled_at": None if auto_renew else now.isoformat(),
                },
            }},
        )
    )
    return until


class TestSubscriptionAuth:
    def test_get_subscription_requires_auth(self):
        r = requests.get(f"{API}/payments/subscription")
        assert r.status_code == 401

    def test_cancel_requires_auth(self):
        r = requests.post(f"{API}/payments/subscription/cancel")
        assert r.status_code == 401

    def test_resume_requires_auth(self):
        r = requests.post(f"{API}/payments/subscription/resume")
        assert r.status_code == 401


class TestSubscriptionFreshFreeUser:
    def test_get_subscription_free_user_shape(self):
        u = _register_fresh()
        r = u["session"].get(f"{API}/payments/subscription")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["is_pro"] is False
        assert data["status"] in ("none", "expired")
        assert data["auto_renew"] is False
        assert data["days_remaining"] == 0
        assert data["price"] == 4.99
        assert data["plan"] == "pro_monthly"

    def test_cancel_without_subscription_returns_400(self):
        u = _register_fresh()
        r = u["session"].post(f"{API}/payments/subscription/cancel")
        assert r.status_code == 400, r.text

    def test_resume_without_subscription_returns_400(self):
        u = _register_fresh()
        r = u["session"].post(f"{API}/payments/subscription/resume")
        assert r.status_code == 400, r.text


class TestSubscriptionProUser:
    def test_pro_user_active_shape(self):
        u = _register_fresh()
        s = u["session"]
        uid = u["user"]["id"]
        _make_pro(uid, days=30, auto_renew=True)

        r = s.get(f"{API}/payments/subscription")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["is_pro"] is True
        assert data["status"] == "active"
        assert data["auto_renew"] is True
        assert data["plan"] == "pro_monthly"
        assert data["renews_at"] is not None
        assert 28 <= data["days_remaining"] <= 31
        assert data["price"] == 4.99

    def test_cancel_then_resume_flow(self):
        u = _register_fresh()
        s = u["session"]
        uid = u["user"]["id"]
        _make_pro(uid, days=30, auto_renew=True)

        # Cancel
        r = s.post(f"{API}/payments/subscription/cancel")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["is_pro"] is True  # still pro until pro_until
        assert data["status"] == "canceled"
        assert data["auto_renew"] is False
        assert 28 <= data["days_remaining"] <= 31

        # GET reflects cancel
        r2 = s.get(f"{API}/payments/subscription")
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["auto_renew"] is False
        assert d2["status"] == "canceled"
        assert d2["is_pro"] is True

        # Resume
        r3 = s.post(f"{API}/payments/subscription/resume")
        assert r3.status_code == 200, r3.text
        d3 = r3.json()
        assert d3["auto_renew"] is True
        assert d3["status"] == "active"
        assert d3["is_pro"] is True

        # GET reflects resume
        r4 = s.get(f"{API}/payments/subscription")
        assert r4.status_code == 200
        assert r4.json()["auto_renew"] is True
        assert r4.json()["status"] == "active"

    def test_canceled_user_still_pro_can_access_euromillions(self):
        """After cancel, user retains Pro access until period ends (verify gating)."""
        u = _register_fresh()
        s = u["session"]
        uid = u["user"]["id"]
        _make_pro(uid, days=30, auto_renew=True)

        s.post(f"{API}/payments/subscription/cancel")

        # Should still access Pro-gated euromillions
        r = s.post(f"{API}/predict/statistical/euromillions")
        assert r.status_code == 200, r.text

    def test_me_endpoint_pro_flag_after_seed(self):
        u = _register_fresh()
        s = u["session"]
        uid = u["user"]["id"]
        _make_pro(uid, days=30, auto_renew=True)

        me = s.get(f"{API}/auth/me").json()
        assert me.get("is_pro") is True
