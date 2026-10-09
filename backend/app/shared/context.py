"""Principal (người dùng đã xác thực) và RequestContext dùng chung giữa các lớp.

Principal là dataclass thuần để domain/application không phụ thuộc ORM hay FastAPI.
"""

import uuid
from dataclasses import dataclass, field

ADMIN, OFFICER, APPROVER = "ADMIN", "OFFICER", "APPROVER"


@dataclass(frozen=True)
class Principal:
    id: uuid.UUID
    username: str
    full_name: str
    department_id: int | None
    roles: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_admin(self) -> bool:
        return ADMIN in self.roles

    def has_any(self, *roles: str) -> bool:
        """Admin kế thừa quyền của mọi vai trò (SDD mục 3)."""
        return self.is_admin or bool(self.roles & set(roles))


@dataclass(frozen=True)
class RequestContext:
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None


SYSTEM_CONTEXT = RequestContext(user_agent="system")
