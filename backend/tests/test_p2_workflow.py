"""P2-01 (UC-14, UC-13, UC-15) duyệt/xuất bản + P2-07 notifications."""

from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from tests.conftest import make_pdf, upload

F = "workflow,notifications"


def _doc(seed, login):
    c = login("officer", features=F)
    return c, upload(c, seed["category"].id, make_pdf(["Quyet dinh"]), "qd.pdf", title="Quyết định 1").json()[
        "document_id"
    ]


def test_flag_off_returns_404(seed, login):
    c = login("officer", features="")
    doc_id = upload(c, seed["category"].id, make_pdf(["a"]), "a.pdf").json()["document_id"]
    assert c.post(f"/api/documents/{doc_id}/approval/submit").status_code == 404
    assert c.get("/api/reviews").status_code == 404
    assert c.get("/api/notifications").status_code == 404


def test_full_state_machine_with_notifications(seed, login, db):
    officer, doc_id = _doc(seed, login)
    approver = login("approver", features=F)
    st = officer.get(f"/api/documents/{doc_id}/approval").json()
    assert st == {"approval_status": "draft", "allowed_actions": ["submit"]}

    assert officer.post(f"/api/documents/{doc_id}/approval/approve").status_code == 403  # sai quyền
    assert approver.post(f"/api/documents/{doc_id}/approval/approve").status_code == 409  # sai trạng thái
    r = officer.post(f"/api/documents/{doc_id}/approval/submit")
    assert r.status_code == 200 and r.json()["approval_status"] == "pending_review"
    assert officer.post(f"/api/documents/{doc_id}/approval/submit").json()["error"]["code"] == "INVALID_TRANSITION"

    queue = approver.get("/api/reviews").json()
    assert queue["total"] == 1 and queue["items"][0]["title"] == "Quyết định 1"
    assert queue["items"][0]["submitted_by"] == "Officer"
    assert officer.get("/api/reviews").status_code == 403
    bell = approver.get("/api/notifications").json()
    assert bell["unread"] == 1 and bell["items"][0]["type"] == "approval.submit"
    assert bell["items"][0]["message"] == "'Quyết định 1'" and bell["items"][0]["link_url"] == "/reviews"

    assert approver.get(f"/api/documents/{doc_id}/approval").json()["allowed_actions"] == ["approve", "reject"]
    assert approver.post(f"/api/documents/{doc_id}/approval/approve", json={"comments": "OK"}).status_code == 200
    assert approver.post(f"/api/documents/{doc_id}/approval/publish").json()["approval_status"] == "published"
    assert approver.post(f"/api/documents/{doc_id}/approval/unpublish").json()["approval_status"] == "unpublished"
    assert approver.post(f"/api/documents/{doc_id}/approval/publish").json()["approval_status"] == "published"

    history = officer.get(f"/api/documents/{doc_id}/approvals").json()
    assert [h["action"] for h in history] == ["submit", "approve", "publish", "unpublish", "publish"]
    assert history[1]["actor_name"] == "Approver" and history[1]["comments"] == "OK"
    db.rollback()
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.module == "workflow")).all())
    assert {"approval_submit", "approval_approve", "approval_publish", "approval_unpublish"} <= actions

    notes = officer.get("/api/notifications").json()
    types = [n["type"] for n in notes["items"]]
    assert "approval.approve" in types and notes["unread"] == len(types)
    approved = next(n for n in notes["items"] if n["type"] == "approval.approve")
    assert approved["message"] == "'Quyết định 1' - OK" and approved["link_url"] == f"/documents/{doc_id}"
    first = notes["items"][0]["id"]
    assert officer.post(f"/api/notifications/{first}/read").json()["is_read"] is True
    assert approver.post(f"/api/notifications/{first}/read").status_code == 404  # không lộ của người khác
    assert officer.post("/api/notifications/read-all").json()["updated"] == len(types) - 1


def test_reject_requires_reason_and_resubmit(seed, login):
    officer, doc_id = _doc(seed, login)
    approver = login("approver", features=F)
    officer.post(f"/api/documents/{doc_id}/approval/submit")
    bad = approver.post(f"/api/documents/{doc_id}/approval/reject", json={"comments": "  "})
    assert bad.status_code == 422 and bad.json()["error"]["fields"] == {"comments": "required"}
    assert (
        approver.post(f"/api/documents/{doc_id}/approval/reject", json={"comments": "Thiếu chữ ký"}).status_code == 200
    )
    assert approver.post(f"/api/documents/{doc_id}/approval/publish").status_code == 409
    assert officer.post(f"/api/documents/{doc_id}/approval/submit").json()["approval_status"] == "pending_review"


def test_scope_and_ocr_edit_does_not_change_status(seed, login, fake_engine, enqueued):
    from tests.conftest import make_png, run_all_jobs

    officer = login("officer", features=F)
    doc_id = upload(officer, seed["category"].id, make_png(), "a.png").json()["document_id"]
    run_all_jobs(enqueued)
    assert login("officerb", features=F).post(f"/api/documents/{doc_id}/approval/submit").status_code == 403
    officer.post(f"/api/documents/{doc_id}/approval/submit")
    officer.put(f"/api/documents/{doc_id}/pages/1/correction", json={"corrected_text": "sửa", "base_version": 0})
    assert officer.get(f"/api/documents/{doc_id}").json()["approval_status"] == "pending_review"
    assert officer.get("/api/dashboard").json()["extras"]["documents_pending_review"] == 1
