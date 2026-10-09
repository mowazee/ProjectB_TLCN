"""UC-19 Highlight trên ảnh/file scan (P2-02). Dùng API công khai của documents và ocr."""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.documents.application import queries as documents
from app.modules.ocr.application.queries import get_effective_text, latest_result
from app.modules.search.domain import highlight
from app.shared.context import Principal


@dataclass
class PageHighlights:
    page_number: int
    width: int
    height: int
    boxes: list[highlight.HighlightBox]
    reason: str | None


def page_highlights(
    db: Session, principal: Principal, document_id: uuid.UUID, page_number: int, q: str
) -> PageHighlights:
    documents.ensure_can_view(db, principal, document_id)
    page = documents.get_page(db, document_id, page_number)
    result = latest_result(db, page.id)
    if result is None:
        return PageHighlights(page.page_number, page.width, page.height, [], highlight.NO_OCR)
    boxes, reason = highlight.compute(
        q,
        list(result.boxes or []),
        effective_text=get_effective_text(db, page.id),
        raw_text=result.raw_text,
    )
    return PageHighlights(page.page_number, page.width, page.height, boxes, reason)
