"""GET /api/dashboard (SDD mục 7.1): thống kê theo quyền."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.modules.auth.presentation.deps import CurrentPrincipal, DbSession
from app.modules.dashboard.application.stats import get_stats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class CountItem(BaseModel):
    label: str
    count: int


class DashboardOut(BaseModel):
    documents: int
    pages: int
    pages_ocr_done: int
    pages_needs_review: int
    documents_needs_review: int
    jobs_completed: int
    jobs_failed: int
    jobs_in_progress: int
    avg_confidence: float | None = Field(
        description="Điểm tin cậy trung bình (confidence) do model tự đánh giá, KHÔNG phải độ chính xác"
    )
    by_category: list[CountItem]
    by_job_status: list[CountItem] = Field(description="Số tài liệu theo trạng thái job OCR mới nhất")
    extras: dict[str, int] = Field(description="Số liệu của tính năng P2 đang bật")


@router.get("", response_model=DashboardOut)
def dashboard(db: DbSession, principal: CurrentPrincipal) -> DashboardOut:
    return DashboardOut(**get_stats(db, principal))
