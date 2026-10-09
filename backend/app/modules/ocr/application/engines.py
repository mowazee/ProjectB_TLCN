"""Registry OCR engine theo profile (điểm mở rộng port OcrEngine).

- "print": OCR in (MVP), mặc định PaddleOCR.
- P2-03 đăng ký "handwriting" (HandwritingEngine) qua ModuleSpec.setup.
Engine khởi tạo một lần mỗi tiến trình. Lỗi khởi tạo được ghi nhớ: PaddleX không cho khởi
tạo lại trong cùng tiến trình, nên các lần gọi sau báo lại đúng nguyên nhân gốc.
"""

import logging
import threading
from collections.abc import Callable

from app.modules.ocr.domain.ports import OcrEngine
from app.shared.config import settings

logger = logging.getLogger(__name__)

_factories: dict[str, Callable[[], OcrEngine]] = {}
_engines: dict[str, OcrEngine] = {}
_errors: dict[str, Exception] = {}
_lock = threading.Lock()


class OcrEngineInitError(RuntimeError):
    pass


def _paddle_factory() -> OcrEngine:
    if settings.OCR_ENGINE != "paddleocr":
        raise ValueError(f"OCR_ENGINE không được hỗ trợ: {settings.OCR_ENGINE}")
    from app.modules.ocr.infrastructure.engines.paddle import PaddleOcrEngine

    return PaddleOcrEngine(settings.OCR_LANG, settings.OCR_DEVICE)


def register_engine(profile: str, factory: Callable[[], OcrEngine]) -> None:
    _factories[profile] = factory


def profiles() -> list[str]:
    return sorted(_factories)


def get_engine(profile: str = "print") -> OcrEngine:
    with _lock:
        if profile in _engines:
            return _engines[profile]
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
        return _engines[profile]


def reset() -> None:
    """Gọi khi activate registry: chỉ giữ factory mặc định của lõi."""
    _factories.clear()
    _factories["print"] = _paddle_factory


def override(profile: str, engine: OcrEngine) -> None:
    """Cho test: dùng engine giả không cần model."""
    _engines[profile] = engine
    _errors.pop(profile, None)


def clear_instances() -> None:
    _engines.clear()
    _errors.clear()


reset()
