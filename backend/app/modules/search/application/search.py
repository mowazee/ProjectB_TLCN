"""UC-04 Tìm kiếm (FR-06): trên text hiệu lực, trong visible_document_ids(user), nhóm theo tài liệu.

Từ v0.13 tìm theo nội dung khớp cả tên tài liệu (không phân biệt hoa thường, dấu): tài liệu chỉ khớp tên
có pages rỗng và title_match; tài liệu khớp cả tên lẫn nội dung xếp trước.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.documents.application.queries import document_brief, document_titles, visible_document_ids
from app.modules.jobs.application.queries import latest_status_subquery
from app.modules.search.domain.normalize import fold, nfc, normalize_query
from app.modules.search.infrastructure.tables import document_pages, ocr_corrections, ocr_results
from app.shared.context import Principal
from app.shared.db import is_postgres
from app.shared.pagination import PageParams

MAX_PAGE_HITS = 1000
SNIPPET_RADIUS = 80


@dataclass
class PageHit:
    page_number: int
    snippet: str
    match_start: int
    match_end: int


@dataclass
class DocumentHit:
    document_id: uuid.UUID
    title: str
    category_id: int
    pages: list[PageHit] = field(default_factory=list)
    title_match: bool = False


def _snippet(page_number: int, text: str, nq: str) -> PageHit:
    text = nfc(text)
    idx = fold(text).find(nq)
    if idx < 0:  # khớp theo từ (tsvector) nhưng khác khoảng trắng/dấu câu
        return PageHit(page_number, text[: SNIPPET_RADIUS * 2].replace("\n", " "), 0, 0)
    start = max(0, idx - SNIPPET_RADIUS)
    end = min(len(text), idx + len(nq) + SNIPPET_RADIUS)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    body = text[start:end].replace("\n", " ").replace("\r", " ")
    ms = len(prefix) + (idx - start)
    return PageHit(page_number, f"{prefix}{body}{suffix}", ms, ms + len(nq))


def search(
    db: Session,
    principal: Principal,
    q: str,
    params: PageParams,
    *,
    category_id: int | None = None,
    status: str | None = None,
) -> tuple[list[DocumentHit], int]:
    nq = normalize_query(q)
    if not nq:
        return [], 0
    match = (
        ocr_results.c.search_vector.op("@@")(func.phraseto_tsquery("simple", nq))
        if is_postgres(db)
        else ocr_results.c.search_vector.contains(nq, autoescape=True)
    )
    allowed = visible_document_ids(principal, category_id=category_id)
    if status:
        latest = latest_status_subquery()
        allowed = allowed.where(
            allowed.selected_columns[0].in_(select(latest.c.document_id).where(latest.c.status == status))
        )
    rows = db.execute(
        select(ocr_results.c.raw_text, document_pages.c.id, document_pages.c.document_id, document_pages.c.page_number)
        .join(document_pages, ocr_results.c.page_id == document_pages.c.id)
        .where(ocr_results.c.search_vector.is_not(None), match, document_pages.c.document_id.in_(allowed))
        .order_by(document_pages.c.document_id, document_pages.c.page_number)
        .limit(MAX_PAGE_HITS)
    ).all()

    # text hiệu lực: bản chỉnh sửa mới nhất của các trang khớp (một truy vấn)
    page_ids = [r[1] for r in rows]
    corrected: dict[uuid.UUID, str] = {}
    if page_ids:
        newest = (
            select(ocr_corrections.c.page_id, func.max(ocr_corrections.c.version).label("v"))
            .where(ocr_corrections.c.page_id.in_(page_ids))
            .group_by(ocr_corrections.c.page_id)
            .subquery()
        )
        for pid, text in db.execute(
            select(ocr_corrections.c.page_id, ocr_corrections.c.corrected_text).join(
                newest, (newest.c.page_id == ocr_corrections.c.page_id) & (newest.c.v == ocr_corrections.c.version)
            )
        ).all():
            corrected[pid] = text

    title_ids = {doc_id for doc_id, title in document_titles(db, allowed) if nq in fold(nfc(title or ""))}
    briefs = document_brief(db, {r[2] for r in rows} | title_ids)
    groups: dict[uuid.UUID, DocumentHit] = {}
    for raw_text, page_id, doc_id, page_number in rows:
        hit = groups.get(doc_id)
        if hit is None:
            b = briefs.get(doc_id, {})
            hit = DocumentHit(doc_id, b.get("title", ""), b.get("category_id", 0))
            groups[doc_id] = hit
        hit.pages.append(_snippet(page_number, corrected.get(page_id, raw_text), nq))
    for doc_id in title_ids:
        if doc_id not in groups:
            b = briefs.get(doc_id, {})
            groups[doc_id] = DocumentHit(doc_id, b.get("title", ""), b.get("category_id", 0))
        groups[doc_id].title_match = True

    def rank(h: DocumentHit) -> tuple[int, str]:
        both = h.title_match and bool(h.pages)
        return (1 if both else 0, briefs.get(h.document_id, {}).get("created_at") or "")

    ordered = sorted(groups.values(), key=rank, reverse=True)
    return ordered[params.offset : params.offset + params.page_size], len(ordered)
