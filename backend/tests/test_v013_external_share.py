"""FR-18 (SDD v0.13, D-13): chia sẻ ra ngoài bằng link + OTP email; NFR-02 cho endpoint công khai."""

import re
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.sharing.infrastructure.models import ShareLink
from app.shared import email
from app.shared.db import utcnow
from tests.conftest import VALID, make_pdf, run_all_jobs, upload

WF = "workflow,notifications"


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


def _published(seed, login, enqueued):
    owner, approver = login("officer", features=WF), login("approver", features=WF)
    doc = upload(owner, seed["category"].id, make_pdf(["Noi dung"]), "qd.pdf", title="Quyết định").json()["document_id"]
    run_all_jobs(enqueued)
    for c, a in ((owner, "submit"), (approver, "approve"), (approver, "publish")):
        assert c.post(f"/api/documents/{doc}/approval/{a}", json=VALID if a == "submit" else None).status_code == 200, a
    return owner, approver, doc


def _share(client, doc, **body):
    data = {"recipient_email": "khach@example.com", "expires_in_hours": 24, "allow_download": True, **body}
    return client.post(f"/api/documents/{doc}/external-shares", json=data)


def _public(make_app) -> TestClient:
    """Trình duyệt của người nhận: không đăng nhập."""
    return TestClient(make_app(WF))


def test_create_rules(seed, login, enqueued, fake_engine, mailbox):
    owner, approver, doc = _published(seed, login, enqueued)
    assert _share(owner, doc, expires_in_hours=25).status_code == 422
    assert _share(owner, doc, recipient_email="khong-hop-le").status_code == 422
    assert _share(login("officerb", features=WF), doc).status_code in (403, 404)
    r = _share(owner, doc)
    assert r.status_code == 201, r.text
    assert r.json()["url"].startswith("http") and "/s/" in r.json()["url"]
    run_all_jobs(enqueued)
    assert mailbox.sent and mailbox.sent[0][0] == "khach@example.com" and "/s/" in mailbox.sent[0][2]
    listed = owner.get(f"/api/documents/{doc}/external-shares").json()
    assert listed["enabled"] and listed["items"][0]["email_status"] == "sent"
    assert _share(approver, doc).status_code == 201  # Kiểm duyệt viên phòng ban của tài liệu
    # chưa xuất bản → 409
    draft = upload(owner, seed["category"].id, make_pdf(["x"]), "x.pdf").json()["document_id"]
    assert _share(owner, draft).json()["error"]["code"] == "DOCUMENT_NOT_PUBLISHED"


def test_email_not_configured(seed, login, enqueued, fake_engine):
    owner, _, doc = _published(seed, login, enqueued)
    assert owner.get(f"/api/documents/{doc}/external-shares").json()["enabled"] is False
    assert _share(owner, doc).status_code == 503


def test_otp_flow_view_download_and_revoke(seed, login, enqueued, fake_engine, mailbox, make_app, db):
    owner, approver, doc = _published(seed, login, enqueued)
    url = _share(owner, doc).json()["url"]
    run_all_jobs(enqueued)
    token = url.rsplit("/s/", 1)[1]
    pub = _public(make_app)
    base = f"/api/public/shares/{token}"
    info = pub.get(base)
    assert info.status_code == 200 and info.json()["verified"] is False and info.json()["pages"] == []
    assert info.headers["cache-control"] == "no-store" and info.headers["referrer-policy"] == "no-referrer"
    assert pub.get(f"{base}/file").status_code == 401  # chưa xác thực OTP
    origin = {"Origin": "http://testserver"}
    assert pub.post(f"{base}/otp", headers=origin).json()["sent_to"].startswith("kh***@")
    run_all_jobs(enqueued)
    code = re.search(r"\b(\d{6})\b", mailbox.sent[-1][1]).group(1)
    assert (
        pub.post(
            f"{base}/verify", json={"code": "000000" if code != "000000" else "111111"}, headers=origin
        ).status_code
        == 422
    )
    assert pub.post(f"{base}/verify", json={"code": code}, headers=origin).status_code == 204
    data = pub.get(base).json()
    assert data["verified"] and data["pages"][0]["page_number"] == 1
    assert pub.get(f"{base}/pages/1/image").status_code == 200
    f = pub.get(f"{base}/file")
    assert f.status_code == 200 and "attachment" in f.headers["content-disposition"]
    assert pub.get(f"{base}/bundle").status_code == 200
    # API khác không dùng được phiên xem
    assert pub.get(f"/api/documents/{doc}").status_code == 401
    # thu hồi → 410
    link_id = owner.get(f"/api/documents/{doc}/external-shares").json()["items"][0]["id"]
    assert owner.delete(f"/api/external-shares/{link_id}").status_code == 204
    assert pub.get(base).status_code == 410
    db.rollback()
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.module == "sharing")))
    assert {
        "create_external_share",
        "external_verify",
        "external_view",
        "external_download",
        "revoke_external_share",
    } <= actions


def test_view_only_expired_unpublished_and_lockout(seed, login, enqueued, fake_engine, mailbox, make_app, db):
    owner, approver, doc = _published(seed, login, enqueued)
    token = _share(owner, doc, allow_download=False).json()["url"].rsplit("/s/", 1)[1]
    run_all_jobs(enqueued)
    pub = _public(make_app)
    base, origin = f"/api/public/shares/{token}", {"Origin": "http://testserver"}
    pub.post(f"{base}/otp", headers=origin)
    run_all_jobs(enqueued)
    code = re.search(r"\b(\d{6})\b", mailbox.sent[-1][1]).group(1)
    pub.post(f"{base}/verify", json={"code": code}, headers=origin)
    assert pub.get(f"{base}/file").status_code == 403  # chỉ xem
    # hủy xuất bản → link mất hiệu lực
    approver.post(f"/api/documents/{doc}/approval/unpublish")
    assert pub.get(base).status_code == 410
    approver.post(f"/api/documents/{doc}/approval/publish")
    # hết hạn → 410
    db.rollback()
    link = db.scalar(select(ShareLink).where(ShareLink.document_id == uuid.UUID(doc)))
    link.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert pub.get(base).status_code == 410
    # sai OTP quá số lần → 429
    token2 = _share(owner, doc).json()["url"].rsplit("/s/", 1)[1]
    run_all_jobs(enqueued)
    b2 = f"/api/public/shares/{token2}"
    pub.post(f"{b2}/otp", headers=origin)
    codes = [pub.post(f"{b2}/verify", json={"code": "999999"}, headers=origin).status_code for _ in range(6)]
    assert codes[-1] == 429
    assert pub.get("/api/public/shares/" + "x" * 43).status_code == 410  # token đoán bừa
