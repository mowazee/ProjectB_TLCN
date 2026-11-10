"""v0.15: Nhật ký hệ thống lọc theo tên người dùng, tên tài liệu, hành động gần đúng; dọn nhật ký sót của tài liệu đã xóa."""

import uuid

from sqlalchemy import func, select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.documents.application.purge import purge_expired
from tests.conftest import make_pdf, upload


def test_audit_filters_by_user_document_and_partial_action(seed, login):
    officer, admin = login("officer"), login("admin")
    upload(officer, seed["category"].id, make_pdf(["a"]), "a.pdf", title="Quyết định bổ nhiệm")
    upload(officer, seed["category"].id, make_pdf(["b"]), "b.pdf", title="Công văn khác")

    def items(**params):
        r = admin.get("/api/audit", params=params)
        assert r.status_code == 200, r.text
        return r.json()["items"]

    by_doc = items(document="bổ nhiệm")
    assert by_doc and all(x["action"] == "upload_document" for x in by_doc) and len(by_doc) == 1
    assert by_doc[0]["document_title"] == "Quyết định bổ nhiệm"  # cột Tên tài liệu
    username = seed["officer"].username
    assert {x["user_id"] for x in items(user=username[:3])} == {str(seed["officer"].id)}
    assert items(user="khong-co-ai-ten-nay") == []
    assert len(items(action="upload")) >= 2  # gần đúng: upload -> upload_document
    assert items(user="nh") is not None  # không còn lỗi 422 khi gõ dở


def test_purge_removes_orphaned_logs_of_old_purged_documents(seed, login, db):
    c = login("officer")
    alive = upload(c, seed["category"].id, make_pdf(["a"]), "a.pdf").json()["document_id"]
    gone = str(uuid.uuid4())
    db.add(AuditLog(action="legacy", module="documents", entity_type="document", entity_id=alive))  # tài liệu còn
    db.add(AuditLog(action="purge", module="documents", entity_type="document", entity_id=gone))
    db.add(AuditLog(action="update_document", module="documents", entity_type="document", entity_id=gone))
    db.add(AuditLog(action="update_category", module="categories", entity_type="category", entity_id="1"))
    db.commit()
    cats = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_type == "category"))
    purge_expired()
    db.rollback()
    left = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == gone))
    assert left == 0
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "legacy")) == 1
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_type == "category")) == cats
