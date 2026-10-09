"""UC-07 Dashboard (FR-08): số liệu trong phạm vi quyền, 0 khi rỗng.

avg_confidence là "điểm tin cậy trung bình (confidence)" do model tự đánh giá, KHÔNG gọi là
độ chính xác/accuracy (độ chính xác chỉ lấy từ báo cáo CER/WER, NFR-08).
Module P2 thêm số liệu qua register_contributor (vd. tài liệu chờ duyệt, yêu cầu mượn đang mở).
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.modules.categories.application.manage import names as category_names
from app.modules.documents.application.queries import dashboard_counts, visible_document_ids
from app.modules.jobs.application.queries import latest_status_subquery, status_counts
from app.modules.ocr.application.queries import avg_confidence_for_documents
from app.shared.context import Principal

Contributor = Callable[[Session, Principal], dict[str, int]]
_contributors: list[Contributor] = []

JOB_STATUSES = ("queued", "processing", "completed", "failed")


def register_contributor(fn: Contributor) -> None:
    if fn not in _contributors:
        _contributors.append(fn)


def reset() -> None:
    _contributors.clear()


def get_stats(db: Session, principal: Principal) -> dict[str, Any]:
    from sqlalchemy import func, select

    counts = dashboard_counts(db, principal)
    ids = visible_document_ids(principal)
    jobs = status_counts(db, ids)
    latest = latest_status_subquery()
    by_job = {
        str(s): n
        for s, n in db.execute(
            select(latest.c.status, func.count()).where(latest.c.document_id.in_(ids)).group_by(latest.c.status)
        ).all()
    }
    pages = counts["pages_by_status"]
    cats = category_names(db, set(counts["by_category"]))
    extras: dict[str, int] = {}
    for fn in _contributors:
        extras.update(fn(db, principal))
    return {
        "documents": counts["documents"],
        "pages": sum(pages.values()),
        "pages_ocr_done": pages.get("completed", 0) + pages.get("needs_review", 0),
        "pages_needs_review": pages.get("needs_review", 0),
        "documents_needs_review": counts["documents_needs_review"],
        "jobs_completed": jobs.get("completed", 0),
        "jobs_failed": jobs.get("failed", 0),
        "jobs_in_progress": jobs.get("queued", 0) + jobs.get("processing", 0),
        "avg_confidence": avg_confidence_for_documents(db, ids),
        "by_category": [
            {"label": cats.get(cid, str(cid)), "count": n}
            for cid, n in sorted(counts["by_category"].items(), key=lambda x: -x[1])
        ],
        "by_job_status": [{"label": s, "count": by_job.get(s, 0)} for s in JOB_STATUSES],
        "extras": extras,
    }
