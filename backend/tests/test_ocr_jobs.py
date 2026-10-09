"""FR-04 (UC-02): job queued -> processing -> completed/failed, retry không trùng, needs_review,
engine lỗi, tài liệu bị xóa, job treo; OcrCompleted phát sau commit."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select

from app.modules.documents.infrastructure.models import DocumentPage
from app.modules.jobs.application.runner import run_job
from app.modules.jobs.domain.model import JobOutcome, JobStatus
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.modules.ocr.application import engines
from app.modules.ocr.domain.events import OcrCompleted
from app.modules.ocr.domain.ports import OcrLine
from app.modules.ocr.infrastructure.models import OcrResult
from app.shared.config import settings
from app.shared.db import utcnow
from app.shared.events import bus
from tests.conftest import make_pdf, make_png, upload


def _upload(seed, login, data, name):
    body = upload(login("officer"), seed["category"].id, data, name).json()
    return UUID(body["document_id"]), UUID(body["job_id"])


def test_text_layer_pdf_no_ocr_engine(seed, login, db, fake_engine):
    doc_id, job_id = _upload(seed, login, make_pdf(["Hợp đồng kinh tế số 45"], pages=2), "a.pdf")
    events = []
    bus.subscribe(OcrCompleted, events.append)
    assert run_job(job_id) == JobOutcome.COMPLETED
    assert fake_engine.calls == 0 and events == [OcrCompleted(doc_id, job_id)]
    db.rollback()
    db.expire_all()
    job = db.get(ProcessingJob, job_id)
    assert job.status == "completed" and job.progress == 100 and job.result["text_layer_pages"] == 2
    pages = db.scalars(select(DocumentPage).where(DocumentPage.document_id == doc_id)).all()
    assert [p.ocr_status for p in pages] == ["completed", "completed"]
    r = db.scalar(select(OcrResult).where(OcrResult.page_id == pages[0].id))
    assert r.engine_version.startswith("pymupdf ") and r.confidence is None and r.boxes


def test_image_ocr_confidence_and_needs_review(seed, login, db, fake_engine):
    doc_id, job_id = _upload(seed, login, make_png(), "a.png")
    run_job(job_id)
    db.rollback()
    db.expire_all()
    page = db.scalar(select(DocumentPage).where(DocumentPage.document_id == doc_id))
    r = db.scalar(select(OcrResult).where(OcrResult.page_id == page.id))
    assert float(r.confidence) == 85.0 and r.engine_version == "fake 1.0" and page.ocr_status == "completed"
    fake_engine.lines = [OcrLine("mờ", 0.4, (0, 0, 5, 5))]
    doc2, job2 = _upload(seed, login, make_png(), "b.png")
    run_job(job2)
    db.rollback()
    db.expire_all()
    assert db.scalar(select(DocumentPage).where(DocumentPage.document_id == doc2)).ocr_status == "needs_review"


def test_job_api_and_retry_no_duplicates(seed, login, db, fake_engine, enqueued):
    doc_id, job_id = _upload(seed, login, make_png(), "a.png")
    c = login("officer")
    assert c.get(f"/api/jobs/{job_id}").json()["status"] == "queued"
    run_job(job_id)
    body = c.get(f"/api/jobs/{job_id}").json()
    assert body["status"] == "completed" and body["progress"] == 100 and body["kind"] == "OCR"
    assert c.post(f"/api/jobs/{job_id}/retry").status_code == 409  # chỉ retry job failed
    job = db.get(ProcessingJob, job_id)
    job.status = "failed"
    db.commit()
    resp = c.post(f"/api/jobs/{job_id}/retry")
    assert resp.status_code == 200 and resp.json()["status"] == "queued"
    run_job(job_id)
    n = db.scalar(select(func.count(OcrResult.id)).join(DocumentPage).where(DocumentPage.document_id == doc_id))
    assert n == 1
    assert login("officerb").get(f"/api/jobs/{job_id}").status_code == 403


def test_engine_unavailable_retries_then_fails(seed, login, db):
    def broken():
        raise RuntimeError("DLL bị chặn")

    _, job_id = _upload(seed, login, make_png(), "a.png")
    engines.register_engine("print", broken)  # sau upload: make_app() gọi registry.activate() đặt lại factory
    assert [run_job(job_id) for _ in range(3)] == [JobOutcome.RETRY, JobOutcome.RETRY, JobOutcome.FAILED]
    db.rollback()
    db.expire_all()
    job = db.get(ProcessingJob, job_id)
    assert job.error_code == "OCR_ENGINE_UNAVAILABLE" and job.attempt == 3
    body = login("officer").get(f"/api/jobs/{job_id}").json()
    assert "DLL" not in body["error_message"]


def test_page_errors_fail_job(seed, login, db, fake_engine):
    fake_engine.error = RuntimeError("lỗi nhận dạng")
    doc_id, job_id = _upload(seed, login, make_png(), "a.png")
    assert run_job(job_id) == JobOutcome.FAILED
    db.rollback()
    db.expire_all()
    assert db.get(ProcessingJob, job_id).error_code == "OCR_ALL_PAGES_FAILED"


def test_deleted_document_and_duplicate_delivery(seed, login, db, fake_engine):
    doc_id, job_id = _upload(seed, login, make_png(), "a.png")
    assert run_job(job_id) == JobOutcome.COMPLETED
    assert run_job(job_id) == JobOutcome.SKIPPED  # broker giao trùng
    doc2, job2 = _upload(seed, login, make_png(), "b.png")
    from app.modules.documents.infrastructure.models import Document

    db.get(Document, doc2).lifecycle_status = "deleted"
    db.commit()
    assert run_job(job2) == JobOutcome.FAILED
    db.rollback()
    db.expire_all()
    assert db.get(ProcessingJob, job2).error_code == "DOCUMENT_DELETED"


def test_stale_processing_job_reclaimed(seed, login, db, fake_engine):
    _, job_id = _upload(seed, login, make_png(), "a.png")
    job = db.get(ProcessingJob, job_id)
    job.status, job.attempt, job.started_at = "processing", 1, utcnow() - timedelta(hours=2)
    db.commit()
    assert run_job(job_id) == JobOutcome.COMPLETED
    db.rollback()
    db.expire_all()
    assert db.get(ProcessingJob, job_id).attempt == 2


def test_no_parallel_ocr_job_for_same_document(seed, login, db):
    from app.modules.jobs.application.create import create_ocr_job
    from app.shared.errors import ConflictError

    doc_id, _ = _upload(seed, login, make_png(), "a.png")
    try:
        create_ocr_job(db, doc_id)
    except ConflictError as exc:
        assert exc.code == "JOB_ALREADY_ACTIVE"
    else:
        raise AssertionError("phải từ chối job trùng")


def test_requeue_stuck_jobs(seed, login, db, enqueued):
    from app.modules.jobs.application.queries import requeue_stuck_jobs

    _, job_id = _upload(seed, login, make_png(), "a.png")
    enqueued.clear()
    job = db.get(ProcessingJob, job_id)
    job.queued_at = utcnow() - timedelta(hours=1)
    db.commit()
    assert requeue_stuck_jobs() == 1 and enqueued == [(job_id, "ocr")]


def test_requeue_reclaims_processing_job_of_dead_worker(seed, login, db, enqueued, fake_engine):
    # Worker chết hẳn: job processing quá JOB_STALE_SECONDS được beat gửi lại; claim nhận lại và chạy xong
    from app.modules.jobs.application.queries import requeue_stuck_jobs

    _, job_id = _upload(seed, login, make_png(), "a.png")
    job = db.get(ProcessingJob, job_id)
    job.status = JobStatus.PROCESSING
    job.attempt = 1
    job.worker_id = "chet:1"
    job.started_at = utcnow() - timedelta(seconds=settings.JOB_STALE_SECONDS + 60)
    db.commit()
    enqueued.clear()
    assert requeue_stuck_jobs() == 1 and enqueued == [(job_id, "ocr")]
    assert run_job(job_id, worker_id="moi:2") == JobOutcome.COMPLETED
    db.rollback()
    db.expire_all()
    assert db.get(ProcessingJob, job_id).attempt == 2


def test_requeue_skips_processing_job_still_running(seed, login, db, enqueued):
    from app.modules.jobs.application.queries import requeue_stuck_jobs

    _, job_id = _upload(seed, login, make_png(), "a.png")
    job = db.get(ProcessingJob, job_id)
    job.status = JobStatus.PROCESSING
    job.started_at = utcnow()
    db.commit()
    enqueued.clear()
    assert requeue_stuck_jobs() == 0 and enqueued == []


def test_worker_restart_releases_only_its_own_orphaned_jobs(seed, login, db, enqueued):
    # Container worker bị kill rồi khởi động lại (cùng hostname): job dở của nó quay về hàng đợi ngay
    from app.modules.jobs.application.queries import release_orphaned_jobs

    _, mine = _upload(seed, login, make_png(), "a.png")
    _, other = _upload(seed, login, make_png(), "b.png")
    for jid, wid in ((mine, "worker-a:7"), (other, "worker-b:7")):
        job = db.get(ProcessingJob, jid)
        job.status = JobStatus.PROCESSING
        job.worker_id = wid
        job.started_at = utcnow()
    db.commit()
    enqueued.clear()
    assert release_orphaned_jobs("worker-a") == 1
    assert enqueued == [(mine, "ocr")]
    db.rollback()
    db.expire_all()
    assert db.get(ProcessingJob, mine).status == JobStatus.QUEUED
    assert db.get(ProcessingJob, other).status == JobStatus.PROCESSING
