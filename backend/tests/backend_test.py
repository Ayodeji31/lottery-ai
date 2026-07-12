"""End-to-end backend tests for LottoPredict API.

Covers: games/draws/stats, auth (register/login/logout/me),
predictions (statistical + AI), saved predictions CRUD, and auth guarding.
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://jackpot-analyzer-24.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@lottopredict.app")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
TEST_USER_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "Passw0rd!")


# ---------- Fixtures ----------
@pytest.fixture
def anon_client():
    """Fresh unauthenticated session per test to avoid cookie bleed."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="session")
def registered_user():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"test_user_{uuid.uuid4().hex[:8]}@lottopredict.app"
    password = TEST_USER_PASSWORD
    r = s.post(f"{API}/auth/register", json={"name": "Test User", "email": email, "password": password})
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
    return {"session": s, "email": email, "password": password, "user": r.json()}


# ---------- Health / games ----------
class TestHealthAndGames:
    def test_root(self, anon_client):
        r = anon_client.get(f"{API}/")
        assert r.status_code == 200
        assert "LottoPredict" in r.json().get("message", "")

    def test_get_games(self, anon_client):
        r = anon_client.get(f"{API}/games")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        ids = {g["id"] for g in data}
        assert {"lotto", "euromillions"} <= ids
        for g in data:
            for key in ["name", "main_count", "main_max", "bonus_count", "bonus_max", "bonus_label"]:
                assert key in g, f"Missing key {key} in game {g['id']}"


# ---------- Draws ----------
class TestDraws:
    @pytest.mark.parametrize("game", ["lotto", "euromillions"])
    def test_get_draws(self, anon_client, game):
        r = anon_client.get(f"{API}/draws/{game}?limit=20")
        assert r.status_code == 200
        draws = r.json()
        assert isinstance(draws, list)
        assert len(draws) > 0, f"No draws for {game}"
        d = draws[0]
        for k in ["game", "draw_date", "main_numbers", "bonus_numbers"]:
            assert k in d
        assert d["game"] == game
        # main numbers count
        expected_main = 6 if game == "lotto" else 5
        assert len(d["main_numbers"]) == expected_main
        # bonus count
        expected_bonus = 1 if game == "lotto" else 2
        assert len(d["bonus_numbers"]) == expected_bonus

    def test_get_draws_unknown_game(self, anon_client):
        r = anon_client.get(f"{API}/draws/foobar")
        assert r.status_code == 404


# ---------- Stats ----------
class TestStats:
    @pytest.mark.parametrize("game,main_max", [("lotto", 59), ("euromillions", 50)])
    def test_stats(self, anon_client, game, main_max):
        r = anon_client.get(f"{API}/stats/{game}")
        assert r.status_code == 200
        s = r.json()
        for key in ["total_draws", "main_frequency", "bonus_frequency", "hot", "cold", "overdue"]:
            assert key in s
        assert s["total_draws"] > 0
        assert len(s["main_frequency"]) == main_max
        assert len(s["hot"]) == 6
        assert len(s["cold"]) == 6
        assert len(s["overdue"]) == 6
        # entries look correct
        assert set(s["hot"][0].keys()) >= {"number", "count", "percentage", "draws_ago"}


# ---------- Auth ----------
class TestAuth:
    def test_admin_login(self, anon_client):
        r = anon_client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        assert "id" in data
        assert "access_token" in r.cookies

    def test_login_invalid(self, anon_client):
        r = anon_client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_register_and_me(self, registered_user):
        s = registered_user["session"]
        # Cookie should be set - GET /me
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["email"] == registered_user["email"]
        assert me["role"] == "user"

    def test_register_duplicate(self, anon_client, registered_user):
        r = anon_client.post(f"{API}/auth/register", json={
            "name": "dup", "email": registered_user["email"], "password": TEST_USER_PASSWORD
        })
        assert r.status_code == 400

    def test_me_unauth(self, anon_client):
        # brand new session with no cookies
        s = requests.Session()
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_register_returns_access_token(self, anon_client):
        email = f"test_user_{uuid.uuid4().hex[:8]}@lottopredict.app"
        r = anon_client.post(f"{API}/auth/register", json={
            "name": "Bearer User", "email": email, "password": TEST_USER_PASSWORD
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("access_token"), str)
        assert len(body["access_token"]) > 20
        assert body["email"] == email

    def test_login_returns_access_token(self, anon_client):
        r = anon_client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body.get("access_token"), str)
        assert len(body["access_token"]) > 20

    def test_bearer_only_me_no_cookies(self, anon_client):
        # Login and grab token from body
        r = anon_client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        token = r.json()["access_token"]
        # Fresh session (no cookies) + Authorization header
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {token}"})
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 200, r.text
        assert r.json()["email"] == ADMIN_EMAIL

    def test_bearer_invalid_token(self, anon_client):
        s = requests.Session()
        s.headers.update({"Authorization": "Bearer notavalidjwt"})
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_logout(self, registered_user):
        # use a fresh session to avoid corrupting the shared session
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{API}/auth/login", json={"email": registered_user["email"], "password": registered_user["password"]})
        assert r.status_code == 200
        assert s.get(f"{API}/auth/me").status_code == 200
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        # cookies cleared -> unauth
        s.cookies.clear()
        assert s.get(f"{API}/auth/me").status_code == 401


