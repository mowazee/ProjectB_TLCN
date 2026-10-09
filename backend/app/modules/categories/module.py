from app.modules.categories.presentation.router import router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(name="categories", router=router, permissions=["categories:manage"])
