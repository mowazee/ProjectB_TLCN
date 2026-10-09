"""Event/after_commit chỉ chạy khi transaction gốc commit (không chạy khi RELEASE SAVEPOINT)."""

from app.shared.db import SessionLocal
from app.shared.events import after_commit


def test_after_commit_ignores_savepoints():
    calls: list[str] = []
    with SessionLocal() as s:
        s.begin()
        after_commit(s, lambda: calls.append("x"))
        with s.begin_nested():
            pass  # RELEASE SAVEPOINT
        assert calls == []
        nested = s.begin_nested()
        nested.rollback()  # rollback savepoint không hủy việc đang chờ
        s.commit()
    assert calls == ["x"]


def test_after_commit_dropped_on_rollback():
    calls: list[str] = []
    with SessionLocal() as s:
        s.begin()
        after_commit(s, lambda: calls.append("x"))
        s.rollback()
        s.begin()
        s.commit()
    assert calls == []
