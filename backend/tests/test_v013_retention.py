"""FR-14 (SDD v0.13): Admin cấu hình thời gian lưu thùng rác và audit log; beat dọn audit quá hạn."""

import uuid
from datetime import timedelta

from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.documents.application.purge import purge_expired
from app.modules.documents.infrastructure.models import Document
from app.modules.settings.application.retention import purge_audit
from app.shared.db import utcnow
from tests.conftest import make_pdf, upload


def test_settings_admin_only_and_validated(seed, login):
    admin = login("admin")
    got = admin.get("/api/admin/settings").json()
    assert got == {"trash_retention_days": 30, "audit_retention_days": 365}
    assert login("officer").get("/api/admin/settings").status_code == 403
    assert login("officer").put("/api/admin/settings", json={"trash_retention_days": 5}).status_code == 403
    for body in ({"audit_retention_days": 179}, {"audit_retention_days": 3651}, {"trash_retention_days": 0}):
        r = admin.put("/api/admin/settings", json=body)
        assert r.status_code == 422, body
    r = admin.put("/api/admin/settings", json={"trash_retention_days": 7, "audit_retention_days": 180})
    assert r.status_code == 200 and r.json() == {"trash_retention_days": 7, "audit_retention_days": 180}
    assert admin.get("/api/admin/settings").json()["trash_retention_days"] == 7


def test_trash_retention_applies_to_restore_and_purge(seed, login, db):
    admin, officer = login("admin"), login("officer")
    doc_id = upload(officer, seed["category"].id, make_pdf(["a"]), "a.pdf").json()["document_id"]
    officer.delete(f"/api/documents/{doc_id}")
    doc = db.get(Document, uuid.UUID(doc_id))
    doc.deleted_at = utcnow() - timedelta(days=10)
    db.commit()
    trash = officer.get("/api/documents", params={"lifecycle_status": "deleted"}).json()["items"]
    assert trash and trash[0]["restore_deadline"]  # mặc định 30 ngày: còn hạn
    admin.put("/api/admin/settings", json={"trash_retention_days": 7})
    r = officer.post(f"/api/documents/{doc_id}/restore")
    assert r.status_code == 410
    assert purge_expired() == 1


def test_purge_audit_keeps_recent_and_logs_itself(seed, login, db):
    admin = login("admin")
    admin.put("/api/admin/settings", json={"audit_retention_days": 180})
    db.add(AuditLog(action="old_action", module="test", created_at=utcnow() - timedelta(days=181)))
    db.add(AuditLog(action="recent_action", module="test", created_at=utcnow() - timedelta(days=10)))
    db.commit()
    assert purge_audit() >= 1
    db.expire_all()
    actions = set(db.scalars(select(AuditLog.action)).all())
    assert "old_action" not in actions and "recent_action" in actions
    assert {"purge_audit", "update_settings"} <= actions
