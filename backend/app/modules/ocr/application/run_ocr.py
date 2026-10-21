"""UC-02 Thực hiện OCR: handler cho job kind 'OCR' (đăng ký qua ModuleSpec.job_handlers).

Pipeline: file gốc -> PyMuPDF (text layer hoặc render) -> OpenCV tiền xử lý -> engine theo
profile (print | handwriting) -> document_pages + ocr_results -> chỉ mục text hiệu lực
-> OcrCompleted (phát sau commit). Lỗi một trang không làm hỏng cả tài liệu.
Trang có lớp chữ vẫn OCR các vùng ảnh nhúng chưa có chữ (v0.9, FR-04; ocr/domain/regions.py).
"""

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import cv2
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
from app.modules.ocr.domain.regions import Box, drop_duplicates, merge_reading_order, regions_to_ocr
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
    image_boxes: list[Box] | None = None


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
            _PageInput(p.number, png=p.png, lines=p.lines, image_boxes=p.image_boxes)
            for p in pdf.render_pages(src, settings.OCR_RENDER_DPI)
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
            lines = [OcrLine(ln.text, None, ln.box) for ln in page_in.lines or []]
            return page_in.png, w, h, _with_image_text(bgr, lines, page_in.image_boxes or [], holder)
        source = images.png_to_bgr(page_in.png)
    elif page_in.image_bgr is not None:
        source = page_in.image_bgr
    else:
        raise ValueError("Trang không có dữ liệu ảnh")
    processed, _ = images.preprocess(source)
    h, w = processed.shape[:2]
    out = holder.get().recognize(processed)
    return images.encode_png(processed), w, h, out


MIN_CROP_SIDE = 200  # vùng ảnh nhỏ hơn thì phóng to 2 lần cho engine đọc chữ nhỏ


def _ocr_region(engine: Any, page_bgr: np.ndarray, box: Box) -> list[OcrLine]:
    """OCR một vùng ảnh; box của kết quả đổi về toạ độ ảnh trang (để highlight P2-02 vẽ đúng chỗ)."""
    x, y, w, h = box
    crop = page_bgr[y : y + h, x : x + w]
    scale = 2.0 if min(w, h) < MIN_CROP_SIDE else 1.0
    if scale != 1.0:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    # Không deskew: vùng cắt phải giữ đúng hệ toạ độ của trang
    crop = cv2.cvtColor(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    out = engine.recognize(crop)
    return [
        OcrLine(
            ln.text,
            ln.score,
            (
                x + round(ln.box[0] / scale),
                y + round(ln.box[1] / scale),
                round(ln.box[2] / scale),
                round(ln.box[3] / scale),
            ),
        )
        for ln in out.lines
        if ln.text.strip()
    ]


def _with_image_text(
    page_bgr: np.ndarray, lines: list[OcrLine], image_boxes: list[Box], holder: "_EngineHolder"
) -> OcrOutput:
    """Trang có lớp chữ: thêm chữ OCR từ các ảnh nhúng chưa có chữ (nếu có) vào đúng vị trí đọc."""
    h, w = page_bgr.shape[:2]
    regions = regions_to_ocr(
        image_boxes,
        lines,
        w,
        h,
        min_area_ratio=settings.OCR_IMAGE_MIN_AREA,
        max_regions=settings.OCR_IMAGE_MAX_REGIONS,
        min_text_chars=settings.TEXT_LAYER_MIN_CHARS,
    )
    if not regions:  # PDF thuần chữ: không nạp engine OCR
        return OcrOutput(TEXT_LAYER_ENGINE, pymupdf.__version__, lines)
    engine = holder.get()
    blocks = [(box, drop_duplicates(_ocr_region(engine, page_bgr, box), lines)) for box in regions]
    if not any(found for _, found in blocks):
        return OcrOutput(TEXT_LAYER_ENGINE, pymupdf.__version__, lines)
    # engine_version tối đa 50 ký tự: ghi phiên bản/model của engine OCR (phần quyết định chất lượng), bỏ bản PyMuPDF
    return OcrOutput(f"{TEXT_LAYER_ENGINE}+{engine.name}", engine.version, merge_reading_order(lines, blocks))


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
    # Không giữ transaction mở trong lúc OCR (một trang có thể mất hàng chục giây): API/người dùng cần ghi vào job
    # (vd. bấm Dừng) không bị chặn; các trang sau đã có commit ở ctx.progress.
    db.commit()
    failed: list[int] = []
    review: list[int] = []
    confidences: list[Decimal] = []
    text_layer = 0
    mixed = 0
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
            elif out.engine.startswith(f"{TEXT_LAYER_ENGINE}+"):
                mixed += 1  # lớp chữ + OCR vùng ảnh
                if conf is not None:
                    confidences.append(conf)
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
            "mixed_pages": mixed,
            "needs_review_pages": review,
            "failed_pages": failed,
            "avg_confidence": round(float(sum(confidences) / len(confidences)), 2) if confidences else None,
            "seconds": round(time.perf_counter() - t0, 2),
        }
    )
    if total and len(failed) == total:
        raise JobError("OCR_ALL_PAGES_FAILED", "Tất cả các trang đều lỗi")
    publish(db, OcrCompleted(doc.id, job.id))
