"""UC-12 So sánh phiên bản (P2-06): version 0 = OCR thô, 1..n = ocr_corrections. Chỉ đọc."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.documents.application import queries as documents
from app.modules.ocr.application.queries import get_correction, latest_result, list_corrections
from app.modules.ocr.domain.diff import DiffResult, diff_text
from app.modules.users.application.queries import display_names
from app.shared.context import Principal
from app.shared.errors import NotFoundError, UnprocessableError


@dataclass
class VersionInfo:
    version: int
    is_raw: bool
    edited_by: uuid.UUID | None
    edited_by_name: str | None
    edited_at: datetime | None
    engine_version: str | None
    chars: int


def list_versions(db: Session, principal: Principal, document_id: uuid.UUID, page_number: int) -> list[VersionInfo]:
    documents.ensure_can_view(db, principal, document_id)
    page = documents.get_page(db, document_id, page_number)
    raw = latest_result(db, page.id)
    corrections = list_corrections(db, page.id)
    names = display_names(db, {c.edited_by for c in corrections if c.edited_by})
    out = []
    if raw is not None:
        out.append(VersionInfo(0, True, None, None, raw.created_at, raw.engine_version, len(raw.raw_text)))
    for c in corrections:
        out.append(
            VersionInfo(
                c.version,
                False,
                c.edited_by,
                names.get(c.edited_by) if c.edited_by else None,
                c.edited_at,
                None,
                len(c.corrected_text),
            )
        )
    return out


def _text_of(db: Session, page_id: uuid.UUID, version: int) -> str:
    if version == 0:
        raw = latest_result(db, page_id)
        if raw is None:
            raise NotFoundError("Trang chưa có kết quả OCR")
        return raw.raw_text
    c = get_correction(db, page_id, version)
    if c is None:
        raise NotFoundError(f"Không có version {version}")
    return c.corrected_text


def diff_versions(
    db: Session, principal: Principal, document_id: uuid.UUID, page_number: int, *, from_version: int, to_version: int
) -> DiffResult:
    if from_version < 0 or to_version < 0:
        raise UnprocessableError("Version không hợp lệ", fields={"from": "invalid"})
    documents.ensure_can_view(db, principal, document_id)
    page = documents.get_page(db, document_id, page_number)
    return diff_text(_text_of(db, page.id, from_version), _text_of(db, page.id, to_version))
