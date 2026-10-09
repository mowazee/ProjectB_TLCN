"""UC-23 Bulk import (P2-08), include UC-01 cho từng file.

API: kiểm quyền/giới hạn -> lưu file thô vào vùng tạm private (imports/<batch>/) -> job BULK_IMPORT.
Worker: giải nén an toàn -> mỗi file đi qua đúng luồng upload của lõi (kiểm tra như FR-03, tạo job
OCR riêng) -> báo cáo từng file trong processing_jobs.result. File lỗi không làm hỏng cả lô.

Chạy lại không tạo trùng: trạng thái từng file nằm trong job.result và được ghi CÙNG transaction
với tài liệu tạo ra (create_document_from_bytes commit cả hai), nên file đã nhập sẽ được bỏ qua.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any, BinaryIO

from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.categories.application import manage as categories
from app.modules.documents.application.upload import create_document_from_bytes
from app.modules.imports.domain.archive import ArchiveError, Budget, expand_batch, parse_metadata
from app.modules.jobs.application import queries as jobs
from app.modules.jobs.application.create import create_job
from app.modules.jobs.domain.model import JobError
from app.modules.users.application.queries import get_principal
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.errors import AppError, NotFoundError, PayloadTooLargeError, PermissionDeniedError, UnprocessableError
from app.shared.storage import get_storage

logger = logging.getLogger(__name__)
KIND = "BULK_IMPORT"
PREFIX = "imports"


@dataclass
class StagedFile:
    name: str
    stream: BinaryIO


def _budget() -> Budget:
    return Budget(settings.IMPORT_MAX_FILES, settings.IMPORT_MAX_TOTAL_MB * 1024 * 1024, settings.IMPORT_MAX_ZIP_RATIO)


def start_import(
    db: Session,
    principal: Principal,
    *,
    files: list[StagedFile],
    metadata: StagedFile | None,
    category_id: int,
    is_handwritten: bool,
    ctx: RequestContext,
) -> Any:
    if not principal.has_any("OFFICER", "ADMIN"):
        raise PermissionDeniedError("Bạn không có quyền bulk import")
    if not files:
        raise UnprocessableError("Chưa chọn file", fields={"files": "required"})
    if len(files) > settings.IMPORT_MAX_FILES:
        raise PayloadTooLargeError(f"Lô vượt quá {settings.IMPORT_MAX_FILES} file", code="TOO_MANY_FILES")
    categories.require_active(db, category_id)
    batch = uuid.uuid4().hex
    storage = get_storage()
    limit = settings.IMPORT_MAX_TOTAL_MB * 1024 * 1024
    total = 0
    staged: list[dict[str, str]] = []
    try:
        for i, f in enumerate([*files, *([metadata] if metadata else [])]):
            data = bytearray()
            while chunk := f.stream.read(1024 * 1024):
                data.extend(chunk)
                total += len(chunk)
                if total > limit:
                    raise PayloadTooLargeError("Tổng dung lượng lô vượt giới hạn", code="BATCH_TOO_LARGE")
            name = "metadata.csv" if (metadata is not None and f is metadata) else (f.name or f"file{i}")
            key = f"{PREFIX}/{batch}/{i:04d}"
            storage.save_bytes(key, bytes(data))
            staged.append({"key": key, "name": name})
        job = create_job(
            db,
            kind=KIND,
            document_id=None,
            queue="default",
            payload={
                "user_id": str(principal.id),
                "category_id": category_id,
                "is_handwritten": is_handwritten,
                "batch": batch,
                "files": staged,
            },
        )
        record(
            db,
            action="bulk_import",
            module="imports",
            actor_id=principal.id,
            ctx=ctx,
            entity_type="job",
            entity_id=job.id,
            after={"files": [s["name"] for s in staged], "category_id": category_id, "bytes": total},
        )
        db.commit()
    except Exception:
        db.rollback()
        storage.delete_prefix(f"{PREFIX}/{batch}")
        raise
    return job


def _unique_keys(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n}#{seen[n]}")
    return out


def run_import(ctx: Any) -> None:
    db: Session = ctx.db
    p = ctx.payload
    principal = get_principal(db, uuid.UUID(p["user_id"]))
    if principal is None:
        raise JobError("USER_INACTIVE", "Người tạo lô không còn hoạt động")
    storage = get_storage()
    try:
        raw = [(f["name"], storage.read_bytes(f["key"])) for f in p.get("files", [])]
    except AppError as exc:
        raise JobError("FILE_NOT_FOUND", "Không đọc được file của lô") from exc
    try:
        expanded = expand_batch(raw, _budget())
        meta = parse_metadata(expanded.metadata)
    except ArchiveError as exc:
        raise JobError(exc.code, str(exc)) from exc

    job_ctx = RequestContext(ip_address=None, user_agent="bulk-import", request_id=f"import:{ctx.job_id}")
    keys = _unique_keys([e.name for e in expanded.entries])
    state: dict[str, dict[str, Any]] = dict((ctx.job.result or {}).get("files_state", {}))
    total = len(expanded.entries)

    def save(key: str, value: dict[str, Any]) -> None:
        state[key] = value
        ctx.set_result({"files_state": dict(state), "total": total})

    for n, (key, entry) in enumerate(zip(keys, expanded.entries, strict=True), start=1):
        if state.get(key, {}).get("status") in ("imported", "importing"):
            continue  # đã nhập ở lần chạy trước
        if entry.error_code:
            save(key, {"status": "error", "code": entry.error_code, "message": entry.error_message})
        else:
            # Đánh dấu "importing" trong cùng transaction tạo tài liệu: lỗi thì rollback cả hai
            save(key, {"status": "importing"})
            try:
                doc, ocr_job = create_document_from_bytes(
                    db,
                    principal,
                    data=entry.data or b"",
                    filename=entry.filename,
                    title=meta.get(entry.filename.lower(), {}).get("title") or None,
                    category_id=int(p["category_id"]),
                    is_handwritten=bool(p.get("is_handwritten")),
                    ctx=job_ctx,
                    audit_action="import_document",
                )
            except AppError as exc:
                state.pop(key, None)  # đã bị rollback cùng transaction
                save(key, {"status": "error", "code": exc.code, "message": exc.message})
            else:
                save(key, {"status": "imported", "document_id": str(doc.id), "job_id": str(ocr_job.id)})
        ctx.progress(round(n * 100 / max(total, 1)))

    imported = sum(1 for v in state.values() if v.get("status") in ("imported", "importing"))
    ctx.set_result(
        {
            "files_state": dict(state),
            "total": total,
            "imported": imported,
            "errors": sum(1 for v in state.values() if v.get("status") == "error"),
            "order": keys,
        }
    )
    if p.get("batch"):
        storage.delete_prefix(f"{PREFIX}/{p['batch']}")  # xong lô: xóa vùng tạm


def get_report(db: Session, principal: Principal, job_id: uuid.UUID) -> dict[str, Any]:
    job = jobs.get_job(db, job_id)
    if job.kind != KIND:
        raise NotFoundError("Không tìm thấy lô import")
    if not principal.is_admin and (job.payload or {}).get("user_id") != str(principal.id):
        raise PermissionDeniedError("Bạn không có quyền xem lô import này")
    result = job.result or {}
    state = result.get("files_state", {})
    order = result.get("order") or list(state)
    files = [
        {"name": k, **{kk: vv for kk, vv in state[k].items() if kk != "status"}, "status": state[k].get("status")}
        for k in order
        if k in state
    ]
    return {
        "job": job,
        "total": result.get("total", len((job.payload or {}).get("files", []))),
        "imported": result.get("imported", sum(1 for f in files if f["status"] in ("imported", "importing"))),
        "errors": result.get("errors", sum(1 for f in files if f["status"] == "error")),
        "files": files,
    }
