from app.modules.audit.presentation.router import router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(name="audit", router=router, permissions=["audit:read"])
