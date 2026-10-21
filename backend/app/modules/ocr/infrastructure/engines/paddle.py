"""Adapter PaddleOCR cho OCR in (MVP). Nạp model một lần mỗi tiến trình worker."""

import os
from typing import Any

import numpy as np

from app.modules.ocr.domain.ports import OcrLine, OcrOutput
from app.shared.config import settings


class PaddleOcrEngine:
    name = "paddleocr"

    def __init__(self, lang: str, device: str) -> None:
        if not settings.OCR_MODEL_SOURCE_CHECK:
            # PaddleX kiểm tra nơi tải model mỗi lần khởi tạo (~2 phút khi mạng chậm)
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        import paddleocr  # import chậm: chỉ nạp trong worker
        from paddleocr import PaddleOCR

        self.version: str | None = getattr(paddleocr, "__version__", None)
        models: dict[str, str] = {}
        if settings.OCR_DET_MODEL:
            models["text_detection_model_name"] = settings.OCR_DET_MODEL
        if settings.OCR_REC_MODEL:
            models["text_recognition_model_name"] = settings.OCR_REC_MODEL
            self.version = f"{self.version} {settings.OCR_REC_MODEL}"  # ocr_results.engine_version ghi model đã dùng
        self._ocr = PaddleOCR(
            lang=None if models else lang,  # PaddleOCR bỏ qua lang khi đã chỉ định model
            device=device,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            **models,
        )

    def recognize(self, image_bgr: Any) -> OcrOutput:
        out = OcrOutput(self.name, self.version)
        for res in self._ocr.predict(image_bgr):
            boxes, polys = res.get("rec_boxes"), res.get("rec_polys")
            for i, (text, score) in enumerate(zip(res["rec_texts"], res["rec_scores"], strict=False)):
                out.lines.append(OcrLine(str(text), float(score), _box(boxes, polys, i)))
        return out


def _box(boxes: Any, polys: Any, i: int) -> tuple[int, int, int, int]:
    if boxes is not None and len(boxes) > i:
        x1, y1, x2, y2 = (int(v) for v in boxes[i])
        return x1, y1, x2 - x1, y2 - y1
    if polys is not None and len(polys) > i:
        pts = np.asarray(polys[i])
        x1, y1 = pts.min(axis=0)
        x2, y2 = pts.max(axis=0)
        return int(x1), int(y1), int(x2 - x1), int(y2 - y1)
    return 0, 0, 0, 0
