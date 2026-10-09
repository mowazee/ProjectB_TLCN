"""API so sánh phiên bản (SDD 7.2, P2-06):
GET /api/documents/{id}/pages/{page}/versions                 danh sách version (0 = OCR thô)
GET /api/documents/{id}/pages/{page}/versions/diff?from=&to=  diff theo dòng/từ, chỉ đọc
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel

from app.modules.auth.presentation.deps import CurrentPrincipal, DbSession, require_feature
from app.modules.ocr.application import versions

router = APIRouter(prefix="/api/documents", tags=["versions"], dependencies=[Depends(require_feature("versions"))])
PageNo = Annotated[int, Path(ge=1)]


class VersionOut(BaseModel):
    version: int
    is_raw: bool
    edited_by: uuid.UUID | None
    edited_by_name: str | None
    edited_at: datetime | None
    engine_version: str | None
    chars: int


class WordOpOut(BaseModel):
    op: str
    old: str
    new: str


class HunkOut(BaseModel):
    op: str
    old_start: int
    new_start: int
    old_lines: list[str]
    new_lines: list[str]
    words: list[WordOpOut]


class DiffOut(BaseModel):
    from_version: int
    to_version: int
    identical: bool
    lines_added: int
    lines_removed: int
    hunks: list[HunkOut]


@router.get("/{document_id}/pages/{page_number}/versions", response_model=list[VersionOut])
def list_versions(document_id: uuid.UUID, page_number: PageNo, db: DbSession, principal: CurrentPrincipal) -> list:
    return [VersionOut(**v.__dict__) for v in versions.list_versions(db, principal, document_id, page_number)]


@router.get("/{document_id}/pages/{page_number}/versions/diff", response_model=DiffOut)
def diff(
    document_id: uuid.UUID,
    page_number: PageNo,
    db: DbSession,
    principal: CurrentPrincipal,
    from_version: Annotated[int, Query(alias="from", ge=0)],
    to_version: Annotated[int, Query(alias="to", ge=0)],
) -> DiffOut:
    d = versions.diff_versions(
        db, principal, document_id, page_number, from_version=from_version, to_version=to_version
    )
    return DiffOut(
        from_version=from_version,
        to_version=to_version,
        identical=d.identical,
        lines_added=d.lines_added,
        lines_removed=d.lines_removed,
        hunks=[
            HunkOut(
                op=h.op,
                old_start=h.old_start,
                new_start=h.new_start,
                old_lines=h.old_lines,
                new_lines=h.new_lines,
                words=[WordOpOut(**w.__dict__) for w in h.words],
            )
            for h in d.hunks
        ],
    )
