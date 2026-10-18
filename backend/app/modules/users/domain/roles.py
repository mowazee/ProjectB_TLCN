"""Vai trò hệ thống (SDD mục 3, FR-12, D-07): 4 vai trò cố định, Admin kế thừa quyền của các vai trò còn lại.

ROLE_PERMISSIONS là ma trận quyền HIỂN THỊ (chỉ đọc, trang Nhóm quyền). Quyền thực sự vẫn được kiểm ở server tại
từng use case (policies, require_roles...); khi đổi quy tắc ở đó phải sửa mô tả ở đây và SDD mục 3 cùng lúc.
"""

from enum import StrEnum


class RoleCode(StrEnum):
    ADMIN = "ADMIN"
    OFFICER = "OFFICER"  # Nhân viên nghiệp vụ
    APPROVER = "APPROVER"  # Kiểm duyệt viên
    VIEWER = "VIEWER"  # Người dùng thông thường (v0.7): chỉ xem, tìm kiếm, tải


ROLE_DESCRIPTIONS = {
    RoleCode.ADMIN: "Quản trị viên hệ thống",
    RoleCode.OFFICER: "Nhân viên nghiệp vụ",
    RoleCode.APPROVER: "Kiểm duyệt viên",
    RoleCode.VIEWER: "Người dùng thông thường",
}

ROLE_SUMMARIES = {
    RoleCode.ADMIN: "Toàn quyền: quản trị người dùng, nhóm quyền, phòng ban, danh mục, nhật ký; làm được mọi thao tác.",
    RoleCode.OFFICER: "Số hóa và quản lý tài liệu của phòng ban: tải lên, sửa OCR, gửi duyệt, mượn hồ sơ.",
    RoleCode.APPROVER: "Kiểm duyệt: duyệt, từ chối, xuất bản tài liệu; duyệt yêu cầu mượn hồ sơ.",
    RoleCode.VIEWER: "Chỉ xem, tìm kiếm và tải tài liệu đã xuất bản thuộc phòng ban mình.",
}

ROLE_PERMISSIONS: dict[RoleCode, list[str]] = {
    RoleCode.ADMIN: [
        "Xem và quản lý mọi tài liệu (không giới hạn phòng ban)",
        "Quản lý người dùng, nhóm quyền, phòng ban",
        "Quản lý danh mục, kho lưu trữ",
        "Xem nhật ký hệ thống, khôi phục thay đổi (rollback)",
        "Mọi quyền của Nghiệp vụ và Kiểm duyệt",
    ],
    RoleCode.OFFICER: [
        "Xem, tìm kiếm, tải tài liệu trong phạm vi (của mình và phòng ban)",
        "Tải lên, nhập hàng loạt, sửa thông tin, xóa và khôi phục tài liệu",
        "Sửa kết quả OCR, xác nhận trường trích xuất, chấp nhận gợi ý danh mục",
        "Gửi duyệt tài liệu",
        "Tạo yêu cầu mượn hồ sơ",
        "Theo dõi hàng đợi xử lý, chạy lại job lỗi",
    ],
    RoleCode.APPROVER: [
        "Xem, tìm kiếm, tải tài liệu trong phạm vi (của mình và phòng ban)",
        "Duyệt, từ chối, xuất bản, hủy xuất bản tài liệu",
        "Tạo yêu cầu mượn; duyệt yêu cầu mượn và ghi nhận trả",
    ],
    RoleCode.VIEWER: [
        "Xem, tìm kiếm tài liệu đã xuất bản thuộc phòng ban mình",
        "Tải file gốc của tài liệu được xem (mỗi lượt tải ghi nhật ký)",
        "Không tải lên, sửa, gửi duyệt hay mượn hồ sơ",
    ],
}
DEFAULT_DEPARTMENT = ("HC-TH", "Phòng Hành chính - Tổng hợp")
