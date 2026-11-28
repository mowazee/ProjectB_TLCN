"""FR-21 (v0.16): Hướng dẫn sử dụng - Admin tải lên/sửa/xóa tài liệu hướng dẫn, mọi người dùng xem."""

import uuid

from sqlalchemy import select

from app.modules.audit.infrastructure.models import AuditLog
from app.modules.guides.infrastructure.models import GuideDocument
from app.shared.storage import get_storage
from tests.conftest import make_pdf

DOCX = b"PK\x03\x04" + b"\x00" * 64


def _upload(client, name: str, data: bytes, title: str | None = None, description: str | None = None):
    form = {k: v for k, v in {"title": title, "description": description}.items() if v is not None}
    return client.post("/api/guides", data=form, files={"file": (name, data, "application/octet-stream")})


def test_admin_uploads_and_everyone_views(seed, login, db):
    admin, officer, viewer = login("admin"), login("officer"), login("approver")
    r = _upload(admin, "huong-dan-tai-len.pdf", make_pdf(["Hướng dẫn"]), title="Hướng dẫn tải lên tài liệu")
    assert r.status_code == 201, r.text
    pdf = r.json()
    assert pdf["inline"] is True and pdf["uploaded_by"] and pdf["file_name"] == "huong-dan-tai-len.pdf"
    docx = _upload(admin, "Quy trình duyệt.docx", DOCX).json()
    assert docx["title"] == "Quy trình duyệt" and docx["inline"] is False  # tiêu đề trống -> tên file

    for c in (officer, viewer):  # mọi người dùng đã đăng nhập xem được
        page = c.get("/api/guides").json()
        assert page["total"] == 2 and page["items"][0]["id"] == docx["id"]  # mới nhất trước
    assert {x["id"] for x in officer.get("/api/guides", params={"q": "tải lên"}).json()["items"]} == {pdf["id"]}

    f = viewer.get(f"/api/guides/{pdf['id']}/file")
    assert f.status_code == 200 and f.headers["content-type"] == "application/pdf"
    assert f.headers["content-disposition"].startswith("inline")
    assert viewer.get(f"/api/guides/{docx['id']}/file").headers["content-disposition"].startswith("attachment")
    db.rollback()
    assert {a for (a,) in db.execute(select(AuditLog.action).where(AuditLog.module == "guides"))} == {"upload_guide"}


def test_only_admin_manages_and_files_are_validated(seed, login, db):
    admin, officer = login("admin"), login("officer")
    assert _upload(officer, "a.pdf", make_pdf(["a"])).status_code == 403
    r = _upload(admin, "virus.exe", b"MZ\x90\x00")
    assert r.status_code == 415
    r = _upload(admin, "gia.pdf", b"not a pdf at all")
    assert r.status_code == 415 and r.json()["error"]["code"] == "EXTENSION_MISMATCH"
    assert _upload(admin, "rong.pdf", b"").status_code == 422

    g = _upload(admin, "a.pdf", make_pdf(["a"]), title="Cũ").json()
    assert officer.patch(f"/api/guides/{g['id']}", json={"title": "X"}).status_code == 403
    r = admin.patch(f"/api/guides/{g['id']}", json={"title": "Hướng dẫn mới", "description": "Bản 2"})
    assert r.json()["title"] == "Hướng dẫn mới" and r.json()["description"] == "Bản 2"

    db.rollback()
    key = db.get(GuideDocument, uuid.UUID(g["id"])).storage_key
    assert get_storage().exists(key)
    assert officer.delete(f"/api/guides/{g['id']}").status_code == 403
    assert admin.delete(f"/api/guides/{g['id']}").status_code == 204
    assert not get_storage().exists(key)  # xóa luôn file trong kho
    assert admin.get(f"/api/guides/{g['id']}/file").status_code == 404
    assert login("officer").get("/api/guides").json()["total"] == 0
