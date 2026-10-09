"""Module registry (điểm mở rộng, Đặc tả đề tài v0.5 mục 4.3, 4.6).

ALL_MODULES: lõi MVP luôn bật; module P2/P3 chỉ thêm MỘT dòng vào đây (R9).
activate(): nạp module đang bật theo FEATURES_ENABLED: đăng ký job handler, event handler,
và gọi setup() để module cắm vào registry của lõi (engine OCR, dashboard, notifier...).
"""

from app.modules.audit import module as audit
from app.modules.auth import module as auth
from app.modules.borrowing import module as borrowing
from app.modules.categories import module as categories
from app.modules.classification import module as classification
from app.modules.dashboard import module as dashboard
from app.modules.documents import module as documents
from app.modules.extraction import module as extraction
from app.modules.imports import module as imports
from app.modules.jobs import module as jobs
from app.modules.notifications import module as notifications
from app.modules.ocr import handwriting_module, versions_module
from app.modules.ocr import module as ocr
from app.modules.rollback import module as rollback
from app.modules.search import highlight_module
from app.modules.search import module as search
from app.modules.users import module as users
from app.modules.workflow import module as workflow
from app.shared.config import Settings, settings
from app.shared.modules import ModuleSpec

ALL_MODULES: list[ModuleSpec] = [
    auth.MODULE,
    users.MODULE,
    categories.MODULE,
    documents.MODULE,
    jobs.MODULE,
    ocr.MODULE,
    search.MODULE,
    dashboard.MODULE,
    audit.MODULE,  # lõi MVP
    notifications.MODULE,  # P2-07 (Notifier dùng chung với P2-01)
    workflow.MODULE,  # P2-01
    highlight_module.MODULE,  # P2-02
    handwriting_module.MODULE,  # P2-03
    extraction.MODULE,  # P2-04
    classification.MODULE,  # P2-05
    versions_module.MODULE,  # P2-06
    borrowing.MODULE,  # P2-07
    imports.MODULE,  # P2-08
    rollback.MODULE,  # P2-09
]


def enabled_modules(s: Settings = settings) -> list[ModuleSpec]:
    return [m for m in ALL_MODULES if m.feature is None or m.feature in s.features_enabled]


def activate(s: Settings = settings) -> list[ModuleSpec]:
    """Đặt lại mọi registry của lõi rồi đăng ký module đang bật (dùng cho API, worker, beat, test)."""
    from app.modules.dashboard.application import stats
    from app.modules.jobs.application import registry as job_registry
    from app.modules.ocr.application import engines
    from app.shared import notify
    from app.shared.events import bus

    bus.clear()
    job_registry.reset()
    engines.reset()
    stats.reset()
    notify.reset_notifier()
    modules = enabled_modules(s)
    for m in modules:
        for kind, handler in m.job_handlers.items():
            job_registry.register_handler(kind, handler)
        for event_type, handler in m.event_handlers:
            bus.subscribe(event_type, handler)
        if m.setup is not None:
            m.setup()
    return modules
