from fastapi import APIRouter

from app.modules.auth.presentation.account_router import router as account_router
from app.modules.auth.presentation.router import router as auth_router
from app.shared.modules import ModuleSpec

# /api/auth (đăng nhập, phiên) + /api/account (FR-09 tài khoản của tôi, v0.7)
router = APIRouter()
router.include_router(auth_router)
router.include_router(account_router)

MODULE = ModuleSpec(name="auth", router=router, permissions=["session"])
