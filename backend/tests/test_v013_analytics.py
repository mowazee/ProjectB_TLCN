"""FR-17 (SDD v0.13): thống kê hoạt động theo người dùng/phòng ban; chỉ Admin; bảng tổng hợp không mất khi dọn audit."""

from datetime import timedelta

from sqlalchemy import delete, select

from app.modules.analytics.application import stats
from app.modules.analytics.infrastructure.models import DailyActivityStat
from app.modules.audit.infrastructure.models import AuditLog
from app.shared.db import utcnow
from tests.conftest import make_pdf, run_all_jobs, upload


def _activity(seed, login, enqueued):
    officer = login("officer")
    for i in range(2):
        upload(officer, seed["category"].id, make_pdf(["a"], pages=2), f"{i}.pdf")
    upload(login("officerb"), seed["category"].id, make_pdf(["b"]), "b.pdf")
    run_all_jobs(enqueued)


def test_admin_only_and_range_validation(seed, login):
    assert login("officer").get("/api/admin/analytics").status_code == 403
    admin = login("admin")
    assert admin.get("/api/admin/analytics", params={"from": "2026-01-01", "to": "2027-03-01"}).status_code == 422
    assert admin.get("/api/admin/analytics", params={"from": "2026-05-02", "to": "2026-05-01"}).status_code == 422
    empty = admin.get("/api/admin/analytics", params={"from": "2020-01-01", "to": "2020-01-31"}).json()
    assert empty["totals"]["uploads"] == 0 and len(empty["series"]) == 31


def test_today_counts_by_user_and_department(seed, login, fake_engine, enqueued):
    _activity(seed, login, enqueued)
    admin = login("admin")
    data = admin.get("/api/admin/analytics").json()
    assert data["totals"]["uploads"] == 3 and data["totals"]["pages_uploaded"] == 5
    assert data["totals"]["jobs_completed"] == 3 and data["totals"]["job_failure_rate"] == 0
    users = {u["username"]: u for u in data["by_user"]}
    assert users["officer"]["uploads"] == 2 and users["officerb"]["uploads"] == 1
    assert sum(d["uploads"] for d in data["by_department"]) == 3
    dep_a = users["officer"]["department_id"]
    only_a = admin.get("/api/admin/analytics", params={"department_id": dep_a}).json()
    assert only_a["totals"]["uploads"] == 2
    weekly = admin.get("/api/admin/analytics", params={"granularity": "month"}).json()
    assert sum(p["uploads"] for p in weekly["series"]) == 3


def test_daily_table_survives_audit_purge_and_csv_is_audited(seed, login, fake_engine, enqueued, db):
    _activity(seed, login, enqueued)
    yesterday = stats.today() - timedelta(days=1)
    db.execute(AuditLog.__table__.update().values(created_at=utcnow() - timedelta(days=1)))
    db.commit()
    assert stats.refresh_recent() > 0
    db.execute(delete(AuditLog))  # dọn audit: thống kê vẫn còn trong bảng tổng hợp
    db.commit()
    assert db.scalar(select(DailyActivityStat.value).where(DailyActivityStat.metric == "uploads").limit(1))
    admin = login("admin")
    params = {"from": str(yesterday), "to": str(yesterday)}
    assert admin.get("/api/admin/analytics", params=params).json()["totals"]["uploads"] == 3
    csv = admin.get("/api/admin/analytics/export.csv", params=params)
    assert csv.status_code == 200 and "Tài liệu tải lên" in csv.text and "officer" in csv.text
    db.rollback()  # bắt đầu transaction mới để thấy dòng API vừa ghi
    assert db.scalar(select(AuditLog).where(AuditLog.action == "export_analytics")) is not None
