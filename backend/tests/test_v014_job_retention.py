"""Hàng đợi xử lý chỉ lưu 30 ngày (JOB_RETENTION_DAYS): xóa job đã kết thúc quá hạn, giữ job mới nhất của tài liệu."""

import uuid
from datetime import timedelta

from sqlalchemy import select

from app.modules.jobs.application.retention import purge_old_jobs
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.shared.db import utcnow
from tests.conftest import make_pdf, upload


def test_purge_old_jobs_keeps_latest_per_document(seed, login, db):
    c = login("officer")
    body = upload(c, seed["category"].id, make_pdf(["a"]), "a.pdf").json()
    doc_id, latest_id = uuid.UUID(body["document_id"]), uuid.UUID(body["job_id"])
    old = utcnow() - timedelta(days=40)

    def job(**kw):
        j = ProcessingJob(
            **{
                "kind": "OCR",
                "status": "completed",
                "queued_at": old,
                "finished_at": old,
                "idempotency_key": uuid.uuid4().hex,
                **kw,
            }
        )
        db.add(j)
        return j

    older = job(document_id=doc_id)  # job cũ hơn của cùng tài liệu
    older.queued_at = old - timedelta(days=1)
    batch_old = job(document_id=None, kind="BULK_IMPORT")  # job cấp lô quá hạn
    batch_new = job(document_id=None, kind="BULK_IMPORT")
    batch_new.finished_at = utcnow() - timedelta(days=5)
    running = job(document_id=None, kind="BULK_IMPORT")
    running.status, running.finished_at = "processing", None
    latest = db.get(ProcessingJob, latest_id)
    latest.status, latest.finished_at = "completed", old  # job mới nhất của tài liệu: giữ dù quá hạn
    db.commit()
    gone, kept = {older.id, batch_old.id}, {latest_id, batch_new.id, running.id}

    assert purge_old_jobs() == 2
    db.expire_all()
    left = set(db.scalars(select(ProcessingJob.id)).all())
    assert kept <= left and not (gone & left)
