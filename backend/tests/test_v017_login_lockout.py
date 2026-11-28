"""v0.17: khóa tài khoản sau 5 lần sai mật khẩu, quên mật khẩu qua email (link 30 phút), khôi phục mở lại tài khoản."""

import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.users.infrastructure.models import PasswordResetToken, User
from app.shared import email
from app.shared.config import settings
from app.shared.db import SessionLocal, utcnow
from tests.conftest import PASSWORD

NEW_PASSWORD = "MatKhauMoi@2026"
SEND_FAILED = "Không gửi được email khôi phục mật khẩu, vui lòng liên hệ Quản trị viên"


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, text: str, html: str | None = None) -> None:
        self.sent.append((to, subject, text))


class BrokenSender:
    def send(self, to: str, subject: str, text: str, html: str | None = None) -> None:
        raise ConnectionRefusedError("smtp down")


@pytest.fixture
def mailbox():
    box = FakeSender()
    email.set_email_sender(box)
    yield box
    email.set_email_sender(None)


def _login(c: TestClient, password: str, username: str = "officer"):
    return c.post("/api/auth/login", json={"username": username, "password": password})


def _lock(c: TestClient) -> None:
    for _ in range(settings.ACCOUNT_LOCK_THRESHOLD):
        _login(c, "sai")


def _token(mailbox: FakeSender) -> str:
    m = re.search(r"/reset-password/(\S+)", mailbox.sent[-1][2])
    assert m
    return m.group(1)


def _user(db, seed) -> User:
    """Đọc bằng phiên mới: phiên `db` của test có thể còn giữ ảnh chụp cũ của SQLite sau khi API ghi."""
    with SessionLocal() as fresh:
        return fresh.get(User, seed["officer"].id)


# ---------------------------------------------------------------- khóa tài khoản
INVALID = "Tên đăng nhập hoặc mật khẩu không đúng, lưu ý tài khoản sẽ bị khóa nếu nhập sai mật khẩu quá 5 lần"


def test_wrong_password_warns_then_locked(seed, make_app, db):
    c = TestClient(make_app(""))
    for _ in range(settings.ACCOUNT_LOCK_THRESHOLD - 1):
        r = _login(c, "sai")
        assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"
        assert r.json()["error"]["message"] == INVALID
        assert "remaining_attempts" not in r.json()["error"].get("details", {})
    # tên đăng nhập không tồn tại: cùng thông báo (không phân biệt được tài khoản có thật)
    assert _login(c, "sai", username="khongco").json()["error"]["message"] == INVALID
    r = _login(c, "sai")
    assert r.status_code == 401 and r.json()["error"]["code"] == "ACCOUNT_LOCKED"
    assert "liên hệ Quản trị viên" in r.json()["error"]["message"]
    user = _user(db, seed)
    assert user.is_active is False and user.locked_reason == "failed_logins"
    # đã khóa: đúng mật khẩu cũng không vào được, vẫn báo bị khóa
    r = _login(c, PASSWORD)
    assert r.status_code == 401 and r.json()["error"]["code"] == "ACCOUNT_LOCKED"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "auto_lock_user"))


def test_successful_login_resets_counter(seed, make_app, db):
    c = TestClient(make_app(""))
    for _ in range(settings.ACCOUNT_LOCK_THRESHOLD - 1):
        _login(c, "sai")
    assert _login(c, PASSWORD).status_code == 200
    assert _user(db, seed).failed_login_count == 0
    _login(c, "sai")
    assert _user(db, seed).failed_login_count == 1


def test_lock_revokes_existing_sessions(seed, login, make_app):
    officer = login("officer")
    _lock(TestClient(make_app("")))
    assert officer.get("/api/auth/me").status_code == 401


def test_admin_unlock_clears_lock(seed, login, make_app, db):
    _lock(TestClient(make_app("")))
    admin = login("admin")
    items = admin.get("/api/users", params={"page_size": 100}).json()["items"]
    listed = next(u for u in items if u["id"] == str(seed["officer"].id))
    assert listed["is_active"] is False and listed["locked_reason"] == "failed_logins"
    assert admin.patch(f"/api/users/{seed['officer'].id}", json={"is_active": True}).status_code == 200
    user = _user(db, seed)
    assert user.locked_reason is None and user.failed_login_count == 0
    assert _login(TestClient(make_app("")), PASSWORD).status_code == 200


def test_admin_locked_account_hides_state_on_wrong_password(seed, login, make_app):
    admin = login("admin")
    admin.patch(f"/api/users/{seed['officer'].id}", json={"is_active": False})
    c = TestClient(make_app(""))
    assert _login(c, "sai").json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert _login(c, PASSWORD).json()["error"]["code"] == "ACCOUNT_LOCKED"


