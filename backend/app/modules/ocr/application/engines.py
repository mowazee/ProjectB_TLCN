"""Registry OCR engine theo profile (điểm mở rộng port OcrEngine).

- "print": OCR in (MVP), engine theo OCR_ENGINE: paddleocr | vietocr (GUIDE 9 phương án 1) | auto.
- P2-03 đăng ký "handwriting" (HandwritingEngine) qua ModuleSpec.setup.
Engine khởi tạo một lần mỗi tiến trình. Lỗi khởi tạo được ghi nhớ: PaddleX không cho khởi
tạo lại trong cùng tiến trình, nên các lần gọi sau báo lại đúng nguyên nhân gốc.
Mọi engine trả về đều được bọc lọc ký tự lạ (GUIDE 9 phương án 3, domain/charset.py).
"""

import importlib.util
import logging
import threading
from collections.abc import Callable
from typing import Any

from app.modules.ocr.domain.charset import sanitize
from app.modules.ocr.domain.ports import OcrEngine, OcrOutput
from app.shared.config import settings

logger = logging.getLogger(__name__)

_factories: dict[str, Callable[[], OcrEngine]] = {}
_engines: dict[str, OcrEngine] = {}
_errors: dict[str, Exception] = {}
_lock = threading.Lock()


class OcrEngineInitError(RuntimeError):
    pass


def resolved_print_engine() -> str:
    """Tên engine chữ in thực dùng: "auto" -> vietocr nếu đã cài gói, không thì paddleocr."""
    if settings.OCR_ENGINE == "auto":
        return "vietocr" if importlib.util.find_spec("vietocr") else "paddleocr"
    return settings.OCR_ENGINE


def _print_factory() -> OcrEngine:
    name = resolved_print_engine()
    if name == "paddleocr":
        from app.modules.ocr.infrastructure.engines.paddle import PaddleOcrEngine

        return PaddleOcrEngine(settings.OCR_LANG, settings.OCR_DEVICE)
    if name == "vietocr":
        from app.modules.ocr.infrastructure.engines.vietocr import LineCrop, VietOcrEngine

        crop = LineCrop(pad=4, max_ratio=settings.OCR_VIETOCR_MAX_RATIO or None)
        return VietOcrEngine(crop, det_model=settings.OCR_DET_MODEL or None, config=settings.OCR_VIETOCR_CONFIG)
    raise ValueError(f"OCR_ENGINE không được hỗ trợ: {settings.OCR_ENGINE}")


class _Sanitized:
    """Bọc engine: lọc ký tự lạ trên kết quả; name/version giữ nguyên của engine gốc."""

    def __init__(self, engine: OcrEngine) -> None:
        self.inner = engine
        self.name = engine.name
        self.version = engine.version

    def recognize(self, image_bgr: Any) -> OcrOutput:
        return sanitize(self.inner.recognize(image_bgr))


def register_engine(profile: str, factory: Callable[[], OcrEngine]) -> None:
    _factories[profile] = factory


def profiles() -> list[str]:
    return sorted(_factories)


def get_engine(profile: str = "print") -> OcrEngine:
    with _lock:
        if profile in _engines:
            return _Sanitized(_engines[profile])
        if profile in _errors:
            raise OcrEngineInitError(f"Engine '{profile}' khởi tạo lỗi, cần khởi động lại worker: {_errors[profile]!r}")
        factory = _factories.get(profile)
        if factory is None:
            raise OcrEngineInitError(f"Chưa đăng ký OCR profile '{profile}' (tính năng có thể đang tắt)")
        logger.info("Khởi tạo OCR engine profile=%s", profile)
        try:
            _engines[profile] = factory()
        except Exception as exc:
            _errors[profile] = exc
            raise
        return _Sanitized(_engines[profile])


def reset() -> None:
    """Gọi khi activate registry: chỉ giữ factory mặc định của lõi."""
    _factories.clear()
    _factories["print"] = _print_factory


def override(profile: str, engine: OcrEngine) -> None:
    """Cho test: dùng engine giả không cần model."""
    _engines[profile] = engine
    _errors.pop(profile, None)


def clear_instances() -> None:
    _engines.clear()
    _errors.clear()


reset()
