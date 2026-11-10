"""FR-15 (SDD v0.13): tài liệu đi kèm, tải cả bộ; quyền theo tài liệu chính (D-11 sửa, D-02/D-09 xem)."""

import io
import uuid
import zipfile

from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.documents.application.purge import purge_expired
from app.modules.documents.infrastructure.models import Document, DocumentAttachment
from app.shared.db import utcnow
from app.shared.storage import get_storage
from tests.conftest import make_pdf, make_png, upload

DOCX = b"PK\x03\x04" + b"\x00" * 64


def _doc(seed, login, **extra):
    return upload(login("officer"), seed["category"].id, make_pdf(["Chính"]), "chinh.pdf", title="Hồ sơ", **extra)


def test_add_list_download_delete(seed, login, db):
    owner = login("officer")
    doc_id = _doc(seed, login).json()["document_id"]
    base = f"/api/documents/{doc_id}/attachments"
    r = owner.post(
        base, files=[("files", ("phu-luc.docx", DOCX, "x")), ("files", ("ghi-chu.txt", "Ghi chú".encode(), "x"))]
    )
    assert r.status_code == 201, r.text
    items = owner.get(base).json()
    assert [i["file_name"] for i in items] == ["phu-luc.docx", "ghi-chu.txt"] or len(items) == 2
    att = next(i for i in items if i["file_name"] == "ghi-chu.txt")
    dl = owner.get(f"{base}/{att['id']}/file")
    assert (
        dl.status_code == 200 and dl.content == "Ghi chú".encode() and "attachment" in dl.headers["content-disposition"]
    )
    # KDV cùng phòng ban xem được nhưng không xóa khi còn Nháp (D-11); phòng khác không xem
    assert login("approver").get(base).status_code == 200
    assert login("approver").delete(f"{base}/{att['id']}").status_code == 403
    assert login("officerb").get(base).status_code in (403, 404)
    assert owner.delete(f"{base}/{att['id']}").status_code == 204
    assert len(owner.get(base).json()) == 1
    db.rollback()
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.document_id == uuid.UUID(doc_id))).all())
    assert {"add_attachment", "download_attachment", "delete_attachment"} <= actions


def test_rejects_unsafe_types_and_limits(seed, login, monkeypatch):
    from app.shared.config import settings

    owner = login("officer")
    base = f"/api/documents/{_doc(seed, login).json()['document_id']}/attachments"
    for name, data in (("virus.exe", b"MZ\x90\x00"), ("gia.pdf", b"not pdf"), ("nen.zip", b"PK\x03\x04")):
        r = owner.post(base, files=[("files", (name, data, "x"))])
        assert r.status_code == 415 and name in r.json()["error"]["message"], name
    monkeypatch.setattr(settings, "MAX_ATTACHMENTS", 1)
    r = owner.post(base, files=[("files", ("a.txt", b"a", "x")), ("files", ("b.txt", b"b", "x"))])
    assert r.status_code == 422 and r.json()["error"]["code"] == "TOO_MANY_ATTACHMENTS"


def test_bundle_zip_and_upload_with_attachments(seed, login, db):
    owner = login("officer")
    r = _doc(seed, login)
    # tải lên kèm tài liệu đi kèm trong cùng request
    r = owner.post(
        "/api/documents",
        data={"category_id": str(seed["category"].id), "title": "Bộ hồ sơ"},
        files=[
            ("file", ("chinh.pdf", make_pdf(["Chính"]), "application/pdf")),
            ("attachments", ("anh.png", make_png(), "image/png")),
            ("attachments", ("anh.png", make_png("khác"), "image/png")),
        ],
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["document_id"]
    z = zipfile.ZipFile(io.BytesIO(owner.get(f"/api/documents/{doc_id}/bundle").content))
    assert sorted(z.namelist()) == ["chinh.pdf", "di-kem/anh (2).png", "di-kem/anh.png"]
    # một file đi kèm lỗi -> từ chối cả upload, không tạo tài liệu
    before = db.scalar(select(Document.id).where(Document.title == "Lỗi")) is None
    bad = owner.post(
        "/api/documents",
        data={"category_id": str(seed["category"].id), "title": "Lỗi"},
        files=[("file", ("c.pdf", make_pdf(["x"]), "x")), ("attachments", ("x.exe", b"MZ", "x"))],
    )
    assert bad.status_code == 415 and before
    db.rollback()
    assert db.scalar(select(Document.id).where(Document.title == "Lỗi")) is None


def test_keep_originals_on_merge_and_purge_removes_files(seed, login, db):
    owner = login("officer")
    r = owner.post(
        "/api/documents",
        data={"category_id": str(seed["category"].id), "keep_originals": "true"},
        files=[("files", ("a.png", make_png(), "x")), ("files", ("b.pdf", make_pdf(["b"]), "x"))],
    )
    assert r.status_code == 201, r.text
    doc_id = uuid.UUID(r.json()["document_id"])
    names = sorted(a["file_name"] for a in owner.get(f"/api/documents/{doc_id}/attachments").json())
    assert names == ["a.png", "b.pdf"]
    keys = list(db.scalars(select(DocumentAttachment.storage_key).where(DocumentAttachment.document_id == doc_id)))
    owner.delete(f"/api/documents/{doc_id}")
    db.rollback()
    doc = db.get(Document, doc_id)
    doc.deleted_at = utcnow().replace(year=2000)
    db.commit()
    assert purge_expired() == 1
    assert not any(get_storage().exists(k) for k in keys)
