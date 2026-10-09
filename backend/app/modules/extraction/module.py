"""P2-04 trích xuất trường: cờ "extraction"; job EXTRACT chạy sau OcrCompleted (Đặc tả đề tài 4.6)."""

from app.modules.extraction.application import fields
from app.modules.extraction.presentation.router import router
from app.modules.ocr.domain.events import OcrCompleted
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(
    name="extraction",
    feature="extraction",
    router=router,
    job_handlers={fields.KIND: fields.run_extraction},
    event_handlers=[(OcrCompleted, fields.enqueue_extraction)],
    permissions=["fields:read", "fields:verify"],
)
