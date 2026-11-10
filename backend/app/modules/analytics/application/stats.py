"""UC-31 Xem thống kê hoạt động (FR-17, SDD v0.13).

- compute_day: đếm chỉ số của một ngày theo người dùng từ audit_logs, processing_jobs, documents.
- refresh_recent (Celery beat): ghi daily_activity_stats cho hôm qua và hôm kia (ghi đè), lần đầu tính lùi
  BACKFILL_DAYS ngày; nhờ vậy dọn audit log (FR-14) không làm mất thống kê.
- query: đọc bảng tổng hợp (hôm nay tính trực tiếp), lọc thời gian/phòng ban/người dùng, gom ngày/tuần/tháng.
Chỉ Admin (kiểm ở đây và ở router).
"""

import csv
import io
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.analytics.domain.metrics import (
    ACTION_TO_METRIC,
    JOBS_DONE,
    JOBS_FAILED,
    LABELS,
    LEAD_COUNT,
    LEAD_SUM,
    MAX_RANGE_DAYS,
    METRICS,
    PAGES,
    derived,
    period_start,
    periods,
)
from app.modules.analytics.infrastructure.models import (
    DailyActivityStat,
    audit_logs,
    documents,
    processing_jobs,
    users,
)
from app.modules.audit.application.recorder import record
from app.modules.users.application.queries import department_names, user_briefs
from app.shared.context import Principal, RequestContext
from app.shared.db import SessionLocal, aware
from app.shared.errors import PermissionDeniedError, UnprocessableError

BACKFILL_DAYS = 90
Row = tuple[uuid.UUID, int | None, str, float]  # user_id, department_id, metric, value


def _bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


def today() -> date:
    return datetime.now(UTC).date()


def compute_day(db: Session, day: date) -> list[Row]:
    start, end = _bounds(day)
    values: dict[tuple[uuid.UUID, str], float] = defaultdict(float)
    for user_id, action, after in db.execute(
        select(audit_logs.c.user_id, audit_logs.c.action, audit_logs.c.state_after).where(
            audit_logs.c.created_at >= start,
            audit_logs.c.created_at < end,
            audit_logs.c.user_id.is_not(None),
            audit_logs.c.action.in_(list(ACTION_TO_METRIC)),
        )
    ).all():
        metric = ACTION_TO_METRIC[action]
        values[(user_id, metric)] += 1
        if metric == "uploads" and isinstance(after, dict):
            values[(user_id, PAGES)] += float(after.get("pages") or 0)
    # Job OCR kết thúc trong ngày, tính cho chủ tài liệu
    for owner, status, n in db.execute(
        select(documents.c.owner_id, processing_jobs.c.status, func.count())
        .join(documents, documents.c.id == processing_jobs.c.document_id)
        .where(
            processing_jobs.c.kind == "OCR",
            processing_jobs.c.finished_at >= start,
            processing_jobs.c.finished_at < end,
            processing_jobs.c.status.in_(["completed", "failed"]),
            documents.c.owner_id.is_not(None),
        )
        .group_by(documents.c.owner_id, processing_jobs.c.status)
    ).all():
        values[(owner, JOBS_DONE if status == "completed" else JOBS_FAILED)] += n
    # Thời gian từ tải lên đến xuất bản, tính cho chủ tài liệu
    for owner, published_at, created_at in db.execute(
        select(documents.c.owner_id, audit_logs.c.created_at, documents.c.created_at)
        .join(documents, documents.c.id == audit_logs.c.document_id)
        .where(
            audit_logs.c.action == "approval_publish",
            audit_logs.c.created_at >= start,
            audit_logs.c.created_at < end,
            documents.c.owner_id.is_not(None),
        )
    ).all():
        pub, made = aware(published_at), aware(created_at)
        if pub is None or made is None:
            continue
        hours = (pub - made).total_seconds() / 3600
        values[(owner, LEAD_SUM)] += max(hours, 0)
        values[(owner, LEAD_COUNT)] += 1
    if not values:
        return []
    ids = {u for u, _ in values}
    deps: dict[uuid.UUID, int | None] = {
        r[0]: r[1] for r in db.execute(select(users.c.id, users.c.department_id).where(users.c.id.in_(ids))).all()
    }
    return [(u, deps.get(u), m, v) for (u, m), v in values.items() if u in deps]


def store_day(db: Session, day: date) -> int:
    rows = compute_day(db, day)
    db.execute(delete(DailyActivityStat).where(DailyActivityStat.day == day))
    db.add_all(DailyActivityStat(day=day, user_id=u, department_id=d, metric=m, value=v) for u, d, m, v in rows)
    return len(rows)


