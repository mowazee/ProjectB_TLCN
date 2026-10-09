"""UC-18 Ghi audit log. Mọi module ghi audit qua hàm record() này (API công khai).

Ghi trong transaction nghiệp vụ, bọc SAVEPOINT: bình thường commit cùng thao tác; riêng
việc ghi log lỗi thì ghi application log và cảnh báo (UC-18 2a), không làm hỏng nghiệp vụ.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.audit.infrastructure.models import AuditLog, AuditResult
from app.shared.context import RequestContext
from app.shared.db import utcnow

logger = logging.getLogger(__name__)


def record(
    db: Session,
    *,
    action: str,
    module: str,
    actor_id: uuid.UUID | None,
    ctx: RequestContext,
    entity_type: str | None = None,
    entity_id: Any = None,
    document_id: uuid.UUID | None = None,
    success: bool = True,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog | None:
    db.flush()  # lỗi dữ liệu nghiệp vụ phải nổi lên ở đây, không bị coi là lỗi audit
    log = AuditLog(
        user_id=actor_id,
        document_id=document_id,
        action=action,
        module=module,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        result=AuditResult.SUCCESS if success else AuditResult.FAILURE,
        ip_address=ctx.ip_address,
        user_agent=(ctx.user_agent or "")[:500] or None,
        request_id=ctx.request_id,
        state_before=before,
        state_after=after,
        created_at=utcnow(),
    )
    try:
        with db.begin_nested():
            db.add(log)
    except SQLAlchemyError:
        logger.exception("Ghi audit thất bại: action=%s entity=%s", action, entity_id)
        return None
    return log
