"""FR-17 (SDD v0.13): định nghĩa chỉ số thống kê và gom theo kỳ (Python thuần)."""

from collections.abc import Iterable
from datetime import date, timedelta

# Chỉ số -> các audit action được đếm (một dòng audit = 1)
ACTION_METRICS: dict[str, tuple[str, ...]] = {
    "uploads": ("upload_document", "import_document"),
    "ocr_edits": ("edit_ocr",),
    "submits": ("approval_submit",),
    "approvals": ("approval_approve",),
    "rejections": ("approval_reject",),
    "publishes": ("approval_publish",),
    "borrow_requests": ("create_borrow_request",),
    "downloads": ("download_document",),
}
# Chỉ số tính riêng
PAGES = "pages_uploaded"  # tổng state_after.pages của uploads
JOBS_DONE, JOBS_FAILED = "jobs_completed", "jobs_failed"  # job OCR kết thúc trong ngày, theo chủ tài liệu
LEAD_SUM, LEAD_COUNT = "lead_hours_sum", "published_docs"  # giờ từ tải lên đến xuất bản, theo chủ tài liệu

METRICS: tuple[str, ...] = (*ACTION_METRICS, PAGES, JOBS_DONE, JOBS_FAILED, LEAD_SUM, LEAD_COUNT)
LABELS = {
    "uploads": "Tài liệu tải lên",
    "pages_uploaded": "Trang tải lên",
    "ocr_edits": "Lần sửa OCR",
    "submits": "Gửi duyệt",
    "approvals": "Duyệt",
    "rejections": "Từ chối",
    "publishes": "Xuất bản",
    "borrow_requests": "Yêu cầu mượn",
    "downloads": "Lượt tải file",
    "jobs_completed": "Job OCR hoàn tất",
    "jobs_failed": "Job OCR lỗi",
    "published_docs": "Tài liệu được xuất bản",
    "lead_hours_sum": "Tổng giờ tải lên → xuất bản",
}
ACTION_TO_METRIC = {a: m for m, actions in ACTION_METRICS.items() for a in actions}
MAX_RANGE_DAYS = 366


def period_start(day: date, granularity: str) -> date:
    if granularity == "week":
        return day - timedelta(days=day.weekday())
    if granularity == "month":
        return day.replace(day=1)
    return day


def periods(start: date, end: date, granularity: str) -> list[date]:
    out: list[date] = []
    d = start
    while d <= end:
        p = period_start(d, granularity)
        if not out or out[-1] != p:
            out.append(p)
        d += timedelta(days=1)
    return out


def derived(values: dict[str, float]) -> dict[str, float | None]:
    """Chỉ số suy ra: tỉ lệ job lỗi (%), thời gian trung bình tải lên → xuất bản (giờ)."""
    done, failed = values.get(JOBS_DONE, 0), values.get(JOBS_FAILED, 0)
    count = values.get(LEAD_COUNT, 0)
    return {
        "job_failure_rate": round(100 * failed / (done + failed), 1) if done + failed else None,
        "avg_lead_hours": round(values.get(LEAD_SUM, 0) / count, 1) if count else None,
    }


def add(into: dict[str, float], rows: Iterable[tuple[str, float]]) -> None:
    for metric, value in rows:
        into[metric] = into.get(metric, 0) + value
