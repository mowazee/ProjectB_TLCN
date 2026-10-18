"""SDD v0.7 FR-09 (tài khoản của tôi), FR-10 (phòng ban), FR-01 bổ sung (thu hồi phiên khi khóa/đặt lại mật khẩu)."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.shared.config import settings
from app.shared.security.session import get_session_store
from tests.conftest import PASSWORD, make_pdf, upload

NEW_PASSWORD = "MatKhauMoi456!"


def _actions(db, action):
    db.expire_all()
    return db.scalars(select(AuditLog).where(AuditLog.action == action)).all()


# ---------------------------------------------------------------- FR-09 tài khoản của tôi
def test_account_profile_view_and_update(seed, login, db):
    c = login("officer")
    me = c.get("/api/account").json()
    assert me["username"] == "officer" and me["department_name"] == "Phòng A" and me["roles"] == ["OFFICER"]

    resp = c.patch("/api/account", json={"full_name": "  Nguyễn Văn A ", "phone": "0901234567"})
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Nguyễn Văn A" and resp.json()["phone"] == "0901234567"
    assert c.patch("/api/account", json={"full_name": "   "}).status_code == 422
    # Không tự đổi vai trò/phòng ban/email qua API tài khoản (trường lạ bị bỏ qua)
    c.patch("/api/account", json={"roles": ["ADMIN"], "email": "x@x.vn", "department_id": seed["dep_b"].id})
    me = c.get("/api/account").json()
    assert me["roles"] == ["OFFICER"] and me["email"] == "officer@test.vn" and me["department_id"] == seed["dep_a"].id
    assert len(_actions(db, "update_account")) == 1  # lần sửa không đổi gì thì không ghi audit


def test_change_password_rotates_session_and_revokes_others(seed, login, db):
    browser, other_device = login("officer"), login("officer")
    old_cookie = browser.cookies.get(settings.SESSION_COOKIE_NAME)

    resp = browser.post("/api/account/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert resp.status_code == 204
    assert other_device.get("/api/auth/me").status_code == 401  # phiên trên thiết bị khác bị thu hồi

    me = browser.get("/api/auth/me")  # trình duyệt hiện tại nhận phiên mới qua Set-Cookie
    assert me.status_code == 200
    new_cookie = browser.cookies.get(settings.SESSION_COOKIE_NAME)
    assert new_cookie != old_cookie
    browser.headers["X-CSRF-Token"] = me.json()["csrf_token"]
    assert browser.patch("/api/account", json={"phone": "1"}).status_code == 200  # CSRF mới dùng được

    anon = TestClient(browser.app)
    assert anon.post("/api/auth/login", json={"username": "officer", "password": PASSWORD}).status_code == 401
    assert anon.post("/api/auth/login", json={"username": "officer", "password": NEW_PASSWORD}).status_code == 200
    logs = _actions(db, "change_password")
    assert len(logs) == 1 and logs[0].result == "success" and logs[0].state_after["revoked_sessions"] >= 2


def test_change_password_validation(seed, login, db):
    c = login("officer")
    url = "/api/account/password"
    wrong = c.post(url, json={"current_password": "sai", "new_password": NEW_PASSWORD})
    assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "WRONG_PASSWORD"
    assert c.post(url, json={"current_password": PASSWORD, "new_password": "ngan"}).status_code == 422
    assert c.post(url, json={"current_password": PASSWORD, "new_password": PASSWORD}).status_code == 422
    assert c.get("/api/auth/me").status_code == 200  # thất bại không thu hồi phiên
    assert [log.result for log in _actions(db, "change_password")] == ["failure"]


def test_change_password_rate_limited(seed, login):
    c = login("officer")
    body = {"current_password": "sai", "new_password": NEW_PASSWORD}
    codes = [c.post("/api/account/password", json=body).status_code for _ in range(settings.LOGIN_MAX_FAILURES + 1)]
    assert codes[:-1] == [400] * settings.LOGIN_MAX_FAILURES and codes[-1] == 429
    # Đã vượt ngưỡng: mật khẩu đúng cũng bị chặn trong cửa sổ (không thì phiên bị lộ vẫn dò được mật khẩu)
    ok = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    assert c.post("/api/account/password", json=ok).status_code == 429
    get_session_store().reset(f"pwchange:{seed['officer'].id}")  # hết cửa sổ
    assert c.post("/api/account/password", json=ok).status_code == 204


def test_change_password_correct_resets_failures(seed, login):
    c = login("officer")
    for _ in range(settings.LOGIN_MAX_FAILURES):
        assert (
            c.post("/api/account/password", json={"current_password": "x", "new_password": NEW_PASSWORD}).status_code
            == 400
        )
    ok = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    assert c.post("/api/account/password", json=ok).status_code == 204  # chưa vượt ngưỡng: đổi được


# ---------------------------------------------------------------- FR-10 phòng ban
def test_departments_crud_and_counts(seed, login, db):
    admin = login("admin")
    listed = {d["code"]: d for d in admin.get("/api/departments").json()}
    assert listed["A"]["user_count"] == 2 and listed["B"]["user_count"] == 1

    created = admin.post("/api/departments", json={"code": "kt", "name": "Phòng Kế toán", "description": "Tài chính"})
    assert created.status_code == 201
    dep = created.json()
    assert dep["code"] == "KT" and dep["description"] == "Tài chính" and dep["user_count"] == 0
    assert admin.post("/api/departments", json={"code": "KT", "name": "Trùng"}).status_code == 409

    upd = admin.patch(f"/api/departments/{dep['id']}", json={"name": "Phòng Tài chính - Kế toán", "description": None})
    assert (
        upd.status_code == 200
        and upd.json()["name"] == "Phòng Tài chính - Kế toán"
        and upd.json()["description"] is None
    )
    dup = admin.patch(f"/api/departments/{dep['id']}", json={"code": "a"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "DEPARTMENT_DUPLICATE"

    assert admin.delete(f"/api/departments/{dep['id']}").status_code == 204
    assert admin.delete(f"/api/departments/{dep['id']}").status_code == 404
    assert {"create_department", "update_department", "delete_department"} <= {
        log.action for log in db.scalars(select(AuditLog)).all()
    }


def test_department_in_use_cannot_be_deleted(seed, login, db):
    admin, officer_b = login("admin"), login("officerb")
    dep_b = seed["dep_b"].id
    upload(officer_b, seed["category"].id, make_pdf(["a"]), "a.pdf")
    resp = admin.delete(f"/api/departments/{dep_b}")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "DEPARTMENT_IN_USE"
    assert resp.json()["error"]["details"] == {"user_count": 1, "document_count": 1}
    assert {d["code"]: d for d in admin.get("/api/departments").json()}["B"]["document_count"] == 1

    # Còn tài liệu (kể cả trong thùng rác) vẫn không xóa được dù đã chuyển hết người dùng đi
    admin.patch(f"/api/users/{seed['officer_b'].id}", json={"department_id": seed["dep_a"].id})
    resp = admin.delete(f"/api/departments/{dep_b}")
    assert resp.status_code == 409 and resp.json()["error"]["details"] == {"user_count": 0, "document_count": 1}


def test_department_write_requires_admin(seed, login):
    officer = login("officer")
    assert officer.get("/api/departments").status_code == 200  # đọc: mọi người dùng (form, bộ lọc)
    assert officer.post("/api/departments", json={"code": "X", "name": "X"}).status_code == 403
    assert officer.patch(f"/api/departments/{seed['dep_a'].id}", json={"name": "X"}).status_code == 403
    assert officer.delete(f"/api/departments/{seed['dep_b'].id}").status_code == 403


# ---------------------------------------------------------------- FR-01 bổ sung: thu hồi phiên
def test_admin_revokes_sessions(seed, login, db):
    admin, officer = login("admin"), login("officer")
    resp = admin.post(f"/api/users/{seed['officer'].id}/revoke-sessions")
    assert resp.status_code == 200 and resp.json()["revoked"] == 1
    assert officer.get("/api/auth/me").status_code == 401
    assert admin.get("/api/auth/me").status_code == 200
    assert len(_actions(db, "revoke_sessions")) == 1
    assert login("approver").post(f"/api/users/{seed['officer'].id}/revoke-sessions").status_code == 403


def test_admin_password_reset_revokes_sessions(seed, login):
    admin, officer = login("admin"), login("officer")
    resp = admin.patch(f"/api/users/{seed['officer'].id}", json={"password": NEW_PASSWORD})
    assert resp.status_code == 200
    assert officer.get("/api/auth/me").status_code == 401  # mật khẩu bị đặt lại -> phải đăng nhập lại
    assert admin.get("/api/auth/me").status_code == 200
    login("officer", NEW_PASSWORD)
