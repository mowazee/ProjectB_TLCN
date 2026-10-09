"""FR-01 (UC-06), FR-02 (UC-09), FR-08 audit (UC-08)."""

from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from tests.conftest import make_pdf, upload


def test_admin_creates_user(seed, login, db):
    admin = login("admin")
    resp = admin.post(
        "/api/users",
        json={
            "username": "NguyenA",
            "email": "a@test.vn",
            "full_name": "Nguyễn A",
            "password": "Password123!",
            "roles": ["APPROVER"],
            "department_id": seed["dep_a"].id,
        },
    )
    assert resp.status_code == 201 and resp.json()["roles"] == ["APPROVER"]
    assert resp.json()["username"] == "nguyena"
    assert db.scalar(select(AuditLog).where(AuditLog.action == "create_user"))
    dup = admin.post(
        "/api/users",
        json={
            "username": "officer",
            "email": "z@test.vn",
            "full_name": "Z",
            "password": "Password123!",
            "roles": ["OFFICER"],
        },
    )
    assert dup.status_code == 409 and dup.json()["error"]["fields"] == {"username": "duplicate"}
    bad = admin.post(
        "/api/users", json={"username": "x", "email": "bad", "full_name": "", "password": "1", "roles": []}
    )
    assert bad.status_code == 422 and {"username", "email", "password"} <= set(bad.json()["error"]["fields"])


def test_admin_cannot_lock_self(seed, login):
    resp = login("admin").patch(f"/api/users/{seed['admin'].id}", json={"is_active": False})
    assert resp.status_code == 422


def test_roles_departments_and_users_list(seed, login):
    admin = login("admin")
    assert [r["name"] for r in admin.get("/api/roles").json()] == ["ADMIN", "OFFICER", "APPROVER"]
    page = admin.get("/api/users", params={"page_size": 2}).json()
    assert page["total"] == 4 and len(page["items"]) == 2 and page["page_size"] == 2
    assert len(login("officer").get("/api/departments").json()) == 3


def test_inactive_category_not_selectable_old_documents_keep_it(seed, login, db):
    officer = login("officer")
    doc_id = upload(officer, seed["category"].id, make_pdf(["noi dung mau"]), "a.pdf").json()["document_id"]
    admin = login("admin")
    resp = admin.patch(f"/api/categories/{seed['category'].id}", json={"is_active": False})
    assert resp.status_code == 200 and resp.json()["is_active"] is False
    assert db.scalar(select(AuditLog).where(AuditLog.action == "deactivate_category"))
    bad = upload(officer, seed["category"].id, make_pdf(["moi"]), "b.pdf")
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "CATEGORY_INACTIVE"
    active = officer.get("/api/categories", params={"active_only": True}).json()
    assert seed["category"].id not in [c["id"] for c in active]
    assert officer.get(f"/api/documents/{doc_id}").json()["category"]["name"] == "Hợp đồng"


def test_category_duplicate_409(seed, login):
    resp = login("admin").post("/api/categories", json={"name": "Lặp", "code": "hop-dong"})
    assert resp.status_code == 409


def test_audit_filters_admin_only(seed, login):
    admin = login("admin")
    page = admin.get("/api/audit", params={"user_id": str(seed["admin"].id)}).json()
    assert page["total"] > 0 and all(i["user_id"] == str(seed["admin"].id) for i in page["items"])
    assert admin.get("/api/audit", params={"date_from": "2000-01-01", "date_to": "2000-01-02"}).json()["total"] == 0
    assert admin.get("/api/audit", params={"action": "CREATE_USER"}).json()["total"] >= 3
    assert admin.delete("/api/audit").status_code == 405
    assert login("approver").get("/api/audit").status_code == 403
