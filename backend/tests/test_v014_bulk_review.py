"""FR-20 (SDD v0.14): duyệt, xuất bản, từ chối hàng loạt."""

import uuid

from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.documents.infrastructure.models import Document
from app.modules.workflow.infrastructure.models import DocumentApproval
from tests.conftest import VALID, make_pdf, upload

F = "workflow,notifications"
CHECKS = ["validity", "physical_copy", "extraction", "metadata"]


def _pending(seed, login, n, title="Hồ sơ"):
    owner = login("officer", features=F)
    ids = []
    for i in range(n):
        doc = upload(owner, seed["category"].id, make_pdf([f"{title} {i}"]), f"{i}.pdf", title=f"{title} {i}").json()
        assert owner.post(f"/api/documents/{doc['document_id']}/approval/submit", json=VALID).status_code == 200
        ids.append(doc["document_id"])
    return owner, ids


def test_bulk_approve_publish_with_checklist(seed, login, db):
    owner, ids = _pending(seed, login, 3)
    approver = login("approver", features=F)
    body = {"action": "approve_publish", "document_ids": ids}
    r = approver.post("/api/reviews/bulk", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "CHECKLIST_REQUIRED"
    r = approver.post("/api/reviews/bulk", json={**body, "confirmed_checks": CHECKS})
    assert r.status_code == 200
    out = r.json()
    assert out["succeeded"] == 3 and out["failed"] == 0
    assert {x["approval_status"] for x in out["results"]} == {"published"}
    db.rollback()
    batch = out["batch_id"]
    rows = db.scalars(select(AuditLog).where(AuditLog.action.in_(["approval_approve", "approval_publish"]))).all()
    assert len(rows) == 6 and all(x.state_after["batch_id"] == batch for x in rows)
    assert db.scalar(select(AuditLog).where(AuditLog.action == "bulk_review")).state_after["succeeded"] == 3
    assert len(db.scalars(select(DocumentApproval).where(DocumentApproval.action == "publish")).all()) == 3
    assert approver.get("/api/reviews").json()["total"] == 0


def test_bulk_partial_failure_and_reject_reason(seed, login):
    owner, ids = _pending(seed, login, 2)
    draft = upload(owner, seed["category"].id, make_pdf(["n"]), "n.pdf", title="Nháp").json()["document_id"]
    approver = login("approver", features=F)
    r = approver.post("/api/reviews/bulk", json={"action": "reject", "document_ids": ids})
    assert r.status_code == 422 and r.json()["error"]["fields"] == {"comments": "required"}
    r = approver.post(
        "/api/reviews/bulk", json={"action": "reject", "document_ids": [*ids, draft], "comments": "Thiếu"}
    )
    out = r.json()
    assert out["succeeded"] == 2 and out["failed"] == 1
    bad = next(x for x in out["results"] if not x["ok"])
    assert bad["document_id"] == draft and bad["error_code"] == "INVALID_TRANSITION"


def test_bulk_limit_and_roles(seed, login):
    officer = login("officer", features=F)
    many = [f"00000000-0000-0000-0000-{i:012d}" for i in range(21)]
    body = {"action": "approve", "document_ids": many, "confirmed_checks": CHECKS}
    assert officer.post("/api/reviews/bulk", json=body).status_code == 403
    r = login("approver", features=F).post("/api/reviews/bulk", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "BULK_LIMIT"


def test_review_queue_hides_expired(seed, login, db):
    _, ids = _pending(seed, login, 2)
    db.rollback()
    db.get(Document, uuid.UUID(ids[0])).validity_status = "expired"
    db.commit()
    approver = login("approver", features=F)
    assert {x["document_id"] for x in approver.get("/api/reviews").json()["items"]} == {ids[1]}
    got = approver.get("/api/reviews", params={"include_expired": "true"}).json()["items"]
    assert {x["document_id"] for x in got} == set(ids)
