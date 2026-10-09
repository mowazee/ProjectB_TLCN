"""P2-03 OCR chữ viết tay: file bổ sung trong module ocr, cờ "handwriting".

setup(): đăng ký engine profile "handwriting" (HandwritingEngine) và profile OCR -> hàng đợi
"ocr_hw" (worker riêng: WORKER_OCR_PROFILES=handwriting, -Q ocr_hw; compose --profile hw).
Tài liệu is_handwritten=True được xếp vào profile này. Tắt cờ hoặc lỗi model không ảnh hưởng OCR in.
"""

from app.modules.jobs.application.registry import register_ocr_profile
from app.modules.ocr.application import engines
from app.modules.ocr.presentation.reprocess_router import router
from app.shared.modules import ModuleSpec

PROFILE, QUEUE = "handwriting", "ocr_hw"


def _resolve(is_handwritten: bool) -> str | None:
    return PROFILE if is_handwritten else None


def _create_engine() -> object:
    from app.modules.ocr.infrastructure.engines.handwriting import create_handwriting_engine

    return create_handwriting_engine()


def _setup() -> None:
    engines.register_engine(PROFILE, _create_engine)  # type: ignore[arg-type]
    register_ocr_profile(PROFILE, QUEUE, _resolve)


MODULE = ModuleSpec(
    name="handwriting",
    feature="handwriting",
    router=router,
    permissions=["ocr:reprocess"],
    setup=_setup,
)
