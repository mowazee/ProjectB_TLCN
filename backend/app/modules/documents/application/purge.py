"""UC-05b bước 4-5: xóa cứng tài liệu quá hạn khôi phục (Celery beat, D-05).

Bỏ qua tài liệu còn job queued/processing (FR-07). Xóa toàn bộ file của tài liệu trong storage trước (file gốc, ảnh
trang, tài liệu đi kèm - cùng thư mục); lỗi xóa file thì giữ bản ghi để thử lại lượt sau (không để dữ liệu mồ côi).
Xóa documents kéo theo document_pages, ocr_results, ocr_corrections, processing_jobs, document_attachments,
share_links, document_approvals (ON DELETE CASCADE). Không giữ nhật ký của tài liệu đã xóa vĩnh viễn (v0.14): xóa
mọi audit_logs của tài liệu và không ghi dòng audit cho lượt xóa.
"""

import logging
from datetime import timedelta

from sqlalchemy import select

from app.modules.audit.application.retention import delete_for_document
from app.modules.documents.domain.events import DocumentPurged
from app.modules.documents.domain.lifecycle import LifecycleStatus
from app.modules.documents.infrastructure.models import Document
from app.modules.jobs.application.queries import has_running_jobs
from app.modules.settings.application.retention import trash_retention_days
from app.shared.db import SessionLocal, utcnow
from app.shared.events import publish
from app.shared.storage import document_prefix, get_storage

logger = logging.getLogger(__name__)


def purge_expired() -> int:
    purged = 0
    storage = get_storage()
    with SessionLocal() as db:
        cutoff = utcnow() - timedelta(days=trash_retention_days(db))  # FR-14: Admin cấu hình
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
            delete_for_document(db, doc.id)
            publish(db, DocumentPurged(doc.id))
            db.delete(doc)
            db.commit()
            purged += 1
    return purged
