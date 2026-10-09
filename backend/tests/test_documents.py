"""FR-03 (UC-01, NFR-01), FR-07 (UC-05, UC-05b, D-05): upload, quyền, xóa mềm, khôi phục, purge."""

from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.documents.application.purge import purge_expired
from app.modules.documents.infrastructure.models import Document
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.shared.config import settings
from app.shared.db import utcnow
from app.shared.errors import StorageError
from app.shared.storage import LocalStorage
from tests.conftest import make_pdf, make_png, upload


def test_upload_creates_active_document_and_queued_job(seed, login, db, enqueued):
    c = login("officer")
    resp = upload(c, seed["category"].id, make_pdf(["Hop dong"], pages=2), "hop-dong.pdf", title="Hợp đồng A")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["lifecycle_status"] == "active" and body["job_status"] == "queued"
    assert enqueued == [(UUID(body["job_id"]), "ocr")]  # gửi sang hàng đợi SAU commit
    detail = c.get(f"/api/documents/{body['document_id']}").json()
    assert detail["title"] == "Hợp đồng A" and detail["file_type"] == "PDF" and detail["job_status"] == "queued"
    assert "storage_key" not in detail and detail["approval_status"] == "draft"
    assert detail["job_id"] == body["job_id"]
    assert db.scalar(select(AuditLog).where(AuditLog.action == "upload_document"))


@pytest.mark.parametrize(
    ("data", "name", "status", "code"),
    [
        (make_png(), "gia-mao.pdf", 415, "EXTENSION_MISMATCH"),
        (b"MZ\x90\x00 exe", "virus.pdf", 415, "UNSUPPORTED_FILE_TYPE"),
        (b"%PDF-1.4 hong", "hong.pdf", 400, "FILE_CORRUPT"),
    ],
)
def test_upload_rejects_bad_files(seed, login, db, enqueued, data, name, status, code):
    resp = upload(login("officer"), seed["category"].id, data, name)
    assert resp.status_code == status and resp.json()["error"]["code"] == code
    assert db.scalar(select(func.count(Document.id))) == 0 and enqueued == []


def test_upload_limits_413(seed, login, monkeypatch):
    monkeypatch.setattr(settings, "MAX_PAGES", 1)
    resp = upload(login("officer"), seed["category"].id, make_pdf(["a"], pages=2), "dai.pdf")
    assert resp.status_code == 413 and resp.json()["error"]["code"] == "TOO_MANY_PAGES"
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0)
    resp = upload(login("officer"), seed["category"].id, make_pdf(["a"]), "a.pdf")
    assert resp.status_code == 413 and resp.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_missing_metadata_422(seed, login):
    resp = login("officer").post("/api/documents", files={"file": ("a.pdf", make_pdf(["a"]))})
    assert resp.status_code == 422 and "category_id" in resp.json()["error"]["fields"]


def test_storage_error_no_document_no_job(seed, login, db, enqueued, monkeypatch):
    def broken(self, key, data):
        raise StorageError("đầy")

    monkeypatch.setattr(LocalStorage, "save_bytes", broken)
    resp = upload(login("officer"), seed["category"].id, make_pdf(["a"]), "a.pdf")
    assert resp.status_code == 500 and resp.json()["error"]["code"] == "STORAGE_ERROR"
    assert db.scalar(select(func.count(ProcessingJob.id))) == 0 and enqueued == []


def test_queue_unavailable_marks_job_failed(seed, login, db, monkeypatch):
    from app.modules.jobs.infrastructure import dispatcher

    def down(*a, **k):
        raise ConnectionError("broker down")

    monkeypatch.setattr(dispatcher, "send", down)
    body = upload(login("officer"), seed["category"].id, make_pdf(["a"]), "a.pdf").json()
    db.rollback()
    db.expire_all()
    job = db.get(ProcessingJob, UUID(body["job_id"]))
    assert job.status == "failed" and job.error_code == "QUEUE_UNAVAILABLE"


def test_same_file_twice_two_documents(seed, login):
    c = login("officer")
    data = make_pdf(["cung file"])
    ids = {upload(c, seed["category"].id, data, "a.pdf").json()["document_id"] for _ in range(2)}
    assert len(ids) == 2


