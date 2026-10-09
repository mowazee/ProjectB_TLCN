"""P2-03 OCR chữ viết tay (UC-20): profile handwriting -> hàng đợi ocr_hw; reprocess; cô lập lỗi."""

from uuid import UUID

from sqlalchemy import select

from app.modules.jobs.application.runner import run_job
from app.modules.jobs.domain.model import JobOutcome
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.modules.ocr.application import engines
from app.modules.ocr.infrastructure.models import OcrResult
from tests.conftest import FakeEngine, make_pdf, make_png, run_all_jobs, upload

F = "handwriting"


class HwEngine(FakeEngine):
    name, version = "hw-fake", "0.1"


def test_handwritten_upload_goes_to_hw_queue(seed, login, db, enqueued):
    c = login("officer", features=F)
    hw = HwEngine()
    engines.override("handwriting", hw)
    body = upload(c, seed["category"].id, make_pdf(["Chu viet tay co lop chu"]), "a.pdf", is_handwritten="true").json()
    assert enqueued == [(UUID(body["job_id"]), "ocr_hw")]
    run_all_jobs(enqueued)
    db.rollback()
    job = db.get(ProcessingJob, UUID(body["job_id"]))
    assert job.payload == {"profile": "handwriting"} and job.status == "completed"
    assert hw.calls == 1  # chữ viết tay: luôn OCR ảnh, không dùng lớp chữ PDF
    r = db.scalar(select(OcrResult).where(OcrResult.job_id == job.id))
    assert r.engine_version == "hw-fake 0.1"
    assert c.get(f"/api/documents/{body['document_id']}").json()["is_handwritten"] is True


def test_flag_off_uses_print_and_hides_endpoint(seed, login, enqueued):
    c = login("officer", features="")
    body = upload(c, seed["category"].id, make_png(), "a.png", is_handwritten="true").json()
    assert enqueued == [(UUID(body["job_id"]), "ocr")]
    assert c.post(f"/api/documents/{body['document_id']}/reprocess", json={}).status_code == 404


def test_reprocess(seed, login, db, fake_engine, enqueued):
    c = login("officer", features=F)
    doc_id = upload(c, seed["category"].id, make_png(), "a.png").json()["document_id"]
    busy = c.post(f"/api/documents/{doc_id}/reprocess", json={"ocr_profile": "handwriting"})
    assert busy.status_code == 409 and busy.json()["error"]["code"] == "JOB_ALREADY_ACTIVE"
    run_all_jobs(enqueued)
    r = c.post(f"/api/documents/{doc_id}/reprocess", json={"ocr_profile": "handwriting"})
    assert r.status_code == 202 and r.json()["queue"] == "ocr_hw"
    assert c.post(f"/api/documents/{doc_id}/reprocess", json={"ocr_profile": "abc"}).status_code == 422
    assert login("approver", features=F).post(f"/api/documents/{doc_id}/reprocess", json={}).status_code == 403


def test_handwriting_model_failure_does_not_affect_print(seed, login, db, fake_engine, enqueued):
    c = login("officer", features=F)

    def broken():
        raise RuntimeError("model chữ viết tay lỗi")

    engines.register_engine("handwriting", broken)
    hw = upload(c, seed["category"].id, make_png(), "hw.png", is_handwritten="true").json()
    pr = upload(c, seed["category"].id, make_png(), "print.png").json()
    assert run_job(UUID(hw["job_id"])) == JobOutcome.RETRY
    assert run_job(UUID(pr["job_id"])) == JobOutcome.COMPLETED
