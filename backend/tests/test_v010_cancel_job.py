"""FR-04 (SDD v0.10): dừng job OCR đang chờ / đang xử lý; chạy lại được."""

from uuid import UUID

import pymupdf
from sqlalchemy import select, update

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.documents.infrastructure.models import DocumentPage
from app.modules.jobs.application.runner import run_job
from app.modules.jobs.domain.model import JobOutcome, JobStatus
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.modules.ocr.domain.events import OcrCompleted
from app.shared.db import SessionLocal
from app.shared.events import bus
from tests.conftest import make_png, upload


def _scan_pdf(pages: int) -> bytes:
    """PDF chỉ có ảnh (như bản scan): mỗi trang phải OCR."""
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_image(page.rect, stream=make_png(f"Trang scan {i + 1}", size=(1190, 1684)))
    return bytes(doc.tobytes())


def _upload(seed, login, pages=3):
    officer = login("officer")
    body = upload(officer, seed["category"].id, _scan_pdf(pages), "scan.pdf").json()
    return officer, UUID(body["document_id"]), UUID(body["job_id"])


def test_cancel_queued_job_then_retry(seed, login, db, fake_engine, enqueued):
    officer, doc_id, job_id = _upload(seed, login)
    resp = officer.post(f"/api/jobs/{job_id}/cancel")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed" and body["error_code"] == "CANCELLED" and "Đã dừng" in body["error_message"]
    assert run_job(job_id) == JobOutcome.SKIPPED and fake_engine.calls == 0  # message cũ tới worker: bỏ qua
    assert officer.post(f"/api/jobs/{job_id}/cancel").status_code == 409  # đã dừng rồi

    assert officer.post(f"/api/jobs/{job_id}/retry").status_code == 200
    assert run_job(job_id) == JobOutcome.COMPLETED
    db.rollback()  # phiên test đọc lại dữ liệu mới nhất
    db.expire_all()
    assert db.get(ProcessingJob, job_id).status == JobStatus.COMPLETED
    log = db.scalar(select(AuditLog).where(AuditLog.action == "cancel_job"))
    assert log is not None and log.state_after["error_code"] == "CANCELLED"


def test_cancel_while_processing_stops_after_current_page(seed, login, db, fake_engine):
    officer, doc_id, job_id = _upload(seed, login, pages=3)
    original = fake_engine.recognize

    def recognize_then_user_cancels(image):
        out = original(image)
        if fake_engine.calls == 1:  # người dùng bấm Dừng trong lúc trang 1 đang OCR
            with SessionLocal() as other:
                other.execute(
                    update(ProcessingJob)
                    .where(ProcessingJob.id == job_id)
                    .values(status=JobStatus.FAILED, error_code="CANCELLED")
                )
                other.commit()
        return out

    fake_engine.recognize = recognize_then_user_cancels
    events = []
    bus.subscribe(OcrCompleted, events.append)
    assert run_job(job_id) == JobOutcome.FAILED
    assert fake_engine.calls == 1 and events == []  # không xử lý trang 2, 3; không phát OcrCompleted
    db.rollback()  # phiên test đọc lại dữ liệu mới nhất
    db.expire_all()
    job = db.get(ProcessingJob, job_id)
    assert job.status == JobStatus.FAILED and job.error_code == "CANCELLED"  # worker không ghi đè
    pages = db.scalars(select(DocumentPage).where(DocumentPage.document_id == doc_id)).all()
    assert [p.page_number for p in pages] == [1]  # trang đã xong được giữ lại

    fake_engine.recognize = original
    assert officer.post(f"/api/jobs/{job_id}/retry").status_code == 200
    assert run_job(job_id) == JobOutcome.COMPLETED
    db.rollback()  # phiên test đọc lại dữ liệu mới nhất
    db.expire_all()
    assert len(db.scalars(select(DocumentPage).where(DocumentPage.document_id == doc_id)).all()) == 3


def test_cancel_permissions(seed, login, db, fake_engine):
    officer, _, job_id = _upload(seed, login)
    assert login("approver").post(f"/api/jobs/{job_id}/cancel").status_code == 403  # không quản lý tài liệu
    assert login("officerb").post(f"/api/jobs/{job_id}/cancel").status_code == 403  # phòng ban khác
    assert run_job(job_id) == JobOutcome.COMPLETED
    done = officer.post(f"/api/jobs/{job_id}/cancel")
    assert done.status_code == 409 and done.json()["error"]["code"] == "JOB_NOT_ACTIVE"


def test_cancel_right_after_last_page_does_not_complete(seed, login, db, fake_engine, monkeypatch):
    """Bấm Dừng đúng lúc trang cuối vừa xong: không đánh dấu hoàn tất, không phát OcrCompleted (trích xuất/phân loại)."""
    from app.modules.ocr.application import run_ocr

    _, _, job_id = _upload(seed, login, pages=1)
    real_publish = run_ocr.publish

    def cancel_then_publish(session, evt):
        with SessionLocal() as other:
            other.execute(
                update(ProcessingJob)
                .where(ProcessingJob.id == job_id)
                .values(status=JobStatus.FAILED, error_code="CANCELLED")
            )
            other.commit()
        real_publish(session, evt)

    monkeypatch.setattr(run_ocr, "publish", cancel_then_publish)
    events = []
    bus.subscribe(OcrCompleted, events.append)
    assert run_job(job_id) == JobOutcome.FAILED and events == []
    db.rollback()
    job = db.get(ProcessingJob, job_id)
    assert job.status == JobStatus.FAILED and job.error_code == "CANCELLED"
