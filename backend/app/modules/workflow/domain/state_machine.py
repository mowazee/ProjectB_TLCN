"""State machine duyệt/xuất bản (P2-01, SDD mục 5). Python thuần (R3).

draft -> pending_review -> approved | rejected; rejected -> draft; approved -> published <-> unpublished.
"rejected -> draft" không có action riêng trong API (SDD 7.2 chỉ có submit/approve/reject/publish/
unpublish): gửi duyệt lại từ rejected được hiểu là rejected -> draft -> pending_review trong một bước.
"""

from dataclasses import dataclass
from enum import StrEnum


class Action(StrEnum):
    SUBMIT = "submit"
    APPROVE = "approve"
    REJECT = "reject"
    PUBLISH = "publish"
    UNPUBLISH = "unpublish"


DRAFT, PENDING, APPROVED, REJECTED, PUBLISHED, UNPUBLISHED = (
    "draft",
    "pending_review",
    "approved",
    "rejected",
    "published",
    "unpublished",
)

TRANSITIONS: dict[Action, tuple[frozenset[str], str]] = {
    Action.SUBMIT: (frozenset({DRAFT, REJECTED}), PENDING),
    Action.APPROVE: (frozenset({PENDING}), APPROVED),
    Action.REJECT: (frozenset({PENDING}), REJECTED),
    Action.PUBLISH: (frozenset({APPROVED, UNPUBLISHED}), PUBLISHED),
    Action.UNPUBLISH: (frozenset({PUBLISHED}), UNPUBLISHED),
}

# Nghiệp vụ (OFFICER) gửi duyệt; Kiểm duyệt (APPROVER) quyết định; Admin làm được tất cả (SDD mục 3)
ACTION_ROLES: dict[Action, frozenset[str]] = {
    Action.SUBMIT: frozenset({"OFFICER", "ADMIN"}),
    Action.APPROVE: frozenset({"APPROVER", "ADMIN"}),
    Action.REJECT: frozenset({"APPROVER", "ADMIN"}),
    Action.PUBLISH: frozenset({"APPROVER", "ADMIN"}),
    Action.UNPUBLISH: frozenset({"APPROVER", "ADMIN"}),
}


@dataclass(frozen=True)
class Transition:
    action: Action
    from_status: str
    to_status: str


class InvalidTransition(Exception):
    def __init__(self, action: Action, current: str) -> None:
        super().__init__(f"Không thể '{action}' khi tài liệu đang ở trạng thái '{current}'")
        self.action = action
        self.current = current


def next_status(action: Action, current: str) -> Transition:
    allowed_from, target = TRANSITIONS[action]
    if current not in allowed_from:
        raise InvalidTransition(action, current)
    return Transition(action, current, target)


def allowed_actions(current: str, roles: frozenset[str]) -> list[str]:
    """Các action người dùng có thể thực hiện ở trạng thái hiện tại (cho React hiện nút)."""
    return [
        a.value for a, (allowed_from, _) in TRANSITIONS.items() if current in allowed_from and roles & ACTION_ROLES[a]
    ]