# ---------------------------------------------------------------- quên mật khẩu
def test_options_and_disabled_without_smtp(seed, make_app):
    c = TestClient(make_app(""))
    assert c.get("/api/auth/options").json()["password_reset"] is False
    r = c.post("/api/auth/forgot-password", json={"login": "officer"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "EMAIL_NOT_CONFIGURED"


def test_forgot_sends_link_and_same_reply_for_unknown(seed, make_app, mailbox, db):
    c = TestClient(make_app(""))
    opts = c.get("/api/auth/options").json()
    assert opts == {"password_reset": True, "password_reset_ttl_minutes": 30}
    known = c.post("/api/auth/forgot-password", json={"login": "Officer@Test.vn"})
    unknown = c.post("/api/auth/forgot-password", json={"login": "khongco@test.vn"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(mailbox.sent) == 1 and mailbox.sent[0][0] == "officer@test.vn"
    assert "30 phút" in mailbox.sent[0][2]
    row = db.scalar(select(PasswordResetToken))
    assert row.token_hash != _token(mailbox)  # chỉ lưu băm
    assert c.get(f"/api/auth/reset-password/{_token(mailbox)}").json() == {"username": "officer"}


def test_reset_password_unlocks_and_is_single_use(seed, login, make_app, mailbox, db):
    officer = login("officer")
    c = TestClient(make_app(""))
    _lock(c)
    c.post("/api/auth/forgot-password", json={"login": "officer"})
    token = _token(mailbox)
    assert c.post(f"/api/auth/reset-password/{token}", json={"new_password": "ngan"}).status_code == 422
    r = c.post(f"/api/auth/reset-password/{token}", json={"new_password": NEW_PASSWORD})
    assert r.status_code == 200 and r.json()["reactivated"] is True
    user = _user(db, seed)
    assert user.is_active is True and user.locked_reason is None and user.failed_login_count == 0
    assert officer.get("/api/auth/me").status_code == 401  # phiên cũ bị thu hồi
    assert _login(c, PASSWORD).status_code == 401
    assert _login(c, NEW_PASSWORD).status_code == 200
    again = c.post(f"/api/auth/reset-password/{token}", json={"new_password": "KhacNua@2026"})
    assert again.status_code == 410 and again.json()["error"]["code"] == "RESET_LINK_INVALID"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "reset_password"))


def test_reset_link_expires_after_30_minutes(seed, make_app, mailbox, db):
    c = TestClient(make_app(""))
    c.post("/api/auth/forgot-password", json={"login": "officer"})
    row = db.scalar(select(PasswordResetToken))
    delta = row.expires_at.replace(tzinfo=None) - row.created_at.replace(tzinfo=None)
    assert timedelta(minutes=29) < delta <= timedelta(minutes=30, seconds=5)
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert c.get(f"/api/auth/reset-password/{_token(mailbox)}").status_code == 410
    r = c.post(f"/api/auth/reset-password/{_token(mailbox)}", json={"new_password": NEW_PASSWORD})
    assert r.status_code == 410


def test_new_link_replaces_old(seed, make_app, mailbox):
    c = TestClient(make_app(""))
    c.post("/api/auth/forgot-password", json={"login": "officer"})
    first = _token(mailbox)
    c.post("/api/auth/forgot-password", json={"login": "officer"})
    assert c.get(f"/api/auth/reset-password/{first}").status_code == 410
    assert c.get(f"/api/auth/reset-password/{_token(mailbox)}").status_code == 200


def test_admin_locked_account_gets_no_reset_mail(seed, login, make_app, mailbox):
    login("admin").patch(f"/api/users/{seed['officer'].id}", json={"is_active": False})
    c = TestClient(make_app(""))
    r = c.post("/api/auth/forgot-password", json={"login": "officer"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "EMAIL_SEND_FAILED"
    assert r.json()["error"]["message"] == SEND_FAILED
    assert mailbox.sent == []


def test_account_without_valid_email_reports_send_failed(seed, make_app, mailbox, db):
    user = db.get(User, seed["officer"].id)
    user.email = "chua-co-email"  # tài khoản Admin tạo nhưng chưa có email hợp lệ
    db.commit()
    r = TestClient(make_app("")).post("/api/auth/forgot-password", json={"login": "officer"})
    assert r.status_code == 503 and r.json()["error"]["message"] == SEND_FAILED
    assert mailbox.sent == []
    assert db.scalar(select(PasswordResetToken)) is None


def test_smtp_error_reports_send_failed_and_drops_token(seed, make_app, db):
    email.set_email_sender(BrokenSender())
    try:
        r = TestClient(make_app("")).post("/api/auth/forgot-password", json={"login": "officer"})
    finally:
        email.set_email_sender(None)
    assert r.status_code == 503 and r.json()["error"]["code"] == "EMAIL_SEND_FAILED"
    assert db.scalar(select(PasswordResetToken)) is None
    failed = db.scalar(select(AuditLog).where(AuditLog.action == "request_password_reset"))
    assert failed is not None and failed.result == "failure"


def test_reset_mail_rate_limited_per_account(seed, make_app, mailbox):
    c = TestClient(make_app(""))
    codes = [
        c.post("/api/auth/forgot-password", json={"login": "officer"}).status_code
        for _ in range(settings.PASSWORD_RESET_PER_HOUR + 1)
    ]
    assert codes == [202] * settings.PASSWORD_RESET_PER_HOUR + [429]
    assert len(mailbox.sent) == settings.PASSWORD_RESET_PER_HOUR
