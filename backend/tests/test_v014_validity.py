"""FR-19 (SDD v0.14, D-14): hiệu lực tài liệu."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.documents.application import validity
from app.modules.documents.infrastructure.models import Document
from app.modules.notifications.infrastructure.models import Notification
from app.shared import email
from tests.conftest import VALID, make_pdf, upload

F = "workflow,notifications"


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, text: str, html: str | None = None) -> None:
        self.sent.append((to, subject, text))


@pytest.fixture
def mailbox():
    box = FakeSender()
    email.set_email_sender(box)
    yield box
    email.set_email_sender(None)


def _setup(seed, login, title="Quyết định hiệu lực"):
    owner, approver = login("officer", features=F), login("approver", features=F)
    doc = upload(owner, seed["category"].id, make_pdf(["a"]), "a.pdf", title=title).json()["document_id"]
    return owner, approver, doc


def _publish(owner, approver, doc, body=None):
    assert owner.post(f"/api/documents/{doc}/approval/submit", json=body or VALID).status_code == 200
    assert approver.post(f"/api/documents/{doc}/approval/approve").status_code == 200
    assert approver.post(f"/api/documents/{doc}/approval/publish").status_code == 200


def _set_db(db, doc, **values):
    db.rollback()
    d = db.get(Document, uuid.UUID(doc))
    for k, v in values.items():
        setattr(d, k, v)
    db.commit()


def test_submit_requires_validity_and_future_date(seed, login):
    owner, _, doc = _setup(seed, login)
    base = f"/api/documents/{doc}/approval/submit"
    r = owner.post(base)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDITY_REQUIRED"
    yesterday = (validity.today() - timedelta(days=1)).isoformat()
    r = owner.post(base, json={"validity_status": "effective_until", "valid_until": yesterday})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_VALID_UNTIL"
    r = owner.post(base, json={"validity_status": "effective_until"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_VALID_UNTIL"
    today = validity.today().isoformat()
    assert owner.post(base, json={"validity_status": "effective_until", "valid_until": today}).status_code == 200
    got = owner.get(f"/api/documents/{doc}").json()
    assert got["validity_status"] == "effective_until" and got["valid_until"] == today


def test_resubmit_keeps_previous_declaration(seed, login):
    owner, approver, doc = _setup(seed, login)
    base = f"/api/documents/{doc}/approval"
    assert owner.post(f"{base}/submit", json={"validity_status": "unspecified"}).status_code == 200
    assert approver.post(f"{base}/reject", json={"comments": "Thiếu chữ ký"}).status_code == 200
    assert owner.post(f"{base}/submit").status_code == 200  # đã khai báo (dù giữ nguyên Không quy định)


def test_reviewer_adjusts_validity_on_approve(seed, login, db):
    owner, approver, doc = _setup(seed, login)
    base = f"/api/documents/{doc}/approval"
    owner.post(f"{base}/submit", json=VALID)
    until = (validity.today() + timedelta(days=30)).isoformat()
    r = approver.post(f"{base}/approve", json={"validity_status": "effective_until", "valid_until": until})
    assert r.status_code == 200
    item = owner.get(f"/api/documents/{doc}").json()
    assert item["validity_status"] == "effective_until" and item["valid_until"] == until
    db.rollback()
    logs = db.scalars(select(AuditLog).where(AuditLog.action == "change_validity").order_by(AuditLog.id)).all()
    assert [lg.state_after["validity_status"] for lg in logs] == ["effective", "effective_until"]


def test_change_after_publish_needs_reviewer_and_reason(seed, login):
    owner, approver, doc = _setup(seed, login)
    url = f"/api/documents/{doc}/validity"
    assert owner.put(url, json={"validity_status": "effective"}).status_code == 200  # Nháp: chủ sở hữu, không lý do
    _publish(owner, approver, doc)
    assert "validity" not in owner.get(f"/api/documents/{doc}").json()["permissions"]
    assert owner.put(url, json={"validity_status": "expired", "reason": "Đã thay thế"}).status_code == 403
    r = approver.put(url, json={"validity_status": "expired"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "REASON_REQUIRED"
    r = approver.put(url, json={"validity_status": "expired", "reason": "Đã có văn bản thay thế"})
    assert r.status_code == 200 and r.json()["validity_status"] == "expired"
    # Gia hạn tài liệu đã hết hiệu lực: được, kèm lý do
    until = (validity.today() + timedelta(days=10)).isoformat()
    body = {"validity_status": "effective_until", "valid_until": until, "reason": "Gia hạn theo quyết định mới"}
    assert login("admin", features=F).put(url, json=body).json()["valid_until"] == until


def test_past_date_is_expired_and_hidden_by_default(seed, login, db):
    owner, approver, doc = _setup(seed, login)
    other = upload(owner, seed["category"].id, make_pdf(["b"]), "b.pdf", title="Còn hiệu lực").json()["document_id"]
    _set_db(db, doc, validity_status="effective_until", valid_until=validity.today() - timedelta(days=1))
    assert owner.get(f"/api/documents/{doc}").json()["validity_status"] == "expired"  # API tự tính, chưa cần beat

    def ids(**params):
        return {x["id"] for x in owner.get("/api/documents", params=params).json()["items"]}

    assert doc not in ids() and other in ids()
    assert {doc, other} <= ids(include_expired="true")
    assert ids(validity="expired") == {doc}


def test_scheduled_expires_and_reminds_once(seed, login, db, mailbox):
    owner, approver, doc = _setup(seed, login)
    soon = upload(owner, seed["category"].id, make_pdf(["c"]), "c.pdf", title="Sắp hết").json()["document_id"]
    _set_db(db, doc, validity_status="effective_until", valid_until=validity.today() - timedelta(days=1))
    _set_db(db, soon, validity_status="effective_until", valid_until=validity.today() + timedelta(days=3))
    assert validity.run_scheduled() == {"expired": 1, "reminded": 1}
    assert validity.run_scheduled() == {"expired": 0, "reminded": 0}  # idempotent, nhắc một lần
    db.rollback()
    expired = db.get(Document, uuid.UUID(doc))
    assert str(expired.validity_status) == "expired" and expired.valid_until is not None
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "validity_expired")) == 1
    types = set(db.scalars(select(Notification.type)).all())
    assert {"validity.expired", "validity.expiring"} <= types
    assert len(mailbox.sent) == 1 and "Sắp hết" in mailbox.sent[0][1]
    # Đổi ngày hết hạn -> nhắc lại theo ngày mới
    approver_url = f"/api/documents/{soon}/validity"
    new_until = (validity.today() + timedelta(days=5)).isoformat()
    assert (
        owner.put(approver_url, json={"validity_status": "effective_until", "valid_until": new_until}).status_code
        == 200
    )
    assert validity.run_scheduled()["reminded"] == 1


def test_search_hides_expired_by_default(seed, login, db):
    owner, _, doc = _setup(seed, login, title="Nghị định thử nghiệm")
    _set_db(db, doc, validity_status="expired")

    def hits(**params):
        items = owner.get("/api/search", params={"q": "Nghị định thử nghiệm", **params}).json()["items"]
        return {x["document_id"]: x["validity_status"] for x in items}

    assert doc not in hits()
    assert hits(include_expired="true")[doc] == "expired"
    assert doc in hits(validity="expired")
