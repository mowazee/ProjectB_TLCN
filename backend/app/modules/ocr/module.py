"""OCR in (MVP). File bổ sung của P2 trong cùng module: handwriting_module.py (P2-03),
versions_module.py (P2-06) - mỗi file có ModuleSpec và cờ riêng."""

from app.modules.ocr.application import run_ocr
from app.modules.ocr.presentation.router import router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(
    name="ocr",
    router=router,
    job_handlers={"OCR": run_ocr.handle},
    permissions=["ocr:read", "ocr:edit"],
)
