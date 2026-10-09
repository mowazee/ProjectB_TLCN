"""P2-02 highlight trên ảnh/file scan: file bổ sung trong module search, cờ "highlight"."""

from app.modules.search.presentation.highlight_router import router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(name="highlight", feature="highlight", router=router, permissions=["search:highlight"])
