from app.modules.users.presentation.router import router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(name="users", router=router, permissions=["users:manage"])
