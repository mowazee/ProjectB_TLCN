"""Adapter HandwritingEngine (P2-03), cùng port OcrEngine với OCR in.

OCR_HW_ENGINE:
- "auto" (mặc định): "vietocr" nếu đã cài gói vietocr, không thì "paddleocr-hw".
- "paddleocr-hw" (baseline): PaddleOCR với model nhận dạng cấu hình qua OCR_HW_REC_MODEL
  (để trống = model mặc định của ngôn ngữ). Chạy được ngay trên máy hiện có.
- "vietocr": dò dòng bằng PaddleOCR (chỉ detection) + nhận dạng từng dòng bằng VietOCR
  (ứng viên chính cho chữ viết tay tiếng Việt, file 2 mục 2). Cài: backend/requirements-hw.txt.
Model chọn qua benchmark CER trên tập chữ viết tay (NFR-08, mục tiêu > 70%): eval/README.md.
"""

import importlib.util
import os
import tempfile
from pathlib import Path
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


def vietocr_cache_dir() -> Path:
    return Path(settings.VIETOCR_CACHE_DIR) if settings.VIETOCR_CACHE_DIR else Path.home() / ".cache" / "vietocr"


def prepare_vietocr(name: str | None = None) -> dict[str, Any]:
    """Cấu hình VietOCR dùng file trên đĩa: tải cấu hình + weights MỘT lần vào cache.

    vietocr gốc tải cấu hình từ internet mỗi lần khởi tạo (mất mạng -> worker không lên được) và để
    cnn.pretrained=True làm torchvision tải thêm ~550 MB weights ImageNet vô ích (sau đó bị weights
    VietOCR ghi đè). Ở đây: cấu hình lưu thành <tên>.yml, weights lưu cạnh đó, pretrained=False.
    """
    import requests
    import yaml
    from vietocr.tool.config import Cfg

    name = name or settings.VIETOCR_CONFIG
    cache = vietocr_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    cfg_path = cache / f"{name}.yml"
    if cfg_path.is_file():
        cfg = Cfg(yaml.safe_load(cfg_path.read_text(encoding="utf-8")))
    else:
        cfg = Cfg.load_config_from_name(name)
        cfg_path.write_text(yaml.safe_dump(dict(cfg), allow_unicode=True), encoding="utf-8")
    url = str(cfg["weights"])
    weights = cache / url.rsplit("/", 1)[-1] if url.startswith("http") else Path(url)
    if not weights.is_file():
        fd, tmp = tempfile.mkstemp(dir=cache, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f, requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            os.replace(tmp, weights)  # chỉ xuất hiện khi tải xong, không để file dở dang
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    cfg["weights"] = str(weights)
    cfg["cnn"]["pretrained"] = False
    cfg["device"] = "cuda" if settings.OCR_DEVICE.startswith("gpu") else "cpu"
    return dict(cfg)


class VietOcrHandwritingEngine:
    name = "vietocr"
    PAD = 4  # nới khung dòng vài pixel: nét chữ viết tay hay tràn ra ngoài khung detection

    def __init__(self) -> None:
        _paddle_env()
        from importlib.metadata import version

        from paddleocr import TextDetection
        from vietocr.tool.config import Cfg
        from vietocr.tool.predictor import Predictor

        self._det = TextDetection()
        self._rec = Predictor(Cfg(prepare_vietocr()))
        self.version: str | None = f"{version('vietocr')} {settings.VIETOCR_CONFIG}"  # ghi vào engine_version

    def recognize(self, image_bgr: Any) -> OcrOutput:
        from PIL import Image

        out = OcrOutput(self.name, self.version)
        rgb = image_bgr[:, :, ::-1]
        height, width = rgb.shape[:2]
        polys: list[Any] = []
        for res in self._det.predict(image_bgr):
            polys.extend(res.get("dt_polys", []))
        boxes = sorted((_box(None, polys, i) for i in range(len(polys))), key=lambda b: (b[1] // 20, b[0]))
        p = self.PAD
        for x, y, w, h in boxes:
            if w <= 2 or h <= 2:
                continue
            x0, y0, x1, y1 = max(0, x - p), max(0, y - p), min(width, x + w + p), min(height, y + h + p)
            crop = Image.fromarray(np.ascontiguousarray(rgb[y0:y1, x0:x1]))
            text, prob = self._rec.predict(crop, return_prob=True)
            out.lines.append(OcrLine(str(text), float(prob), (x, y, w, h)))
        return out


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
