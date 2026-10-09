"""Vai trò hệ thống (SDD mục 3). Admin kế thừa quyền của hai vai trò còn lại."""

from enum import StrEnum


class RoleCode(StrEnum):
    ADMIN = "ADMIN"
    OFFICER = "OFFICER"  # Nhân viên nghiệp vụ
    APPROVER = "APPROVER"  # Kiểm duyệt viên


ROLE_DESCRIPTIONS = {
    RoleCode.ADMIN: "Quản trị viên hệ thống",
    RoleCode.OFFICER: "Nhân viên nghiệp vụ",
    RoleCode.APPROVER: "Kiểm duyệt viên",
}
DEFAULT_DEPARTMENT = ("HC-TH", "Phòng Hành chính - Tổng hợp")
