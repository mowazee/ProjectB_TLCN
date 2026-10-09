"""UC-05b bước 4-5: xóa cứng tài liệu quá hạn khôi phục (Celery beat, D-05).

Bỏ qua tài liệu còn job queued/processing (FR-07). Xóa file trong storage trước; lỗi xóa
file thì giữ bản ghi để thử lại lượt sau (không để dữ liệu mồ côi). Xóa documents kéo theo
document_pages, ocr_results, ocr_corrections, processing_jobs (ON DELETE CASCADE); audit_logs
giữ lại (document_id ON DELETE SET NULL), id tài liệu lưu trong state_before.
"""

import logging
from datetime import timedelta

from sqlalchemy import select

from app.modules.audit.application.recorder import record
from app.modules.documents.domain.events import DocumentPurged
from app.modules.documents.domain.lifecycle import LifecycleStatus
from app.modules.documents.infrastructure.models import Document
from app.modules.jobs.application.queries import has_running_jobs
from app.shared.config import settings
from app.shared.context import SYSTEM_CONTEXT
from app.shared.db import SessionLocal, utcnow
from app.shared.events import publish
from app.shared.storage import document_prefix, get_storage

logger = logging.getLogger(__name__)


def purge_expired() -> int:
    cutoff = utcnow() - timedelta(days=settings.SOFT_DELETE_RETENTION_DAYS)
    purged = 0
    storage = get_storage()
    with SessionLocal() as db:
        candidates = db.scalars(
            select(Document).where(Document.lifecycle_status == LifecycleStatus.DELETED, Document.deleted_at < cutoff)
        ).all()
        for doc in candidates:
            if has_running_jobs(db, doc.id):
                continue
            try:
                storage.delete_prefix(document_prefix(doc.id))
            except Exception:
                logger.exception("Không xóa được file của tài liệu %s, thử lại lượt sau", doc.id)
                continue
            state = {
                "document_id": str(doc.id),
                "title": doc.title,
                "deleted_at": doc.deleted_at.isoformat() if doc.deleted_at else None,
            }
            record(
                db,
                action="purge",
                module="documents",
                actor_id=None,
                ctx=SYSTEM_CONTEXT,
                entity_type="document",
                entity_id=doc.id,
                document_id=None,
                before=state,
            )
            publish(db, DocumentPurged(doc.id))
            db.delete(doc)
            db.commit()
            purged += 1
    return purged
