"""UC-20 OCR chữ viết tay (P2-03): chạy lại OCR với profile print | handwriting.

Không tạo job trùng khi tài liệu đang có job OCR queued/processing (409 JOB_ALREADY_ACTIVE).
Kết quả mới ghi theo (page_id, job_id) mới; bản sửa của người dùng vẫn là text hiệu lực.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.documents.application import queries as documents
from app.modules.jobs.application.create import create_ocr_job
from app.modules.jobs.application.registry import ocr_profiles
from app.shared.context import Principal, RequestContext
from app.shared.errors import UnprocessableError


def reprocess(db: Session, principal: Principal, document_id: uuid.UUID, *, profile: str, ctx: RequestContext) -> Any:
    doc = documents.ensure_can_manage(db, principal, document_id)
    if profile not in ocr_profiles():
        raise UnprocessableError("OCR profile không hợp lệ hoặc chưa bật", fields={"ocr_profile": "invalid"})
    job = create_ocr_job(db, doc.id, profile=profile)
    record(
        db,
        action="reprocess_document",
        module="ocr",
        actor_id=principal.id,
        ctx=ctx,
        entity_type="document",
        entity_id=doc.id,
        document_id=doc.id,
        after={"job_id": str(job.id), "ocr_profile": profile, "queue": job.queue_name},
    )
    db.commit()
    return job
