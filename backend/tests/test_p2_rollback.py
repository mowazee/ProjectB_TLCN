"""P2-09 rollback thay đổi (UC-08b)."""

from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from tests.conftest import make_pdf, make_png, run_all_jobs, upload

F = "rollback"


def _log_id(db, action: str) -> int:
    db.rollback()
    return db.scalar(select(AuditLog.id).where(AuditLog.action == action).order_by(AuditLog.id.desc()))


def test_document_rollback_and_stale_409(seed, login, db):
    officer = login("officer", features=F)
    doc_id = upload(officer, seed["category"].id, make_pdf(["a"]), "a.pdf", title="Ban đầu").json()["document_id"]
    officer.patch(f"/api/documents/{doc_id}", json={"title": "Lần 1"})
    first = _log_id(db, "update_document")
    admin = login("admin", features=F)
    preview = admin.get(f"/api/audit/{first}/rollback").json()
    assert preview["supported"] and not preview["changed_since"] and preview["target"]["title"] == "Ban đầu"

    officer.patch(f"/api/documents/{doc_id}", json={"title": "Lần 2"})
    stale = admin.post(f"/api/audit/{first}/rollback")
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "ROLLBACK_STALE"
    ok = admin.post(f"/api/audit/{first}/rollback", json={"confirm": True})
    assert ok.status_code == 200
    assert officer.get(f"/api/documents/{doc_id}").json()["title"] == "Ban đầu"
    db.rollback()
    log = db.scalar(select(AuditLog).where(AuditLog.action == "rollback_document"))
    assert log.state_after["rollback_of"] == first and log.state_before["title"] == "Lần 2"
    assert db.scalar(select(AuditLog).where(AuditLog.id == first)) is not None  # không xóa lịch sử


def test_ocr_rollback_creates_new_version(seed, login, db, fake_engine, enqueued):
    officer = login("officer", features=F)
    doc_id = upload(officer, seed["category"].id, make_png(), "a.png").json()["document_id"]
    run_all_jobs(enqueued)
    raw = officer.get(f"/api/documents/{doc_id}/pages/1").json()["raw_text"]
    officer.put(f"/api/documents/{doc_id}/pages/1/correction", json={"corrected_text": "Sửa sai", "base_version": 0})
    log_id = _log_id(db, "edit_ocr")
    r = login("admin", features=F).post(f"/api/audit/{log_id}/rollback")
    assert r.status_code == 200, r.text
    page = officer.get(f"/api/documents/{doc_id}/pages/1").json()
    assert page["version"] == 2 and page["effective_text"] == raw
    assert _log_id(db, "rollback_ocr") is not None


def test_category_rollback_and_permissions(seed, login, db):
    admin = login("admin", features=F)
    admin.patch(f"/api/categories/{seed['category'].id}", json={"is_active": False})
    log_id = _log_id(db, "deactivate_category")
    assert login("officer", features=F).post(f"/api/audit/{log_id}/rollback").status_code == 403
    assert admin.post(f"/api/audit/{log_id}/rollback").status_code == 200
    cats = {c["id"]: c for c in admin.get("/api/categories").json()}
    assert cats[seed["category"].id]["is_active"] is True
    login_log = _log_id(db, "login")
    bad = admin.post(f"/api/audit/{login_log}/rollback")
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "ROLLBACK_NOT_SUPPORTED"
    assert login("admin", features="").post(f"/api/audit/{log_id}/rollback").status_code == 404
