"""P2-06 so sánh phiên bản: file bổ sung trong module ocr, cờ "versions"."""

from app.modules.ocr.presentation.versions_router import router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(name="versions", feature="versions", router=router, permissions=["ocr:versions"])
