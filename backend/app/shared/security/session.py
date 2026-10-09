"""Session store (ADR-AUTH-003, SDD mục 14).

Session ID ngẫu nhiên trong cookie HttpOnly; dữ liệu session có TTL trong Redis và thu hồi
được (đăng xuất, khóa tài khoản). Mỗi user có một tập session để thu hồi tất cả khi khóa.

- RedisSessionStore: bản chuẩn (production bắt buộc).
- MemorySessionStore: chỉ cho dev/test một tiến trình khi máy không chạy được Redis
  (ví dụ Windows Smart App Control chặn redis-server). Config chặn dùng ở production.
Cả hai cũng cung cấp bộ đếm có TTL cho rate limit đăng nhập.
"""

import json
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from app.shared.config import settings


@dataclass(frozen=True)
class SessionData:
    session_id: str
    user_id: uuid.UUID
    csrf_token: str


class SessionStore(Protocol):
    def create(self, user_id: uuid.UUID) -> SessionData: ...
    def get(self, session_id: str) -> SessionData | None: ...
    def touch(self, session_id: str) -> None: ...
    def revoke(self, session_id: str) -> None: ...
    def revoke_user(self, user_id: uuid.UUID) -> int: ...
    def incr(self, key: str, ttl_seconds: int) -> int: ...
    def reset(self, key: str) -> None: ...


def _new_session(user_id: uuid.UUID) -> SessionData:
    return SessionData(secrets.token_urlsafe(32), user_id, secrets.token_urlsafe(32))


class RedisSessionStore:
    def __init__(self, client: Any, ttl: int) -> None:
        self.r = client
        self.ttl = ttl

    def _key(self, sid: str) -> str:
        return f"sess:{sid}"

    def _ukey(self, uid: uuid.UUID) -> str:
        return f"user_sess:{uid}"

    def create(self, user_id: uuid.UUID) -> SessionData:
        s = _new_session(user_id)
        payload = json.dumps({"user_id": str(user_id), "csrf": s.csrf_token})
        pipe = self.r.pipeline()
        pipe.set(self._key(s.session_id), payload, ex=self.ttl)
        pipe.sadd(self._ukey(user_id), s.session_id)
        pipe.expire(self._ukey(user_id), self.ttl)
        pipe.execute()
        return s

    def get(self, session_id: str) -> SessionData | None:
        raw = self.r.get(self._key(session_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return SessionData(session_id, uuid.UUID(data["user_id"]), data["csrf"])

    def touch(self, session_id: str) -> None:
        # Gia hạn cả tập session của user: nếu tập hết hạn trước session thì khóa tài khoản
        # (revoke_user) không còn tìm thấy session đang sống để thu hồi.
        s = self.get(session_id)
        if s is None:
            return
        pipe = self.r.pipeline()
        pipe.expire(self._key(session_id), self.ttl)
        pipe.expire(self._ukey(s.user_id), self.ttl)
        pipe.execute()

    def revoke(self, session_id: str) -> None:
        s = self.get(session_id)
        self.r.delete(self._key(session_id))
        if s is not None:
            self.r.srem(self._ukey(s.user_id), session_id)

    def revoke_user(self, user_id: uuid.UUID) -> int:
        sids = [x.decode() if isinstance(x, bytes) else x for x in self.r.smembers(self._ukey(user_id))]
        if sids:
            self.r.delete(*[self._key(s) for s in sids])
        self.r.delete(self._ukey(user_id))
        return len(sids)

    def incr(self, key: str, ttl_seconds: int) -> int:
        # INCR + EXPIRE NX trong một transaction: không bao giờ để lại bộ đếm không TTL
        # (nếu thế, tài khoản bị khóa đăng nhập vĩnh viễn).
        k = f"cnt:{key}"
        pipe = self.r.pipeline()
        pipe.incr(k)
        pipe.expire(k, ttl_seconds, nx=True)
        n, _ = pipe.execute()
        return int(n)

    def reset(self, key: str) -> None:
        self.r.delete(f"cnt:{key}")


class MemorySessionStore:
    def __init__(self, ttl: int) -> None:
        self.ttl = ttl
        self._lock = threading.Lock()
        self._sessions: dict[str, tuple[SessionData, float]] = {}
        self._counters: dict[str, tuple[int, float]] = {}

    def create(self, user_id: uuid.UUID) -> SessionData:
        s = _new_session(user_id)
        with self._lock:
            self._sessions[s.session_id] = (s, time.monotonic() + self.ttl)
        return s

    def get(self, session_id: str) -> SessionData | None:
        with self._lock:
            item = self._sessions.get(session_id)
            if item is None:
                return None
            if item[1] < time.monotonic():
                del self._sessions[session_id]
                return None
            return item[0]

    def touch(self, session_id: str) -> None:
        with self._lock:
            if session_id in self._sessions:
                s, _ = self._sessions[session_id]
                self._sessions[session_id] = (s, time.monotonic() + self.ttl)

    def revoke(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def revoke_user(self, user_id: uuid.UUID) -> int:
        with self._lock:
            sids = [sid for sid, (s, _) in self._sessions.items() if s.user_id == user_id]
            for sid in sids:
                del self._sessions[sid]
            return len(sids)

    def incr(self, key: str, ttl_seconds: int) -> int:
        now = time.monotonic()
        with self._lock:
            n, exp = self._counters.get(key, (0, now + ttl_seconds))
            if exp < now:
                n, exp = 0, now + ttl_seconds
            self._counters[key] = (n + 1, exp)
            return n + 1

    def reset(self, key: str) -> None:
        with self._lock:
            self._counters.pop(key, None)


@lru_cache
def get_session_store() -> SessionStore:
    if settings.SESSION_BACKEND == "memory":
        return MemorySessionStore(settings.SESSION_TTL_SECONDS)
    return RedisSessionStore(redis_client(), settings.SESSION_TTL_SECONDS)


def redis_client() -> Any:
    """Client có timeout: Redis treo/mất kết nối thì request lỗi nhanh (503) thay vì treo worker uvicorn."""
    import redis
    from redis.backoff import ExponentialBackoff
    from redis.retry import Retry

    # Lệnh session chỉ mất vài ms: timeout ngắn + thử lại 1 lần -> Redis treo thì ~4s là trả 503
    # (mặc định redis-py 6 thử lại 3 lần, đo được 10s). Riêng khi container redis bị xóa/dừng hẳn, tra DNS
    # tên "redis" trong Docker mất thêm ~4s mỗi lần - không nằm trong các timeout này.
    return redis.Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=1.5,
        socket_timeout=2,
        health_check_interval=30,
        retry=Retry(ExponentialBackoff(cap=0.5, base=0.1), 1),
    )
