"""P2-08 bulk import: cờ "imports"; job BULK_IMPORT tạo từng tài liệu + job OCR riêng."""

from app.modules.imports.application import batch
from app.modules.imports.presentation.router import router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(
    name="imports",
    feature="imports",
    router=router,
    job_handlers={batch.KIND: batch.run_import},
    permissions=["documents:import"],
)
