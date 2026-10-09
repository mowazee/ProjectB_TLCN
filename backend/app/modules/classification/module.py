"""P2-05 phân loại tự động: cờ "classification"; job CLASSIFY chạy sau OcrCompleted."""

from app.modules.classification.application import suggest
from app.modules.classification.presentation.router import router
from app.modules.ocr.domain.events import OcrCompleted
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(
    name="classification",
    feature="classification",
    router=router,
    job_handlers={suggest.KIND: suggest.run_classification},
    event_handlers=[(OcrCompleted, suggest.enqueue_classification)],
    permissions=["category:suggest"],
)
