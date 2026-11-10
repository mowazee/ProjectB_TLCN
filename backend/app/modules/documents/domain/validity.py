"""Hiệu lực tài liệu (FR-19, D-14 - SDD v0.14). Python thuần, không phụ thuộc framework.

Bốn trạng thái; "Còn hiệu lực đến ngày D" còn hiệu lực trọn ngày D và hết hiệu lực khi qua 23:59 ngày D theo giờ
hệ thống (APP_TIMEZONE), tức quy tắc chỉ là valid_until < hôm nay. API luôn trả trạng thái đã tính theo quy tắc này
(effective_status) nên tác vụ nền chạy trễ không làm hiển thị sai.
"""

from datetime import date
from enum import StrEnum


class ValidityStatus(StrEnum):
    UNSPECIFIED = "unspecified"  # Không quy định (mặc định, dữ liệu trước v0.14)
    EFFECTIVE = "effective"  # Còn hiệu lực
    EFFECTIVE_UNTIL = "effective_until"  # Còn hiệu lực đến ngày valid_until
    EXPIRED = "expired"  # Hết hiệu lực


LABELS = {
    ValidityStatus.UNSPECIFIED: "Không quy định",
    ValidityStatus.EFFECTIVE: "Còn hiệu lực",
    ValidityStatus.EFFECTIVE_UNTIL: "Còn hiệu lực đến ngày",
    ValidityStatus.EXPIRED: "Hết hiệu lực",
}

REASON_MIN, REASON_MAX = 5, 500


def effective_status(status: str, valid_until: date | None, today: date) -> ValidityStatus:
    st = ValidityStatus(status)
    if st == ValidityStatus.EFFECTIVE_UNTIL and valid_until is not None and valid_until < today:
        return ValidityStatus.EXPIRED
    return st


def is_due(status: str, valid_until: date | None, today: date) -> bool:
    """Đã qua ngày hết hạn nhưng dữ liệu chưa chuyển expired (beat sẽ chuyển)."""
    return status == ValidityStatus.EFFECTIVE_UNTIL and valid_until is not None and valid_until < today


def check_input(status: str, valid_until: date | None, today: date) -> tuple[str, str] | None:
    """Trả (mã lỗi, thông báo) nếu không hợp lệ."""
    try:
        st = ValidityStatus(status)
    except ValueError:
        return "VALIDITY_INVALID", "Trạng thái hiệu lực không hợp lệ"
    if st == ValidityStatus.EFFECTIVE_UNTIL:
        if valid_until is None:
            return "INVALID_VALID_UNTIL", "Hãy chọn ngày hết hiệu lực"
        if valid_until < today:
            return "INVALID_VALID_UNTIL", "Ngày hết hiệu lực phải từ hôm nay trở đi"
    return None


def label(status: str, valid_until: date | None) -> str:
    st = ValidityStatus(status)
    if st == ValidityStatus.EFFECTIVE_UNTIL and valid_until:
        return f"Còn hiệu lực đến ngày {valid_until:%d/%m/%Y}"
    if st == ValidityStatus.EXPIRED and valid_until:
        return f"Hết hiệu lực (từ sau ngày {valid_until:%d/%m/%Y})"
    return LABELS[st]


def days_left(valid_until: date, today: date) -> int:
    return (valid_until - today).days
