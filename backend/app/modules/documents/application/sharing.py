"""UC-29 (FR-13, D-09): chia sẻ tài liệu đã xuất bản.

Chỉ chủ sở hữu hoặc Admin xem/đổi cấu hình. PUT thay TOÀN BỘ cấu hình (chế độ + danh sách phòng ban + người).
Cấu hình được giữ khi hủy xuất bản và có hiệu lực lại khi xuất bản lại (chỉ đọc khi approval_status = published).
Quy tắc:
- Riêng tư: danh sách phòng ban bị bỏ (chỉ còn người được thêm đích danh).
- Phòng ban của chính tài liệu và chủ sở hữu luôn có quyền nên không lưu thành dòng chia sẻ.
- Người được thêm MỚI nhận thông báo (P2-07; NullNotifier khi notifications tắt).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.documents.application.queries import scope_of
from app.modules.documents.domain import policies
from app.modules.documents.domain.lifecycle import ApprovalStatus, LifecycleStatus, ShareMode
from app.modules.documents.infrastructure.models import Document, DocumentShare
from app.modules.users.application.queries import UserBrief, department_names, user_briefs
from app.shared.context import Principal, RequestContext
from app.shared.errors import ConflictError, NotFoundError, PermissionDeniedError, UnprocessableError
from app.shared.notify import get_notifier

MAX_DEPARTMENTS = 100
MAX_USERS = 200


@dataclass(frozen=True)
class DepartmentRef:
    id: int
    name: str


@dataclass(frozen=True)
class SharingView:
    document_id: uuid.UUID
    share_mode: str
    is_published: bool  # False: cấu hình đang tạm ngưng (D-09), phạm vi xem theo D-02
    owner_department: DepartmentRef | None  # phòng ban của tài liệu - luôn có quyền ở chế độ Nội bộ
    departments: list[DepartmentRef]
    users: list[UserBrief]


def _get(db: Session, principal: Principal, document_id: uuid.UUID) -> Document:
    doc = db.get(Document, document_id)
    if doc is None or doc.lifecycle_status != LifecycleStatus.ACTIVE:
        raise NotFoundError("Không tìm thấy tài liệu")
    if not (principal.is_admin or (doc.owner_id is not None and doc.owner_id == principal.id)):
        raise PermissionDeniedError("Chỉ chủ sở hữu tài liệu hoặc Quản trị viên được quản lý chia sẻ")
    return doc


def _config(doc: Document) -> tuple[set[int], set[uuid.UUID]]:
    deps = {s.department_id for s in doc.shares if s.department_id is not None}
    users = {s.user_id for s in doc.shares if s.user_id is not None}
    return deps, users


def _view(db: Session, doc: Document) -> SharingView:
    deps, users = _config(doc)
    names = department_names(db, deps | ({doc.department_id} if doc.department_id else set()))
    briefs = user_briefs(db, users)
    return SharingView(
        document_id=doc.id,
        share_mode=str(doc.share_mode),
        is_published=doc.approval_status == ApprovalStatus.PUBLISHED,
        owner_department=DepartmentRef(doc.department_id, names.get(doc.department_id, ""))
        if doc.department_id
        else None,
        departments=sorted((DepartmentRef(i, names.get(i, "")) for i in deps), key=lambda d: d.name),
        users=sorted((briefs[u] for u in users if u in briefs), key=lambda u: u.full_name),
    )


def get_sharing(db: Session, principal: Principal, document_id: uuid.UUID) -> SharingView:
    return _view(db, _get(db, principal, document_id))


def update_sharing(
    db: Session,
    principal: Principal,
    document_id: uuid.UUID,
    *,
    share_mode: ShareMode,
    department_ids: list[int],
    user_ids: list[uuid.UUID],
    ctx: RequestContext,
) -> SharingView:
    doc = _get(db, principal, document_id)
    if not policies.can_share(principal, scope_of(doc)):
        raise ConflictError(
            "Chỉ chia sẻ được tài liệu đã xuất bản",
            code="DOCUMENT_NOT_PUBLISHED",
            details={"approval_status": str(doc.approval_status)},
        )
    deps = set(department_ids) - ({doc.department_id} if doc.department_id else set())
    users = set(user_ids) - ({doc.owner_id} if doc.owner_id else set())
    if share_mode == ShareMode.PRIVATE:
        deps = set()
    if len(deps) > MAX_DEPARTMENTS or len(users) > MAX_USERS:
        raise UnprocessableError("Danh sách chia sẻ quá dài", fields={"user_ids": "too_many"})
    unknown_deps = deps - set(department_names(db, deps))
    if unknown_deps:
        raise UnprocessableError(
            "Phòng ban không tồn tại",
            fields={"department_ids": "invalid"},
            details={"department_ids": sorted(unknown_deps)},
        )
    briefs = user_briefs(db, users)
    invalid_users = {u for u in users if u not in briefs or not briefs[u].is_active}
    if invalid_users:
        raise UnprocessableError(
            "Người dùng không tồn tại hoặc đã bị khóa",
            fields={"user_ids": "invalid"},
            details={"user_ids": sorted(str(u) for u in invalid_users)},
        )

    old_deps, old_users = _config(doc)
    before = {
        "share_mode": str(doc.share_mode),
        "department_ids": sorted(old_deps),
        "user_ids": sorted(map(str, old_users)),
    }
    doc.share_mode = share_mode
    for share in list(doc.shares):
        keep = share.department_id in deps if share.department_id is not None else share.user_id in users
        if not keep:
            doc.shares.remove(share)
    doc.shares.extend(DocumentShare(department_id=d, created_by=principal.id) for d in sorted(deps - old_deps))
    added_users = users - old_users
    doc.shares.extend(DocumentShare(user_id=u, created_by=principal.id) for u in sorted(added_users, key=str))
    after = {"share_mode": str(share_mode), "department_ids": sorted(deps), "user_ids": sorted(map(str, users))}
    if after != before:
        record(
            db,
            action="update_sharing",
            module="documents",
            actor_id=principal.id,
            ctx=ctx,
            entity_type="document",
            entity_id=doc.id,
            document_id=doc.id,
            before=before,
            after=after,
        )
    recipients = [u for u in added_users if u != principal.id]
    if recipients:
        get_notifier().notify(
            db,
            sorted(recipients, key=str),
            title="Tài liệu được chia sẻ với bạn",
            message=f"{principal.full_name} đã chia sẻ '{doc.title}'",
            type="share.added",
            link_url=f"/documents/{doc.id}",
        )
    db.commit()
    db.refresh(doc)
    return _view(db, doc)
