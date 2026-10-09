"""API extraction (SDD 7.2, P2-04):
GET  /api/documents/{id}/fields                xem trường (+ trạng thái job EXTRACT mới nhất)
PUT  /api/documents/{id}/fields/{field_name}   sửa/xác nhận
POST /api/documents/{id}/fields/extract        chạy lại trích xuất -> 202 job EXTRACT
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, Field

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_feature
from app.modules.extraction.application import fields

router = APIRouter(prefix="/api/documents", tags=["extraction"], dependencies=[Depends(require_feature("extraction"))])
FieldName = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{0,99}$")]


class FieldOut(BaseModel):
    field_name: str
    label: str
    field_value: str | None
    extracted_method: str | None
    is_verified: bool


class FieldsOut(BaseModel):
    items: list[FieldOut]
    job_id: uuid.UUID | None
    job_status: str | None


class FieldIn(BaseModel):
    field_value: str | None = Field(default=None, max_length=1000)
    is_verified: bool = True


class JobAccepted(BaseModel):
    job_id: uuid.UUID
    status: str


@router.get("/{document_id}/fields", response_model=FieldsOut)
def get_fields(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> FieldsOut:
    views, job = fields.list_fields(db, principal, document_id)
    return FieldsOut(
        items=[FieldOut(**v.__dict__) for v in views],
        job_id=job.id if job else None,
        job_status=str(job.status) if job else None,
    )


@router.post("/{document_id}/fields/extract", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def extract(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> JobAccepted:
    job = fields.request_extraction(db, principal, document_id, ctx)
    return JobAccepted(job_id=job.id, status=str(job.status))


@router.put("/{document_id}/fields/{field_name}", response_model=FieldOut)
def put_field(
    document_id: uuid.UUID, field_name: FieldName, data: FieldIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx
) -> FieldOut:
    v = fields.update_field(
        db, principal, document_id, field_name, value=data.field_value, is_verified=data.is_verified, ctx=ctx
    )
    return FieldOut(**v.__dict__)
