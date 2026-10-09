"""Policy quyền theo tài liệu (SDD mục 3; D-02 còn mở - áp dụng đề xuất tạm thời):

- Admin: mọi tài liệu.
- Phạm vi (scope): tài liệu do mình sở hữu hoặc thuộc phòng ban của mình.
- Xem/tìm kiếm/preview: mọi vai trò trong phạm vi.
- Quản lý (upload, sửa OCR, sửa metadata, xóa, tải file gốc, khôi phục): Nghiệp vụ trong phạm vi.
Python thuần (R3): không phụ thuộc FastAPI/SQLAlchemy.
"""

import uuid
from dataclasses import dataclass

from app.shared.context import OFFICER, Principal


@dataclass(frozen=True)
class DocScope:
    owner_id: uuid.UUID | None
    department_id: int | None


def in_scope(principal: Principal, doc: DocScope) -> bool:
    if principal.is_admin:
        return True
    if doc.owner_id is not None and doc.owner_id == principal.id:
        return True
    return principal.department_id is not None and doc.department_id == principal.department_id


def can_view(principal: Principal, doc: DocScope) -> bool:
    return in_scope(principal, doc)


def can_manage(principal: Principal, doc: DocScope) -> bool:
    return in_scope(principal, doc) and principal.has_any(OFFICER)


def can_upload(principal: Principal) -> bool:
    return principal.has_any(OFFICER)
