"""Adapter HandwritingEngine (P2-03), cùng port OcrEngine với OCR in.

OCR_HW_ENGINE:
- "paddleocr-hw" (baseline): PaddleOCR với model nhận dạng cấu hình qua OCR_HW_REC_MODEL
  (để trống = model mặc định của ngôn ngữ). Chạy được ngay trên máy hiện có.
- "vietocr": dò dòng bằng PaddleOCR (chỉ detection) + nhận dạng từng dòng bằng VietOCR
  (pip install vietocr; ứng viên chính cho chữ viết tay tiếng Việt, file 2 mục 2).
Model chọn qua benchmark CER trên tập chữ viết tay (NFR-08, mục tiêu > 70%): eval/README.md.
"""

import os
from typing import Any

import numpy as np

from app.modules.ocr.domain.ports import OcrLine, OcrOutput
from app.modules.ocr.infrastructure.engines.paddle import _box
from app.shared.config import settings


def _paddle_env() -> None:
    if not settings.OCR_MODEL_SOURCE_CHECK:
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


class PaddleHandwritingEngine:
    name = "paddleocr-hw"

    def __init__(self) -> None:
        _paddle_env()
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


class VietOcrHandwritingEngine:
    name = "vietocr"

    def __init__(self) -> None:
        _paddle_env()
        from paddleocr import TextDetection
        from vietocr.tool.config import Cfg
        from vietocr.tool.predictor import Predictor

        cfg = Cfg.load_config_from_name(settings.VIETOCR_CONFIG)
        cfg["device"] = "cuda" if settings.OCR_DEVICE.startswith("gpu") else "cpu"
        self._det = TextDetection()
        self._rec = Predictor(cfg)
        self.version: str | None = settings.VIETOCR_CONFIG

    def recognize(self, image_bgr: Any) -> OcrOutput:
        from PIL import Image

        out = OcrOutput(self.name, self.version)
        rgb = image_bgr[:, :, ::-1]
        polys: list[Any] = []
        for res in self._det.predict(image_bgr):
            polys.extend(res.get("dt_polys", []))
        boxes = sorted((_box(None, polys, i) for i in range(len(polys))), key=lambda b: (b[1] // 20, b[0]))
        for x, y, w, h in boxes:
            if w <= 2 or h <= 2:
                continue
            crop = Image.fromarray(np.ascontiguousarray(rgb[y : y + h, x : x + w]))
            text, prob = self._rec.predict(crop, return_prob=True)
            out.lines.append(OcrLine(str(text), float(prob), (x, y, w, h)))
        return out


def create_handwriting_engine() -> Any:
    if settings.OCR_HW_ENGINE == "vietocr":
        return VietOcrHandwritingEngine()
    if settings.OCR_HW_ENGINE == "paddleocr-hw":
        return PaddleHandwritingEngine()
    raise ValueError(f"OCR_HW_ENGINE không được hỗ trợ: {settings.OCR_HW_ENGINE}")
