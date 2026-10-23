"""P2-08 + D-10: nhập hàng loạt với Danh mục gợi ý; metadata.csv ghi đè danh mục (mã) và số hiệu từng file."""

import io
import uuid
import zipfile

from sqlalchemy import select

from app.modules.categories.application.manage import unclassified_id
from app.modules.documents.infrastructure.models import Document
from app.modules.notifications.infrastructure.models import Notification
from tests.conftest import make_png, run_all_jobs
from tests.test_p2_extraction_classification import HOP_DONG, _lines
from tests.test_v09_auto_category import _train

F = "imports,classification,notifications"
CSV = (
    "file_name,title,category,document_code\n"
    "b.png,Hợp đồng số 12,hop-dong,12/2026/HĐMB\n"  # mã không phân biệt hoa/thường
    "c.png,,KHONG-CO,\n"
    "d.png,,CHUA-PHAN-LOAI,\n"
)


def _zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _start(client, data: dict[str, str], archive: bytes):
    return client.post("/api/imports", data=data, files=[("files", ("lo.zip", archive, "application/zip"))])


def _notes(db, type_: str):
    db.rollback()
    return db.scalars(select(Notification).where(Notification.type == type_)).all()


def test_auto_mode_batch_with_metadata_overrides(seed, login, db, fake_engine, enqueued):
    c = login("officer", features=F)
    _train(c, fake_engine, enqueued, seed)  # 2 tài liệu mẫu do người dùng chọn danh mục
    unclassified_id(db)
    db.commit()
    fake_engine.lines = _lines(HOP_DONG[:1] + HOP_DONG[2:])
    archive = _zip({n: make_png() for n in ("a.png", "b.png", "c.png", "d.png")} | {"metadata.csv": CSV.encode()})
    r = _start(c, {"category_mode": "auto"}, archive)
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    run_all_jobs(enqueued)  # nhập lô -> OCR từng tài liệu -> CLASSIFY

    report = {f["name"].removeprefix("lo.zip/"): f for f in c.get(f"/api/imports/{job_id}").json()["files"]}
    assert report["a.png"]["status"] == "imported"
    assert report["a.png"]["category_name"] == "Hợp đồng" and report["a.png"]["category_source"] == "auto"
    # engine giả trả cùng văn bản hợp đồng cho mọi file: b.png phải gán đúng Hợp đồng để không thành mẫu huấn luyện sai
    assert report["b.png"]["category_name"] == "Hợp đồng" and report["b.png"]["category_source"] == "user"
    assert report["c.png"]["status"] == "error" and report["c.png"]["code"] == "CATEGORY_NOT_FOUND"
    assert report["d.png"]["status"] == "error" and report["d.png"]["code"] == "CATEGORY_SYSTEM"

    db.rollback()
    b = db.get(Document, uuid.UUID(report["b.png"]["document_id"]))
    assert (b.title, b.document_code, b.category_id) == ("Hợp đồng số 12", "12/2026/HĐMB", seed["category"].id)

    (done,) = _notes(db, "import.done")
    assert done.user_id == seed["officer"].id and done.link_url == f"/imports/{job_id}"
    assert "2/4 file đã nhập, 2 lỗi" in done.message and "tự chọn sau khi OCR" in done.message
    assert _notes(db, "classify.auto") == []  # không thông báo từng tài liệu của lô


def test_import_category_validation(seed, login, db, fake_engine, enqueued):
    archive = _zip({"a.png": make_png()})
    off = login("officer", features="imports")
    r = _start(off, {"category_mode": "auto"}, archive)
    assert r.status_code == 422 and r.json()["error"]["code"] == "CATEGORY_MODE_UNAVAILABLE"
    r = _start(off, {}, archive)
    assert r.status_code == 422 and r.json()["error"]["code"] == "CATEGORY_REQUIRED"

    c = login("officer", features=F)
    sys_id = unclassified_id(db)
    db.commit()
    r = _start(c, {"category_id": str(sys_id)}, archive)
    assert r.status_code == 422 and r.json()["error"]["code"] == "CATEGORY_SYSTEM"


def test_user_mode_batch_keeps_category_and_document_code_too_long(seed, login, db, fake_engine, enqueued):
    c = login("officer", features=F)
    csv = f"file_name,document_code\nb.png,{'x' * 101}\n"
    archive = _zip({"a.png": make_png(), "b.png": make_png(), "metadata.csv": csv.encode()})
    job_id = _start(c, {"category_id": str(seed["category"].id)}, archive).json()["job_id"]
    run_all_jobs(enqueued)
    report = {f["name"].removeprefix("lo.zip/"): f for f in c.get(f"/api/imports/{job_id}").json()["files"]}
    assert report["a.png"]["category_name"] == "Hợp đồng" and report["a.png"]["category_source"] == "user"
    assert report["b.png"]["code"] == "DOCUMENT_CODE_TOO_LONG"
    (done,) = _notes(db, "import.done")
    assert "tự chọn" not in done.message


def test_single_upload_still_notifies_auto_classification(seed, login, db, fake_engine, enqueued):
    """Chỉ tài liệu của lô mới bỏ thông báo từng tài liệu; tải lên lẻ vẫn báo như D-10."""
    c = login("officer", features=F)
    _train(c, fake_engine, enqueued, seed)
    fake_engine.lines = _lines(HOP_DONG[:1] + HOP_DONG[2:])
    r = c.post("/api/documents", data={"category_mode": "auto"}, files={"file": ("x.png", make_png(), "image/png")})
    assert r.status_code == 201
    run_all_jobs(enqueued)
    assert len(_notes(db, "classify.auto")) == 1
