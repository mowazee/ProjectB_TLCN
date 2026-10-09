"""P2-08 bulk import (UC-23): lô có file lỗi, ZIP độc hại, không trùng khi chạy lại."""

import io
import zipfile
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.modules.documents.infrastructure.models import Document
from app.modules.imports.domain.archive import ArchiveError, Budget, expand_batch, safe_member_name
from app.modules.jobs.application.runner import run_job
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.shared.config import settings
from tests.conftest import make_pdf, make_png

F = "imports"


def _zip(entries: dict[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression) as zf:
        for name, data in entries.items():
            zf.writestr(zipfile.ZipInfo(name), data, compress_type=compression)
    return buf.getvalue()


def test_safe_names_and_budget():
    assert safe_member_name("a/b.pdf") == "a/b.pdf"
    assert safe_member_name("../x.pdf") is None and safe_member_name("/etc/x") is None
    assert safe_member_name("C:/x.pdf") is None and safe_member_name("a\\..\\b") is None
    with pytest.raises(ArchiveError) as e:
        expand_batch([("a.pdf", b"x"), ("b.pdf", b"y")], Budget(1, 10**6, 100))
    assert e.value.code == "TOO_MANY_FILES"
    bomb = _zip({"big.pdf": b"0" * 5_000_000})
    out = expand_batch([("lo.zip", bomb)], Budget(10, 10**8, 100))
    assert out.entries[0].error_code == "ZIP_BOMB_SUSPECTED" and out.entries[0].data is None


def test_import_batch_report_and_idempotent_rerun(seed, login, db, enqueued):
    c = login("officer", features=F)
    archive = _zip(
        {
            "hop-dong/a.pdf": make_pdf(["Hop dong A"]),
            "b.png": make_png(),
            "../evil.pdf": make_pdf(["x"]),
            "gia.pdf": make_png(),  # sai phần mở rộng -> lỗi như FR-03
            "long.zip": b"PK",
            "metadata.csv": "file_name,title\na.pdf,Hợp đồng A (từ CSV)\n".encode(),
        }
    )
    r = c.post(
        "/api/imports",
        data={"category_id": str(seed["category"].id)},
        files=[("files", ("lo1.zip", archive, "application/zip")), ("files", ("c.jpg", b"not-jpg", "image/jpeg"))],
    )
    assert r.status_code == 202, r.text
    job_id = UUID(r.json()["job_id"])
    assert enqueued == [(job_id, "default")]
    enqueued.clear()
    assert run_job(job_id).value == "completed"

    rep = c.get(f"/api/imports/{job_id}").json()
    assert rep["status"] == "completed" and rep["total"] == 6 and rep["imported"] == 2 and rep["errors"] == 4
    by = {f["name"]: f for f in rep["files"]}
    assert by["lo1.zip/hop-dong/a.pdf"]["status"] == "imported"
    assert by["lo1.zip/gia.pdf"]["code"] == "EXTENSION_MISMATCH"
    assert by["lo1.zip/long.zip"]["code"] == "NESTED_ARCHIVE"
    assert any(f["code"] == "UNSAFE_PATH" for f in rep["files"])
    assert by["c.jpg"]["status"] == "error"
    assert len(enqueued) == 2 and all(q == "ocr" for _, q in enqueued)  # mỗi tài liệu một job OCR
    db.rollback()
    titles = set(db.scalars(select(Document.title)).all())
    assert "Hợp đồng A (từ CSV)" in titles and "b" in titles

    # Chạy lại lô: không tạo tài liệu trùng
    job = db.get(ProcessingJob, job_id)
    job.status, job.attempt = "queued", 0
    db.commit()
    assert run_job(job_id).value in ("completed", "failed")
    db.rollback()
    assert db.scalar(select(func.count(Document.id))) == 2


def test_import_permissions_and_limits(seed, login, monkeypatch):
    approver = login("approver", features=F)
    files = [("files", ("a.pdf", make_pdf(["a"]), "application/pdf"))]
    assert approver.post("/api/imports", data={"category_id": str(seed["category"].id)}, files=files).status_code == 403
    officer = login("officer", features=F)
    monkeypatch.setattr(settings, "IMPORT_MAX_FILES", 1)
    two = files + [("files", ("b.pdf", make_pdf(["b"]), "application/pdf"))]
    r = officer.post("/api/imports", data={"category_id": str(seed["category"].id)}, files=two)
    assert r.status_code == 413 and r.json()["error"]["code"] == "TOO_MANY_FILES"
    job_id = officer.post("/api/imports", data={"category_id": str(seed["category"].id)}, files=files).json()["job_id"]
    assert login("officerb", features=F).get(f"/api/imports/{job_id}").status_code == 403
    assert login("admin", features=F).get(f"/api/imports/{job_id}").status_code == 200
    assert login("officer", features="").post("/api/imports", data={}, files=files).status_code == 404
