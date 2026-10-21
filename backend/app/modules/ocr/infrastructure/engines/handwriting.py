"""Adapter HandwritingEngine (P2-03), cùng port OcrEngine với OCR in.

OCR_HW_ENGINE:
- "auto" (mặc định): "vietocr" nếu đã cài gói vietocr, không thì "paddleocr-hw".
- "paddleocr-hw" (baseline): PaddleOCR với model nhận dạng cấu hình qua OCR_HW_REC_MODEL
  (để trống = model mặc định của ngôn ngữ). Chạy được ngay trên máy hiện có.
- "vietocr": dò dòng bằng PaddleOCR (chỉ detection) + nhận dạng từng dòng bằng VietOCR
  (ứng viên chính cho chữ viết tay tiếng Việt, file 2 mục 2). Cài: backend/requirements-hw.txt.
  Lõi engine dùng chung với chữ in: engines/vietocr.py.
Model chọn qua benchmark CER trên tập chữ viết tay (NFR-08, mục tiêu > 70%): eval/README.md.
"""

import importlib.util
from typing import Any

from app.modules.ocr.domain.ports import OcrLine, OcrOutput
from app.modules.ocr.infrastructure.engines.paddle import _box
from app.modules.ocr.infrastructure.engines.vietocr import (  # noqa: F401 - prepare_vietocr, vietocr_cache_dir: API cũ
    LineCrop,
    VietOcrEngine,
    paddle_env,
    prepare_vietocr,
    vietocr_cache_dir,
)
from app.shared.config import settings


class PaddleHandwritingEngine:
    name = "paddleocr-hw"

    def __init__(self) -> None:
        paddle_env()
        import paddleocr
        from paddleocr import PaddleOCR

        self.version: str | None = getattr(paddleocr, "__version__", None)
        kwargs: dict[str, Any] = {
            "lang": settings.OCR_LANG,
            "device": settings.OCR_DEVICE,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": True,  # chữ viết tay hay nghiêng
        }
        if settings.OCR_HW_REC_MODEL:
            kwargs["text_recognition_model_name"] = settings.OCR_HW_REC_MODEL
            self.version = f"{self.version} {settings.OCR_HW_REC_MODEL}"
        self._ocr = PaddleOCR(**kwargs)

    def recognize(self, image_bgr: Any) -> OcrOutput:
        out = OcrOutput(self.name, self.version)
        for res in self._ocr.predict(image_bgr):
            boxes, polys = res.get("rec_boxes"), res.get("rec_polys")
            for i, (text, score) in enumerate(zip(res["rec_texts"], res["rec_scores"], strict=False)):
                out.lines.append(OcrLine(str(text), float(score), _box(boxes, polys, i)))
        return out


class VietOcrHandwritingEngine(VietOcrEngine):
    """VietOCR cho chữ viết tay: nới khung dòng vài pixel (nét chữ viết tay hay tràn ra ngoài khung detection),
    model dò dòng mặc định của PaddleOCR."""

    PAD = 4

    def __init__(self) -> None:
        super().__init__(LineCrop(pad=self.PAD))


def resolved_engine_name() -> str:
    """Tên engine thực dùng: "auto" -> vietocr nếu đã cài gói, không thì paddleocr-hw."""
    if settings.OCR_HW_ENGINE == "auto":
        return "vietocr" if importlib.util.find_spec("vietocr") else "paddleocr-hw"
    return settings.OCR_HW_ENGINE


def create_handwriting_engine() -> Any:
    name = resolved_engine_name()
    if name == "vietocr":
        return VietOcrHandwritingEngine()
    if name == "paddleocr-hw":
        return PaddleHandwritingEngine()
    raise ValueError(f"OCR_HW_ENGINE không được hỗ trợ: {settings.OCR_HW_ENGINE}")
