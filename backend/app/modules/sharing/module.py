"""FR-18 (SDD v0.13, D-13): chia sẻ tài liệu đã xuất bản ra ngoài hệ thống bằng link + OTP email (lõi).

Tính năng chỉ hoạt động khi đã cấu hình SMTP (app.shared.email.email_enabled()).
"""

from app.modules.sharing.application.links import EMAIL_KIND, run_email
from app.modules.sharing.presentation.router import public_router, router
from app.shared.modules import ModuleSpec

MODULE = ModuleSpec(
    name="sharing",
    router=router,
    routers=(public_router,),
    job_handlers={EMAIL_KIND: run_email},
    permissions=["sharing:external"],
)
