"""SDD v0.7 FR-11 (hàng đợi xử lý: phạm vi, lọc, đánh dấu job chờ quá lâu) và FR-07 (lọc trạng thái duyệt)."""

from datetime import timedelta
from uuid import UUID

from app.modules.jobs.application.create import create_job
from app.modules.jobs.application.queries import requeue_stuck_jobs
from app.modules.jobs.domain.model import JobStatus
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.shared.config import settings
from app.shared.db import utcnow
from tests.conftest import make_png, run_all_jobs, upload

WF = "workflow"


def _doc(client, seed, title):
    body = upload(client, seed["category"].id, make_png(), f"{title}.png", title=title).json()
    return UUID(body["document_id"]), UUID(body["job_id"])


def _batch_job(db, owner):
    job = create_job(db, kind="BULK_IMPORT", document_id=None, payload={"user_id": str(owner.id), "files": []})
    db.commit()
    return job.id


def _ids(resp):
    assert resp.status_code == 200, resp.text
    return {UUID(j["id"]) for j in resp.json()["items"]}


def test_job_queue_scope_by_role(seed, login, db):
    officer, officer_b, admin = login("officer"), login("officerb"), login("admin")
    _, job_a = _doc(officer, seed, "Phong A")
    _, job_b = _doc(officer_b, seed, "Phong B")
    batch_a, batch_b = _batch_job(db, seed["officer"]), _batch_job(db, seed["officer_b"])

    assert _ids(officer.get("/api/jobs")) == {job_a, batch_a}  # phạm vi phòng ban + lô do mình tạo
    assert _ids(officer_b.get("/api/jobs")) == {job_b, batch_b}
    assert _ids(admin.get("/api/jobs")) == {job_a, job_b, batch_a, batch_b}
    item = next(j for j in officer.get("/api/jobs").json()["items"] if j["id"] == str(job_a))
    assert item["document_title"] == "Phong A" and item["queue_name"] == "ocr" and item["stale"] is False
    # FR-11: Kiểm duyệt viên không xem hàng đợi (SDD mục 3)
    assert login("approver").get("/api/jobs").status_code == 403


def test_job_queue_filters_and_pagination(seed, login, db, enqueued, fake_engine):
    officer = login("officer")
    _, done = _doc(officer, seed, "Xong")
    run_all_jobs(enqueued)
    _, waiting = _doc(officer, seed, "Cho")
    _batch_job(db, seed["officer"])

    # kind=OCR: khi bật cờ P2, OCR xong còn sinh job EXTRACT/CLASSIFY
    assert _ids(officer.get("/api/jobs", params={"status": "completed", "kind": "OCR"})) == {done}
    assert _ids(officer.get("/api/jobs", params={"status": "queued", "kind": "OCR"})) == {waiting}
    assert officer.get("/api/jobs", params={"kind": "BULK_IMPORT"}).json()["total"] == 1
    page = officer.get("/api/jobs", params={"kind": "OCR", "page_size": 1}).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    assert officer.get("/api/jobs", params={"status": "khong-hop-le"}).status_code == 422


def test_job_queue_marks_stale_jobs_even_after_beat_requeue(seed, login, db, enqueued):
    officer = login("officer")
    _, job_id = _doc(officer, seed, "Ket")

    def stale():
        return next(j["stale"] for j in officer.get("/api/jobs").json()["items"] if j["id"] == str(job_id))

    assert stale() is False
    job = db.get(ProcessingJob, job_id)
    job.queued_at = utcnow() - timedelta(seconds=settings.JOB_REQUEUE_AFTER_SECONDS + 60)
    db.commit()
    assert stale() is True
    # Beat gửi lại và đặt queued_at = now: job vẫn phải được đánh dấu (vd. chưa bật worker chữ viết tay)
    assert requeue_stuck_jobs() == 1
    assert stale() is True

    # Processing quá JOB_STALE_SECONDS: worker có thể đã chết
    db.expire_all()
    job = db.get(ProcessingJob, job_id)
    job.status = JobStatus.PROCESSING
    job.started_at = utcnow() - timedelta(seconds=settings.JOB_STALE_SECONDS + 60)
    db.commit()
    assert stale() is True


def test_retry_clears_requeue_marker(seed, login, db, enqueued):
    officer = login("officer")
    _, job_id = _doc(officer, seed, "Loi")
    job = db.get(ProcessingJob, job_id)
    job.status = JobStatus.FAILED
    job.payload = {**(job.payload or {}), "requeue_count": 3}
    db.commit()
    assert officer.post(f"/api/jobs/{job_id}/retry").status_code == 200
    db.expire_all()
    job = db.get(ProcessingJob, job_id)
    assert "requeue_count" not in job.payload and job.payload.get("profile") == "print"
    item = next(j for j in officer.get("/api/jobs").json()["items"] if j["id"] == str(job_id))
    assert item["status"] == "queued" and item["stale"] is False


def test_document_list_filters_by_approval_status(seed, login):
    officer, approver = login("officer", features=WF), login("approver", features=WF)
    draft, _ = _doc(officer, seed, "Nhap")
    sent, _ = _doc(officer, seed, "Gui")
    assert officer.post(f"/api/documents/{sent}/approval/submit").status_code == 200

    def ids(status):
        resp = officer.get("/api/documents", params={"approval_status": status})
        assert resp.status_code == 200, resp.text
        return {UUID(d["id"]) for d in resp.json()["items"]}

    assert ids("pending_review") == {sent}
    assert ids("draft") == {draft}
    assert ids("published") == set()
    assert approver.get("/api/documents", params={"approval_status": "pending_review"}).json()["total"] == 1
    assert officer.get("/api/documents", params={"approval_status": "sai"}).status_code == 422
