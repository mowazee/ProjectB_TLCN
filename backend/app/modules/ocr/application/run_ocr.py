"""UC-02 Thực hiện OCR: handler cho job kind 'OCR' (đăng ký qua ModuleSpec.job_handlers).

Pipeline: file gốc -> PyMuPDF (text layer hoặc render) -> OpenCV tiền xử lý -> engine theo
profile (print | handwriting) -> document_pages + ocr_results -> chỉ mục text hiệu lực
-> OcrCompleted (phát sau commit). Lỗi một trang không làm hỏng cả tài liệu.
"""

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
import pymupdf
from sqlalchemy import select

from app.modules.documents.application import queries as documents
from app.modules.documents.domain.lifecycle import PageOcrStatus
from app.modules.jobs.domain.model import JobError
from app.modules.ocr.application import engines
from app.modules.ocr.application.queries import current_correction
from app.modules.ocr.domain.events import OcrCompleted
from app.modules.ocr.domain.ports import TEXT_LAYER_ENGINE, OcrLine, OcrOutput, needs_review
from app.modules.ocr.infrastructure import images, pdf
from app.modules.ocr.infrastructure.models import OcrResult
from app.modules.search.application.index import index_page
from app.shared.config import settings
from app.shared.db import utcnow
from app.shared.errors import StorageError
from app.shared.events import publish
from app.shared.storage import get_storage, page_image_key

logger = logging.getLogger(__name__)


@dataclass
class _PageInput:
    number: int
    png: bytes | None = None
    lines: list[pdf.TextLine] | None = None
    image_bgr: np.ndarray | None = None


def _page_inputs(doc: Any) -> tuple[int, Iterator[_PageInput]]:
    try:
        src = get_storage().path(doc.storage_key)
    except StorageError as exc:
        raise JobError("FILE_NOT_FOUND", str(exc)) from exc
    if doc.mime_type == "application/pdf":
        try:
            total = pdf.page_count(src)
        except Exception as exc:  # noqa: BLE001
            raise JobError("FILE_CORRUPT", str(exc)) from exc
        if total > settings.MAX_PAGES:
            raise JobError("TOO_MANY_PAGES", f"{total} trang")
        return total, (
            _PageInput(p.number, png=p.png, lines=p.lines) for p in pdf.render_pages(src, settings.OCR_RENDER_DPI)
        )
    try:
        image = images.load_image_bgr(src)
    except Exception as exc:  # noqa: BLE001
        raise JobError("FILE_CORRUPT", str(exc)) from exc
    return 1, iter([_PageInput(1, image_bgr=image)])


class _EngineHolder:
    """Chỉ khởi tạo engine khi thật sự có trang cần OCR (PDF text layer thì không)."""

    def __init__(self, profile: str) -> None:
        self.profile = profile
        self._engine: Any = None

    def get(self) -> Any:
        if self._engine is None:
            try:
                self._engine = engines.get_engine(self.profile)
            except Exception as exc:
                raise JobError("OCR_ENGINE_UNAVAILABLE", str(exc), retryable=True) from exc
        return self._engine


def _recognize(page_in: _PageInput, holder: _EngineHolder, use_text_layer: bool) -> tuple[bytes, int, int, OcrOutput]:
    if page_in.png is not None:
        chars = sum(len("".join(ln.text.split())) for ln in page_in.lines or [])
        if use_text_layer and chars >= settings.TEXT_LAYER_MIN_CHARS:
            bgr = images.png_to_bgr(page_in.png)
            h, w = bgr.shape[:2]
            out = OcrOutput(
                TEXT_LAYER_ENGINE, pymupdf.__version__, [OcrLine(ln.text, None, ln.box) for ln in page_in.lines or []]
            )
            return page_in.png, w, h, out
        source = images.png_to_bgr(page_in.png)
    elif page_in.image_bgr is not None:
        source = page_in.image_bgr
    else:
        raise ValueError("Trang không có dữ liệu ảnh")
    processed, _ = images.preprocess(source)
    h, w = processed.shape[:2]
    out = holder.get().recognize(processed)
    return images.encode_png(processed), w, h, out


def handle(ctx: Any) -> None:
    """ctx: jobs.application.runner.JobContext."""
    db, job = ctx.db, ctx.job
    doc = documents.get_document(db, job.document_id)
    if doc is None or not documents.is_active(db, job.document_id):
        raise JobError("DOCUMENT_DELETED", "Tài liệu đã bị xóa")
    profile = ctx.payload.get("profile", "print")
    holder = _EngineHolder(profile)
    use_text_layer = profile == "print"  # chữ viết tay: luôn OCR ảnh
    storage = get_storage()

    t0 = time.perf_counter()
    total, pages = _page_inputs(doc)
    failed: list[int] = []
    review: list[int] = []
    confidences: list[Decimal] = []
    text_layer = 0
    for page_in in pages:
        try:
            png, w, h, out = _recognize(page_in, holder, use_text_layer)
        except JobError:
            raise  # lỗi cấp job (engine không khởi tạo được) -> retry cả job
        except Exception:
            logger.exception("OCR lỗi ở trang %s", page_in.number)
            db.rollback()
            page = documents.upsert_page(db, doc.id, page_in.number, image_key="", width=0, height=0)
            documents.set_page_status(page, PageOcrStatus.FAILED)
            failed.append(page_in.number)
        else:
            key = page_image_key(doc.id, page_in.number)
            storage.save_bytes(key, png)
            page = documents.upsert_page(db, doc.id, page_in.number, image_key=key, width=w, height=h)
            result = db.scalar(select(OcrResult).where(OcrResult.page_id == page.id, OcrResult.job_id == job.id))
            if result is None:
                result = OcrResult(page_id=page.id, job_id=job.id)
                db.add(result)
            conf = None if out.is_text_layer else out.confidence
            result.raw_text = out.text
            result.boxes = out.boxes_json()
            result.confidence = conf
            result.engine_version = out.engine_label[:50]
            result.created_at = utcnow()
            flag = needs_review(out, settings.NEEDS_REVIEW_THRESHOLD)
            documents.set_page_status(page, PageOcrStatus.NEEDS_REVIEW if flag else PageOcrStatus.COMPLETED)
            # Text hiệu lực: bản chỉnh sửa của người dùng (nếu có) vẫn được ưu tiên
            correction = current_correction(db, page.id)
            index_page(db, page.id, correction.corrected_text if correction else out.text)
            if out.is_text_layer:
                text_layer += 1
            elif conf is not None:
                confidences.append(conf)
            if flag:
                review.append(page_in.number)
        ctx.progress(round(page_in.number * 100 / max(total, 1)))

    ctx.set_result(
        {
            "pages": total,
            "profile": profile,
            "text_layer_pages": text_layer,
            "needs_review_pages": review,
            "failed_pages": failed,
            "avg_confidence": round(float(sum(confidences) / len(confidences)), 2) if confidences else None,
            "seconds": round(time.perf_counter() - t0, 2),
        }
    )
    if total and len(failed) == total:
        raise JobError("OCR_ALL_PAGES_FAILED", "Tất cả các trang đều lỗi")
    publish(db, OcrCompleted(doc.id, job.id))
