"""Quy tắc mượn hồ sơ (P2-07). Python thuần (R3).

pending -> approved | rejected; approved -> returned. Quá hạn = approved và hôm nay > to_date
(tính toán, không lưu cột). Hai yêu cầu đã duyệt của cùng hồ sơ không được trùng thời gian.
"""

from datetime import date
from enum import StrEnum


class BorrowAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    RETURN = "return"


PENDING, APPROVED, REJECTED, RETURNED = "pending", "approved", "rejected", "returned"

TRANSITIONS: dict[BorrowAction, tuple[str, str]] = {
    BorrowAction.APPROVE: (PENDING, APPROVED),
    BorrowAction.REJECT: (PENDING, REJECTED),
    BorrowAction.RETURN: (APPROVED, RETURNED),
}


def overlaps(a_from: date, a_to: date, b_from: date, b_to: date) -> bool:
    return a_from <= b_to and b_from <= a_to


def is_overdue(status: str, to_date: date, today: date) -> bool:
    return status == APPROVED and today > to_date
