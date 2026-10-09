from app.modules.auth.presentation.router import router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(name="auth", router=router, permissions=["session"])
