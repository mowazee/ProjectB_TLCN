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

Quyền SỬA theo chủ sở hữu và trạng thái duyệt (D-11, v0.12) - thay phần quyền quản lý theo phòng ban của D-02:
- SỬA (EDIT): sửa tiêu đề/số hiệu/danh mục (kể cả áp dụng gợi ý, gán vị trí lưu trữ), sửa OCR và khôi phục phiên
  bản, trích xuất/xác nhận trường. Nháp, Bị từ chối (hoặc cờ workflow tắt): chủ sở hữu. Chờ duyệt, Đã duyệt, Đã hủy
  xuất bản: Kiểm duyệt viên phòng ban của tài liệu và Admin. Đã xuất bản: không ai.
- Chạy lại OCR (REPROCESS, kể cả chạy lại job OCR lỗi): chỉ chủ sở hữu khi Nháp/Bị từ chối (Admin cũng vậy).
- Xóa mềm: chủ sở hữu khi Nháp/Bị từ chối; Admin mọi trạng thái. Khôi phục: chủ sở hữu, Admin.
- Dừng job: người được chạy lại OCR, hoặc Admin (job kẹt). Gửi duyệt, Rút lại: chủ sở hữu. Chia sẻ: chủ sở hữu, Kiểm
  duyệt viên phòng ban của tài liệu, Admin (khi đã xuất bản).
