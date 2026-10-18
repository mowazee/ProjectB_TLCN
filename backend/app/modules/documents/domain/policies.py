"""Policy quyền theo tài liệu (SDD mục 3; D-02 chốt ở v0.6, bổ sung v0.7; D-08):

- Admin: mọi tài liệu.
- Phạm vi (scope) của Nghiệp vụ, Kiểm duyệt: tài liệu do mình sở hữu hoặc thuộc phòng ban của mình.
- Người dùng thông thường (VIEWER) - "chỉ đọc": chỉ tài liệu ĐÃ XUẤT BẢN thuộc phòng ban mình; khi cờ workflow tắt
  (không có khái niệm xuất bản) thì mọi tài liệu cùng phòng ban. Người có thêm vai trò khác dùng phạm vi rộng hơn.
- Xem/tìm kiếm/preview/tải file gốc (D-08): mọi vai trò trong phạm vi.
- Quản lý (upload, sửa OCR, sửa metadata, xóa, khôi phục): Nghiệp vụ trong phạm vi.
Python thuần (R3): không phụ thuộc FastAPI/SQLAlchemy; cờ workflow do tầng application truyền vào DocScope.
"""

import uuid
from dataclasses import dataclass

from app.shared.context import APPROVER, OFFICER, VIEWER, Principal

PUBLISHED = "published"


@dataclass(frozen=True)
class DocScope:
    owner_id: uuid.UUID | None
    department_id: int | None
    approval_status: str | None = None
    publication_required: bool = False  # cờ workflow bật: VIEWER chỉ thấy tài liệu đã xuất bản


def is_reader_only(principal: Principal) -> bool:
    """Chỉ có vai trò VIEWER (không kèm Nghiệp vụ/Kiểm duyệt/Admin)."""
    return VIEWER in principal.roles and not principal.has_any(OFFICER, APPROVER)


def in_scope(principal: Principal, doc: DocScope) -> bool:
    if principal.is_admin:
        return True
    same_department = principal.department_id is not None and doc.department_id == principal.department_id
    if is_reader_only(principal):
        return same_department and (not doc.publication_required or doc.approval_status == PUBLISHED)
    if doc.owner_id is not None and doc.owner_id == principal.id:
        return True
    return same_department


def can_view(principal: Principal, doc: DocScope) -> bool:
    return in_scope(principal, doc)


def can_manage(principal: Principal, doc: DocScope) -> bool:
    return in_scope(principal, doc) and principal.has_any(OFFICER)


def can_upload(principal: Principal) -> bool:
    return principal.has_any(OFFICER)
