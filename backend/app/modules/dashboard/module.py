from app.modules.dashboard.presentation.router import router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(name="dashboard", router=router, permissions=["dashboard:read"])