Rollback (P2-09) không đi qua các kiểm tra này (công cụ khôi phục của Admin, có audit).
Python thuần (R3): không phụ thuộc FastAPI/SQLAlchemy; cờ workflow do tầng application truyền vào DocScope.
"""

import uuid
from dataclasses import dataclass, field

from app.shared.context import APPROVER, OFFICER, VIEWER, Principal

DRAFT, PENDING_REVIEW, APPROVED, REJECTED, PUBLISHED, UNPUBLISHED = (
    "draft",
    "pending_review",
    "approved",
    "rejected",
    "published",
    "unpublished",
)
PRIVATE, INTERNAL, PUBLIC = "private", "internal", "public"
OWNER_PHASE = frozenset({DRAFT, REJECTED})  # chủ sở hữu sửa
REVIEW_PHASE = frozenset({PENDING_REVIEW, APPROVED, UNPUBLISHED})  # Kiểm duyệt viên phòng ban / Admin sửa

# Quyền trên một tài liệu (DocumentOut.permissions, D-11)
EDIT, REPROCESS, DELETE, RESTORE, CANCEL_JOB, SUBMIT, WITHDRAW, SHARE = (
    "edit",
    "reprocess",
    "delete",
    "restore",
    "cancel_job",
    "submit",
    "withdraw",
    "share",
)


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


def can_review(principal: Principal, doc: DocScope) -> bool:
    """Duyệt, từ chối, xuất bản, hủy xuất bản, trả lại, duyệt mượn: Kiểm duyệt viên phòng ban của tài liệu (hoặc
    Admin)."""
    return principal.has_any(APPROVER) and in_department_scope(principal, doc)


def phase(doc: DocScope) -> str:
    """Trạng thái duyệt dùng cho D-11; cờ workflow tắt (không có khái niệm duyệt) = Nháp."""
    if not doc.publication_required:
        return DRAFT
    return doc.approval_status or DRAFT


def is_owner(principal: Principal, doc: DocScope) -> bool:
    """Chủ sở hữu còn vai trò làm việc với tài liệu (Nghiệp vụ hoặc Admin)."""
    return _is_owner(principal, doc) and principal.has_any(OFFICER)


def can_edit(principal: Principal, doc: DocScope) -> bool:
    """D-11 SỬA: chủ sở hữu ở Nháp/Bị từ chối; Kiểm duyệt viên phòng ban / Admin khi đang duyệt hoặc đã hủy xuất bản."""
    st = phase(doc)
    if st in OWNER_PHASE:
        return is_owner(principal, doc)
    return st in REVIEW_PHASE and can_review(principal, doc)


def can_reprocess(principal: Principal, doc: DocScope) -> bool:
    """Chạy lại OCR / chạy lại job OCR lỗi: chỉ chủ sở hữu khi Nháp/Bị từ chối (Admin cũng không ngoại lệ)."""
    return phase(doc) in OWNER_PHASE and is_owner(principal, doc)


def can_delete(principal: Principal, doc: DocScope) -> bool:
    return principal.is_admin or can_reprocess(principal, doc)


def can_restore(principal: Principal, doc: DocScope) -> bool:
    return principal.is_admin or is_owner(principal, doc)


def can_cancel_job(principal: Principal, doc: DocScope) -> bool:
    """Dừng job: người được chạy lại OCR, hoặc Admin xử lý job kẹt."""
    return principal.is_admin or can_reprocess(principal, doc)


def can_submit(principal: Principal, doc: DocScope) -> bool:
    return doc.publication_required and phase(doc) in OWNER_PHASE and is_owner(principal, doc)


def can_withdraw(principal: Principal, doc: DocScope) -> bool:
    return doc.publication_required and phase(doc) in {PENDING_REVIEW, APPROVED} and is_owner(principal, doc)


def can_share(principal: Principal, doc: DocScope) -> bool:
    """FR-13 (v0.12): chủ sở hữu, Kiểm duyệt viên phòng ban của tài liệu hoặc Admin, chỉ khi tài liệu đã xuất bản."""
    if doc.approval_status != PUBLISHED:
        return False
    return principal.is_admin or _is_owner(principal, doc) or can_review(principal, doc)


_CHECKS = {
    EDIT: can_edit,
    REPROCESS: can_reprocess,
    DELETE: can_delete,
    RESTORE: can_restore,
    CANCEL_JOB: can_cancel_job,
    SUBMIT: can_submit,
    WITHDRAW: can_withdraw,
    SHARE: can_share,
}


def permissions(principal: Principal, doc: DocScope) -> list[str]:
    """Thao tác người dùng được làm trên tài liệu (D-11) - React dùng để hiện/ẩn nút; server vẫn kiểm từng thao tác."""
    return [name for name, check in _CHECKS.items() if check(principal, doc)]


def allowed(principal: Principal, doc: DocScope, permission: str) -> bool:
    return _CHECKS[permission](principal, doc)


def edit_lock_reason(principal: Principal, doc: DocScope) -> str | None:
    """Vì sao người có liên quan (người tải lên, Kiểm duyệt viên phòng ban, Admin) không SỬA được ở trạng thái hiện tại
    - hiện cạnh nút mờ. None nếu sửa được, hoặc người dùng không bao giờ sửa được tài liệu này (đồng nghiệp, người
    được chia sẻ): với họ React ẩn hẳn nút."""
    if can_edit(principal, doc) or not (is_owner(principal, doc) or can_review(principal, doc)):
        return None
    return _lock_reason(principal, doc)


def _lock_reason(principal: Principal, doc: DocScope) -> str:
    st = phase(doc)
    if st == PUBLISHED:
        return "Tài liệu đã xuất bản: cần hủy xuất bản trước khi chỉnh sửa"
    if st in OWNER_PHASE:
        return "Chỉ người tải lên chỉnh sửa được tài liệu ở trạng thái Nháp / Bị từ chối"
    if is_owner(principal, doc):
        if st == UNPUBLISHED:
            return "Tài liệu đã hủy xuất bản: chờ Kiểm duyệt viên trả lại để chỉnh sửa"
        return "Tài liệu đang chờ duyệt: bấm Rút lại để chỉnh sửa"
    return "Tài liệu đang trong quy trình duyệt: chỉ Kiểm duyệt viên phòng ban của tài liệu hoặc Admin chỉnh sửa"


def denial_message(principal: Principal, doc: DocScope, permission: str) -> str:
    if permission == REPROCESS and can_edit(principal, doc):
        return "Không chạy lại OCR trong lúc duyệt; chỉ người tải lên chạy lại khi tài liệu ở Nháp / Bị từ chối"
    if permission == REPROCESS and phase(doc) in OWNER_PHASE:
        return "Chỉ người tải lên chạy lại OCR được"
    if permission in (EDIT, REPROCESS):
        return _lock_reason(principal, doc)
    if permission == DELETE:
        return "Chỉ người tải lên (khi Nháp / Bị từ chối) hoặc Admin xóa được tài liệu"
    if permission == RESTORE:
        return "Chỉ người tải lên hoặc Admin khôi phục được tài liệu"
    return "Bạn không có quyền thực hiện thao tác này trên tài liệu"


def can_upload(principal: Principal) -> bool:
    return principal.has_any(OFFICER)