def refresh_recent() -> int:
    """Celery beat: tính lại hôm qua, hôm kia; lần đầu (bảng rỗng) tính lùi BACKFILL_DAYS ngày."""
    with SessionLocal() as db:
        empty = db.scalar(select(func.count()).select_from(DailyActivityStat)) == 0
        days = BACKFILL_DAYS if empty else 2
        n = sum(store_day(db, today() - timedelta(days=k)) for k in range(1, days + 1))
        db.commit()
        return n


@dataclass
class Analytics:
    granularity: str
    date_from: date
    date_to: date
    series: list[dict[str, Any]] = field(default_factory=list)
    by_user: list[dict[str, Any]] = field(default_factory=list)
    by_department: list[dict[str, Any]] = field(default_factory=list)
    totals: dict[str, Any] = field(default_factory=dict)


def _require_admin(actor: Principal) -> None:
    if not actor.is_admin:
        raise PermissionDeniedError("Chỉ Quản trị viên được xem thống kê")


def _rows(
    db: Session, date_from: date, date_to: date, department_id: int | None, user_id: uuid.UUID | None
) -> list[tuple[date, Row]]:
    out: list[tuple[date, Row]] = []
    stmt = select(
        DailyActivityStat.day,
        DailyActivityStat.user_id,
        DailyActivityStat.department_id,
        DailyActivityStat.metric,
        DailyActivityStat.value,
    ).where(DailyActivityStat.day >= date_from, DailyActivityStat.day <= min(date_to, today() - timedelta(days=1)))
    for day, u, d, m, v in db.execute(stmt).all():
        out.append((day, (u, d, m, float(v))))
    if date_to >= today() >= date_from:  # hôm nay chưa tổng hợp: tính trực tiếp
        out.extend((today(), r) for r in compute_day(db, today()))
    return [
        (day, r)
        for day, r in out
        if (department_id is None or r[1] == department_id) and (user_id is None or r[0] == user_id)
    ]


def _metrics(values: dict[str, float]) -> dict[str, Any]:
    base: dict[str, Any] = {m: round(values.get(m, 0), 1) for m in METRICS}
    return {**base, **derived(values)}


def query(
    db: Session,
    actor: Principal,
    *,
    date_from: date,
    date_to: date,
    granularity: str = "day",
    department_id: int | None = None,
    user_id: uuid.UUID | None = None,
) -> Analytics:
    _require_admin(actor)
    if date_from > date_to:
        raise UnprocessableError("Ngày bắt đầu phải trước ngày kết thúc", fields={"to": "before_from"})
    if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
        raise UnprocessableError(f"Khoảng thời gian tối đa {MAX_RANGE_DAYS} ngày", fields={"to": "range_too_long"})
    rows = _rows(db, date_from, date_to, department_id, user_id)
    by_period: dict[date, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_user: dict[uuid.UUID, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_dep: dict[int | None, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    totals: dict[str, float] = defaultdict(float)
    user_dep: dict[uuid.UUID, int | None] = {}
    for day, (u, d, m, v) in rows:
        by_period[period_start(day, granularity)][m] += v
        by_user[u][m] += v
        by_dep[d][m] += v
        totals[m] += v
        user_dep[u] = d
    briefs = user_briefs(db, set(by_user))
    deps = department_names(db, {d for d in by_dep if d is not None})
    result = Analytics(granularity, date_from, date_to, totals=_metrics(totals))
    result.series = [
        {"period": p.isoformat(), **_metrics(by_period.get(p, {}))} for p in periods(date_from, date_to, granularity)
    ]
    result.by_user = sorted(
        (
            {
                "user_id": str(u),
                "username": briefs[u].username if u in briefs else None,
                "full_name": briefs[u].full_name if u in briefs else None,
                "department_id": user_dep.get(u),
                "department_name": deps.get(user_dep.get(u) or -1),
                **_metrics(vals),
            }
            for u, vals in by_user.items()
        ),
        key=lambda r: (-r["uploads"], r["username"] or ""),
    )
    result.by_department = sorted(
        (
            {"department_id": d, "department_name": deps.get(d) if d is not None else None, **_metrics(vals)}
            for d, vals in by_dep.items()
        ),
        key=lambda r: -r["uploads"],
    )
    return result


CSV_COLUMNS = ("full_name", "username", "department_name", *METRICS, "job_failure_rate", "avg_lead_hours")


def export_csv(db: Session, actor: Principal, ctx: RequestContext, **filters: Any) -> str:
    data = query(db, actor, **filters)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([LABELS.get(c, c) for c in CSV_COLUMNS])
    for r in data.by_user:
        writer.writerow([r.get(c, "") if r.get(c) is not None else "" for c in CSV_COLUMNS])
    record(
        db,
        action="export_analytics",
        module="analytics",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="analytics",
        entity_id=None,
        after={k: (str(v) if v is not None else None) for k, v in filters.items()},
    )
    db.commit()
    return "﻿" + buf.getvalue()  # BOM để Excel đọc đúng tiếng Việt
