"""P2-07 mượn hồ sơ (UC-11, UC-16) + kho lưu trữ + thông báo."""

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.borrowing.application.requests import remind_overdue
from app.modules.borrowing.infrastructure.models import BorrowRequest
from tests.conftest import make_pdf, upload

F = "borrowing,notifications"
D = date.today()


def _setup(seed, login):
    admin = login("admin", features=F)
    loc = admin.post("/api/storage-locations", json={"name": "Kho A - Kệ 1", "code": "kho-a1"}).json()
    officer = login("officer", features=F)
    doc_id = upload(officer, seed["category"].id, make_pdf(["Ho so"]), "hs.pdf", title="Hồ sơ 1").json()["document_id"]
    return admin, officer, loc, doc_id


def _req(client, doc_id, start: int, end: int):
    return client.post(
        "/api/borrow-requests",
        json={
            "document_id": doc_id,
            "from_date": str(D + timedelta(days=start)),
            "to_date": str(D + timedelta(days=end)),
            "purpose": "Đối chiếu",
        },
    )


def test_storage_locations_admin_only(seed, login):
    admin, officer, loc, _ = _setup(seed, login)
    assert loc["code"] == "KHO-A1"
    assert officer.post("/api/storage-locations", json={"name": "X", "code": "X"}).status_code == 403
    assert admin.post("/api/storage-locations", json={"name": "Y", "code": "kho-a1"}).status_code == 409
    assert admin.patch(f"/api/storage-locations/{loc['id']}", json={"name": "Kho A"}).json()["name"] == "Kho A"
    assert [x["code"] for x in officer.get("/api/storage-locations").json()] == ["KHO-A1"]


def test_borrow_lifecycle(seed, login, db):
    admin, officer, loc, doc_id = _setup(seed, login)
    no_loc = _req(officer, doc_id, 1, 3)
    assert no_loc.status_code == 422 and no_loc.json()["error"]["code"] == "NO_STORAGE_LOCATION"
    r = officer.put(f"/api/documents/{doc_id}/storage-location", json={"storage_location_id": loc["id"]})
    assert r.json()["storage_location"]["code"] == "KHO-A1"
    assert _req(officer, doc_id, 3, 1).status_code == 422

    req = _req(officer, doc_id, 1, 5).json()
    assert req["status"] == "pending" and req["storage_location"] == "KHO-A1 - Kho A - Kệ 1"
    approver = login("approver", features=F)
    created = approver.get("/api/notifications").json()["items"][0]
    assert created["type"] == "borrow.created" and created["link_url"] == "/borrow-requests"
    assert officer.post(f"/api/borrow-requests/{req['id']}/approve").status_code == 403
    assert approver.post(f"/api/borrow-requests/{req['id']}/return").status_code == 409
    ok = approver.post(f"/api/borrow-requests/{req['id']}/approve").json()
    assert ok["status"] == "approved" and ok["approver_name"] == "Approver"

    overlap = _req(officer, doc_id, 4, 8)
    assert overlap.status_code == 409 and overlap.json()["error"]["code"] == "BORROW_OVERLAP"
    other = _req(officer, doc_id, 6, 8).json()
    assert approver.post(f"/api/borrow-requests/{other['id']}/reject").json()["status"] == "rejected"
    assert approver.post(f"/api/borrow-requests/{req['id']}/return").json()["status"] == "returned"
    mine = officer.get("/api/borrow-requests").json()
    assert mine["total"] == 2
    assert approver.get("/api/borrow-requests", params={"status": "returned"}).json()["total"] == 1
    types = [n["type"] for n in officer.get("/api/notifications").json()["items"]]
    assert {"borrow.approve", "borrow.reject", "borrow.return"} <= set(types)
    db.rollback()
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.module == "borrowing")).all())
    assert {
        "create_borrow_request",
        "borrow_approve",
        "borrow_reject",
        "borrow_return",
        "set_storage_location",
    } <= actions


def test_overdue_computed_and_reminded(seed, login, db):
    admin, officer, loc, doc_id = _setup(seed, login)
    officer.put(f"/api/documents/{doc_id}/storage-location", json={"storage_location_id": loc["id"]})
    req = _req(officer, doc_id, 0, 2).json()
    login("approver", features=F).post(f"/api/borrow-requests/{req['id']}/approve")
    row = db.get(BorrowRequest, UUID(req["id"]))
    row.from_date, row.to_date = D - timedelta(days=10), D - timedelta(days=1)
    db.commit()
    listed = officer.get("/api/borrow-requests", params={"overdue": True}).json()
    assert listed["total"] == 1 and listed["items"][0]["is_overdue"] is True
    assert remind_overdue() == 1
    assert officer.get("/api/notifications").json()["items"][0]["type"] == "borrow.overdue"
    assert admin.get("/api/dashboard").json()["extras"]["borrow_overdue"] == 1


def test_flag_off(seed, login):
    c = login("admin", features="")
    assert c.get("/api/borrow-requests").status_code == 404
    assert c.get("/api/storage-locations").status_code == 404
