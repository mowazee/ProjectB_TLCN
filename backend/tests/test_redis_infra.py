"""Hạ tầng Redis/Celery cho production (ADR-AUTH-003, NFR-03): session store, rate limit, broker.

Chạy trên fakeredis mặc định; TEST_REDIS_URL để kiểm trên Redis thật (Docker)."""

import uuid

import redis

from app.shared.config import Settings
from app.shared.security.session import RedisSessionStore


def _store(ttl: int = 100) -> RedisSessionStore:
    return RedisSessionStore(redis.Redis.from_url("redis://unused"), ttl)


def test_touch_extends_user_session_set():
    # Tập session của user hết hạn trước session -> khóa tài khoản không thu hồi được session đang sống
    store = _store()
    uid = uuid.uuid4()
    s = store.create(uid)
    store.r.expire(store._ukey(uid), 5)
    store.touch(s.session_id)
    assert store.r.ttl(store._ukey(uid)) > 50
    assert store.revoke_user(uid) == 1
    assert store.get(s.session_id) is None


def test_touch_unknown_session_is_noop():
    store = _store()
    store.touch("khong-ton-tai")
    assert store.r.exists("sess:khong-ton-tai") == 0


def test_rate_limit_counter_always_has_ttl_and_window_not_extended():
    store = _store()
    assert store.incr("login:x", 900) == 1
    assert 0 < store.r.ttl("cnt:login:x") <= 900
    store.r.expire("cnt:login:x", 10)
    assert store.incr("login:x", 900) == 2
    assert store.r.ttl("cnt:login:x") <= 10  # lần đếm sau không kéo dài cửa sổ


def test_redis_down_returns_503(seed, login, monkeypatch):
    client = login("officer")
    from app.shared.security import session as session_mod

    def boom(*_a, **_k):
        raise redis.ConnectionError("down")

    monkeypatch.setattr(session_mod.RedisSessionStore, "get", boom)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


def test_broker_transport_options():
    s = Settings(_env_file=None, REDIS_URL="redis://redis:6379/0", JOB_STALE_SECONDS=1800)
    opts = s.broker_transport_options
    assert opts["visibility_timeout"] >= 2 * 1800
    pg = Settings(_env_file=None, CELERY_BROKER_URL="sqla+postgresql+psycopg://x@h/db")
    assert pg.broker_transport_options == {}


def test_cookie_secure_follows_env_unless_overridden():
    assert Settings(_env_file=None, APP_ENV="production").cookie_secure is True
    assert Settings(_env_file=None, APP_ENV="development").cookie_secure is False
    assert Settings(_env_file=None, APP_ENV="production", SESSION_COOKIE_SECURE=False).cookie_secure is False
