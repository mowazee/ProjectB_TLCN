from app.modules.search.presentation.router import router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(name="search", router=router, permissions=["search:read"])
