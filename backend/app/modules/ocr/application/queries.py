"""API truy vấn công khai của ocr (Đặc tả đề tài v0.5 mục 4.3):
get_effective_text, get_page_boxes, kết quả mới nhất, phiên bản hiện hành."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ocr.infrastructure.models import OcrCorrection, OcrResult


def latest_result(db: Session, page_id: uuid.UUID) -> OcrResult | None:
    return db.scalar(
        select(OcrResult).where(OcrResult.page_id == page_id).order_by(OcrResult.created_at.desc()).limit(1)
    )


def current_correction(db: Session, page_id: uuid.UUID) -> OcrCorrection | None:
    return db.scalar(
        select(OcrCorrection).where(OcrCorrection.page_id == page_id).order_by(OcrCorrection.version.desc()).limit(1)
    )


def current_version(db: Session, page_id: uuid.UUID) -> int:
    c = current_correction(db, page_id)
    return c.version if c else 0


def get_effective_text(db: Session, page_id: uuid.UUID) -> str:
    """Text hiệu lực = bản chỉnh sửa mới nhất nếu có, ngược lại raw_text OCR mới nhất."""
    c = current_correction(db, page_id)
    if c is not None:
        return c.corrected_text
    r = latest_result(db, page_id)
    return r.raw_text if r else ""


def get_page_boxes(db: Session, page_id: uuid.UUID) -> list[dict[str, Any]]:
    r = latest_result(db, page_id)
    return list(r.boxes or []) if r else []


def list_corrections(db: Session, page_id: uuid.UUID) -> list[OcrCorrection]:
    return list(
        db.scalars(select(OcrCorrection).where(OcrCorrection.page_id == page_id).order_by(OcrCorrection.version)).all()
    )


def get_correction(db: Session, page_id: uuid.UUID, version: int) -> OcrCorrection | None:
    return db.scalar(select(OcrCorrection).where(OcrCorrection.page_id == page_id, OcrCorrection.version == version))


def document_effective_text(db: Session, page_ids: list[uuid.UUID]) -> str:
    return "\n\n".join(get_effective_text(db, pid) for pid in page_ids)


def avg_confidence_for_documents(db: Session, document_ids_select: Any) -> float | None:
    """Điểm tin cậy TB trên kết quả hiệu lực (search_vector khác NULL) của các tài liệu."""
    from sqlalchemy import Uuid, column, func, table

    pages = table("document_pages", column("id", Uuid), column("document_id", Uuid))
    avg = db.scalar(
        select(func.avg(OcrResult.confidence))
        .join(pages, pages.c.id == OcrResult.page_id)
        .where(OcrResult.search_vector.is_not(None), pages.c.document_id.in_(document_ids_select))
    )
    return round(float(avg), 2) if avg is not None else None


def confidence_avg(db: Session, page_ids: list[uuid.UUID]) -> float | None:
    vals = []
    for pid in page_ids:
        r = latest_result(db, pid)
        if r is not None and r.confidence is not None:
            vals.append(float(r.confidence))
    return round(sum(vals) / len(vals), 2) if vals else None
