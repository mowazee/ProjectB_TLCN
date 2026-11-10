"""API thống kê (SDD v0.13 mục 7.1, FR-17) - chỉ Admin:
GET /api/admin/analytics?from=&to=&department_id=&user_id=&granularity=day|week|month
GET /api/admin/analytics/export.csv   cùng bộ lọc; ghi audit export_analytics
"""

import uuid
from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.modules.analytics.application import stats
from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_roles

router = APIRouter(prefix="/api/admin/analytics", tags=["analytics"], dependencies=[Depends(require_roles("ADMIN"))])

Granularity = Literal["day", "week", "month"]


class AnalyticsOut(BaseModel):
    granularity: str
    date_from: date
    date_to: date
    series: list[dict[str, Any]]
    by_user: list[dict[str, Any]]
    by_department: list[dict[str, Any]]
    totals: dict[str, Any]


def _filters(
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    granularity: Granularity = "day",
    department_id: int | None = None,
    user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    end = date_to or stats.today()
    return {
        "date_from": date_from or end - timedelta(days=29),
        "date_to": end,
        "granularity": granularity,
        "department_id": department_id,
        "user_id": user_id,
    }


@router.get("", response_model=AnalyticsOut)
def get_analytics(
    db: DbSession, principal: CurrentPrincipal, filters: Annotated[dict[str, Any], Depends(_filters)]
) -> AnalyticsOut:
    return AnalyticsOut(**stats.query(db, principal, **filters).__dict__)


@router.get("/export.csv", response_class=Response)
def export_analytics(
    db: DbSession, principal: CurrentPrincipal, ctx: Ctx, filters: Annotated[dict[str, Any], Depends(_filters)]
) -> Response:
    body = stats.export_csv(db, principal, ctx, **filters)
    name = f"thong-ke_{filters['date_from']}_{filters['date_to']}.csv"
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
