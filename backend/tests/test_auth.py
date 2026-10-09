"""FR-01, UC-00, SDD mục 14: session Redis, CSRF, Origin, 401/403/429, khóa user thu hồi session."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from tests.conftest import PASSWORD


def _client(make_app) -> TestClient:
    return TestClient(make_app(""))


def test_login_returns_session_cookie_csrf_and_features(seed, make_app):
    c = _client(make_app)
    resp = c.post("/api/auth/login", json={"username": "officer", "password": PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["username"] == "officer" and body["roles"] == ["OFFICER"]
    assert body["csrf_token"] and body["features"] == []
    cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in cookie and "path=/api" in cookie and "samesite=lax" in cookie
    me = c.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["csrf_token"] == body["csrf_token"]


def test_login_by_email(seed, make_app):
    resp = _client(make_app).post("/api/auth/login", json={"username": "Officer@Test.vn", "password": PASSWORD})
    assert resp.status_code == 200


def test_wrong_password_401_and_audited(seed, make_app, db):
    resp = _client(make_app).post("/api/auth/login", json={"username": "officer", "password": "sai"})
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert resp.json()["error"]["request_id"]
    assert db.scalar(select(AuditLog).where(AuditLog.action == "login", AuditLog.result == "failure"))


def test_rate_limit_429(seed, make_app):
    c = _client(make_app)
    codes = [c.post("/api/auth/login", json={"username": "officer", "password": "sai"}).status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[-1] == 429
    assert c.post("/api/auth/login", json={"username": "officer", "password": PASSWORD}).status_code == 429


def test_unauthenticated_401_json(make_app):
    resp = _client(make_app).get("/api/documents")
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_mutation_without_csrf_403(seed, login):
    c = login("admin")
    del c.headers["X-CSRF-Token"]
    resp = c.post("/api/categories", json={"name": "X", "code": "X"})
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "CSRF_FAILED"


def test_foreign_origin_rejected(seed, login):
    c = login("admin")
    resp = c.post("/api/categories", json={"name": "X", "code": "X"}, headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "ORIGIN_REJECTED"
    ok = c.post("/api/categories", json={"name": "X", "code": "X"}, headers={"Origin": "http://localhost:5173"})
    assert ok.status_code == 201


def test_logout_revokes_session(seed, login):
    c = login("officer")
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").status_code == 401


def test_relogin_rotates_session(seed, login):
    c = login("officer")
    old = c.cookies.get("dms_sid")
    c.post("/api/auth/login", json={"username": "officer", "password": PASSWORD})
    assert c.cookies.get("dms_sid") != old


def test_lock_user_revokes_existing_sessions(seed, login):
    officer = login("officer")
    assert officer.get("/api/dashboard").status_code == 200
    admin = login("admin")
    resp = admin.patch(f"/api/users/{seed['officer'].id}", json={"is_active": False})
    assert resp.status_code == 200 and resp.json()["is_active"] is False
    assert officer.get("/api/dashboard").status_code == 401
    again = TestClient(officer.app).post("/api/auth/login", json={"username": "officer", "password": PASSWORD})
    assert again.status_code == 401 and again.json()["error"]["code"] == "ACCOUNT_LOCKED"


def test_non_admin_403(seed, login):
    c = login("officer")
    assert c.get("/api/users").status_code == 403
    assert c.get("/api/audit").status_code == 403
    assert c.post("/api/categories", json={"name": "X", "code": "X"}).status_code == 403


def test_security_headers_and_json_404(make_app):
    c = _client(make_app)
    resp = c.get("/api/khong-co")
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "HTTP_404"
    assert resp.headers["X-Content-Type-Options"] == "nosniff" and resp.headers["X-Request-ID"]