def test_permissions_by_scope(seed, login):
    doc_id = upload(login("officer"), seed["category"].id, make_pdf(["a"]), "a.pdf").json()["document_id"]
    other = login("officerb")
    assert other.get(f"/api/documents/{doc_id}").status_code == 403
    assert other.patch(f"/api/documents/{doc_id}", json={"title": "x"}).status_code == 403
    assert other.get("/api/documents").json()["total"] == 0
    approver = login("approver")
    assert approver.get(f"/api/documents/{doc_id}").json()["can_edit"] is False
    assert approver.patch(f"/api/documents/{doc_id}", json={"title": "x"}).status_code == 403
    assert approver.get(f"/api/documents/{doc_id}/file").status_code == 403
    assert upload(approver, seed["category"].id, make_pdf(["a"]), "a.pdf").status_code == 403
    assert login("admin").get("/api/documents").json()["total"] == 1


def test_update_metadata_and_download(seed, login, db):
    c = login("officer")
    data = make_pdf(["noi dung"])
    doc_id = upload(c, seed["category"].id, data, "hop-dong.pdf").json()["document_id"]
    resp = c.patch(f"/api/documents/{doc_id}", json={"title": "Tên mới", "category_id": seed["category2"].id})
    assert resp.status_code == 200 and resp.json()["title"] == "Tên mới"
    assert resp.json()["category"]["name"] == "Công văn"
    log = db.scalar(select(AuditLog).where(AuditLog.action == "update_document"))
    assert log.state_before["title"] == "hop-dong" and log.state_after["title"] == "Tên mới"
    file = c.get(f"/api/documents/{doc_id}/file")
    assert file.status_code == 200 and file.content == data


def test_soft_delete_trash_restore(seed, login, db):
    c = login("officer")
    body = upload(c, seed["category"].id, make_pdf(["a"]), "a.pdf").json()
    doc_id = body["document_id"]
    assert c.delete(f"/api/documents/{doc_id}").status_code == 204
    assert c.get(f"/api/documents/{doc_id}").status_code == 404
    assert c.get("/api/documents").json()["total"] == 0
    trash = c.get("/api/documents", params={"lifecycle_status": "deleted"}).json()
    assert trash["total"] == 1 and trash["items"][0]["restore_deadline"]
    db.rollback()
    db.expire_all()
    assert db.get(ProcessingJob, UUID(body["job_id"])).error_code == "DOCUMENT_DELETED"
    assert login("approver").post(f"/api/documents/{doc_id}/restore").status_code == 403
    resp = c.post(f"/api/documents/{doc_id}/restore")
    assert resp.status_code == 200 and resp.json()["lifecycle_status"] == "active"
    assert c.get("/api/documents").json()["total"] == 1
    db.rollback()
    actions = set(db.scalars(select(AuditLog.action)).all())
    assert {"delete_document", "restore_document"} <= actions


def test_restore_expired_410_and_purge_keeps_audit(seed, login, db):
    c = login("officer")
    doc_id = upload(c, seed["category"].id, make_pdf(["a"]), "a.pdf").json()["document_id"]
    c.delete(f"/api/documents/{doc_id}")
    doc = db.get(Document, UUID(doc_id))
    doc.deleted_at = utcnow() - timedelta(days=settings.SOFT_DELETE_RETENTION_DAYS + 1)
    db.commit()
    resp = c.post(f"/api/documents/{doc_id}/restore")
    assert resp.status_code == 410 and resp.json()["error"]["code"] == "RESTORE_EXPIRED"
    assert purge_expired() == 1
    db.rollback()
    db.expire_all()
    assert db.get(Document, UUID(doc_id)) is None
    assert c.post(f"/api/documents/{doc_id}/restore").status_code == 404
    purge_log = db.scalar(select(AuditLog).where(AuditLog.action == "purge"))
    assert purge_log.state_before["document_id"] == doc_id
    assert db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == "upload_document")) == 1


def test_purge_skips_document_with_running_job(seed, login, db):
    c = login("officer")
    body = upload(c, seed["category"].id, make_pdf(["a"]), "a.pdf").json()
    doc = db.get(Document, UUID(body["document_id"]))
    doc.lifecycle_status = "deleted"
    doc.deleted_at = utcnow() - timedelta(days=99)
    job = db.get(ProcessingJob, UUID(body["job_id"]))
    job.status = "processing"
    db.commit()
    assert purge_expired() == 0