# ---------- Predictions ----------
class TestPredictions:
    def test_statistical_requires_auth(self, anon_client):
        r = anon_client.post(f"{API}/predict/statistical/lotto")
        assert r.status_code == 401

    def test_ai_requires_auth(self, anon_client):
        r = anon_client.post(f"{API}/predict/ai/lotto")
        assert r.status_code == 401

    @pytest.mark.parametrize("game", ["lotto", "euromillions"])
    def test_statistical(self, registered_user, game):
        s = registered_user["session"]
        r = s.post(f"{API}/predict/statistical/{game}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["method"] == "statistical"
        assert data["game"] == game
        preds = data["predictions"]
        assert len(preds) == 3
        expected_main = 6 if game == "lotto" else 5
        expected_bonus = 1 if game == "lotto" else 2
        for p in preds:
            assert len(p["main_numbers"]) == expected_main
            assert len(p["bonus_numbers"]) == expected_bonus
            assert len(set(p["main_numbers"])) == expected_main

    def test_ai(self, registered_user):
        s = registered_user["session"]
        r = s.post(f"{API}/predict/ai/lotto", timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["method"] == "ai"
        assert "predictions" in data
        assert "summary" in data
        preds = data["predictions"]
        assert len(preds) >= 1
        for p in preds:
            assert len(p["main_numbers"]) == 6
            assert len(p["bonus_numbers"]) == 1


# ---------- PWA ----------
class TestPWA:
    def test_manifest_json(self, anon_client):
        # PWA manifest is served by frontend origin (same origin as REACT_APP_BACKEND_URL)
        r = anon_client.get(f"{BASE_URL}/manifest.json", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "name" in data or "short_name" in data
        assert "icons" in data

    def test_service_worker(self, anon_client):
        r = anon_client.get(f"{BASE_URL}/sw.js", timeout=15)
        assert r.status_code == 200
        assert "serviceWorker" in r.text or "self.addEventListener" in r.text


# ---------- Saved predictions ----------
class TestSaved:
    def test_saved_requires_auth(self, anon_client):
        assert anon_client.get(f"{API}/saved").status_code == 401
        assert anon_client.post(f"{API}/saved", json={"game": "lotto"}).status_code == 401

    def test_saved_unknown_game_400(self, registered_user):
        s = registered_user["session"]
        r = s.post(f"{API}/saved", json={
            "game": "bogusgame", "method": "manual",
            "main_numbers": [1, 2, 3], "bonus_numbers": [],
        })
        assert r.status_code == 400, r.text

    def test_saved_crud(self, registered_user):
        s = registered_user["session"]
        payload = {
            "game": "lotto",
            "method": "statistical",
            "main_numbers": [1, 2, 3, 4, 5, 6],
            "bonus_numbers": [7],
            "reasoning": "TEST_reasoning",
        }
        r = s.post(f"{API}/saved", json=payload)
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["game"] == "lotto"
        assert created["main_numbers"] == payload["main_numbers"]
        assert "id" in created
        pid = created["id"]

        r = s.get(f"{API}/saved")
        assert r.status_code == 200
        items = r.json()
        assert any(i["id"] == pid for i in items)

        # ensure no leaking _id from mongo
        for it in items:
            assert "_id" not in it

        # delete
        r = s.delete(f"{API}/saved/{pid}")
        assert r.status_code == 200
        # verify gone
        r = s.get(f"{API}/saved")
        assert not any(i["id"] == pid for i in r.json())
        # deleting again -> 404
        r = s.delete(f"{API}/saved/{pid}")
        assert r.status_code == 404

    def test_saved_isolated_per_user(self, registered_user):
        # user 2
        s2 = requests.Session()
        s2.headers.update({"Content-Type": "application/json"})
        email = f"TEST_user_{uuid.uuid4().hex[:8]}@lottopredict.app"
        r = s2.post(f"{API}/auth/register", json={"name": "u2", "email": email, "password": TEST_USER_PASSWORD})
        assert r.status_code == 200

        s1 = registered_user["session"]
        r = s1.post(f"{API}/saved", json={
            "game": "euromillions", "method": "manual",
            "main_numbers": [10, 20, 30, 40, 50], "bonus_numbers": [1, 2],
        })
        assert r.status_code == 200
        pid = r.json()["id"]

        # user2 should not see user1's saved item
        r = s2.get(f"{API}/saved")
        assert r.status_code == 200
        assert not any(i["id"] == pid for i in r.json())

        # user2 cannot delete user1's saved item
        r = s2.delete(f"{API}/saved/{pid}")
        assert r.status_code == 404

        # cleanup
        s1.delete(f"{API}/saved/{pid}")
