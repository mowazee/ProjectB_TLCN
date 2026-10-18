"""Policy quyền theo tài liệu (SDD mục 3; D-02 chốt ở v0.6, bổ sung v0.7, v0.8; D-08; D-09):

Hai phạm vi tách riêng (v0.8):
- Phạm vi PHÒNG BAN (D-02): tài liệu do mình sở hữu hoặc thuộc phòng ban của mình; Admin: mọi tài liệu. Dùng cho
  quản lý (sửa, xóa, sửa OCR, khôi phục, thùng rác, hàng đợi), duyệt/xuất bản và duyệt mượn. Chia sẻ KHÔNG mở rộng
  phạm vi này. Người dùng thông thường (VIEWER) không có phạm vi phòng ban (chỉ đọc).
- Phạm vi XEM (xem, tìm kiếm, preview, tải file - D-08, tạo yêu cầu mượn theo vai trò):
  - tài liệu chưa xuất bản: phạm vi phòng ban; VIEWER không thấy (khi cờ workflow tắt - không có khái niệm xuất bản -
    VIEWER xem mọi tài liệu cùng phòng ban);
  - tài liệu đã xuất bản (D-09): chủ sở hữu, Kiểm duyệt viên phòng ban của tài liệu, người được chia sẻ đích danh,
    và theo chế độ: private - không thêm ai; internal - người thuộc phòng ban của tài liệu hoặc phòng ban được chọn;
    public - mọi người dùng đã đăng nhập.
Bản SQL của các quy tắc này nằm ở documents/application/queries.py; test_v08_sharing kiểm hai bản khớp nhau.
Python thuần (R3): không phụ thuộc FastAPI/SQLAlchemy; cờ workflow do tầng application truyền vào DocScope.
"""

import uuid
from dataclasses import dataclass, field

from app.shared.context import APPROVER, OFFICER, VIEWER, Principal

PUBLISHED = "published"
PRIVATE, INTERNAL, PUBLIC = "private", "internal", "public"


@dataclass(frozen=True)
class DocScope:
    owner_id: uuid.UUID | None
    department_id: int | None
    approval_status: str | None = None
    publication_required: bool = False  # cờ workflow bật: có khái niệm xuất bản
    share_mode: str = INTERNAL
    shared_department_ids: frozenset[int] = field(default_factory=frozenset)
    shared_user_ids: frozenset[uuid.UUID] = field(default_factory=frozenset)


def is_reader_only(principal: Principal) -> bool:
    """Chỉ có vai trò VIEWER (không kèm Nghiệp vụ/Kiểm duyệt/Admin)."""
    return VIEWER in principal.roles and not principal.has_any(OFFICER, APPROVER)


def is_shared_publication(doc: DocScope) -> bool:
    """Tài liệu đã xuất bản: phạm vi xem theo chế độ chia sẻ (D-09)."""
    return doc.publication_required and doc.approval_status == PUBLISHED


def _same_department(principal: Principal, doc: DocScope) -> bool:
    return principal.department_id is not None and doc.department_id == principal.department_id


def _is_owner(principal: Principal, doc: DocScope) -> bool:
    return doc.owner_id is not None and doc.owner_id == principal.id


def in_department_scope(principal: Principal, doc: DocScope) -> bool:
    """D-02: chủ sở hữu hoặc cùng phòng ban (Admin: tất cả; VIEWER: không có)."""
    if principal.is_admin:
        return True
    if is_reader_only(principal):
        return False
    return _is_owner(principal, doc) or _same_department(principal, doc)


def in_share_audience(principal: Principal, doc: DocScope) -> bool:
    """D-09: ai xem được tài liệu đã xuất bản."""
    if principal.is_admin or _is_owner(principal, doc) or principal.id in doc.shared_user_ids:
        return True
    if APPROVER in principal.roles and _same_department(principal, doc):
        return True  # Kiểm duyệt viên phòng ban của tài liệu luôn thấy để hủy xuất bản được
    if doc.share_mode == PUBLIC:
        return True
    if doc.share_mode == INTERNAL and principal.department_id is not None:
        return principal.department_id == doc.department_id or principal.department_id in doc.shared_department_ids
    return False


def can_view(principal: Principal, doc: DocScope) -> bool:
    if principal.is_admin:
        return True
    if is_shared_publication(doc):
        return in_share_audience(principal, doc)
    if is_reader_only(principal):
        return not doc.publication_required and _same_department(principal, doc)
    return in_department_scope(principal, doc)


def can_manage(principal: Principal, doc: DocScope) -> bool:
    """Sửa, xóa, sửa OCR, khôi phục: Nghiệp vụ trong phạm vi phòng ban VÀ xem được (Riêng tư: chỉ chủ sở hữu)."""
    return principal.has_any(OFFICER) and in_department_scope(principal, doc) and can_view(principal, doc)


def can_review(principal: Principal, doc: DocScope) -> bool:
    """Duyệt, từ chối, xuất bản, hủy xuất bản, duyệt mượn: Kiểm duyệt viên phòng ban của tài liệu (hoặc Admin)."""
    return principal.has_any(APPROVER) and in_department_scope(principal, doc)


def can_share(principal: Principal, doc: DocScope) -> bool:
    """FR-13: chủ sở hữu hoặc Admin, chỉ khi tài liệu đã xuất bản."""
    return doc.approval_status == PUBLISHED and (principal.is_admin or _is_owner(principal, doc))


def can_upload(principal: Principal) -> bool:
    return principal.has_any(OFFICER)
