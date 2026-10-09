"""API chạy lại OCR (SDD 7.2, P2-03):
POST /api/documents/{id}/reprocess  {ocr_profile: "print" | "handwriting"} -> 202 job_id
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_feature
from app.modules.ocr.application.reprocess import reprocess

router = APIRouter(
    prefix="/api/documents", tags=["handwriting"], dependencies=[Depends(require_feature("handwriting"))]
)


class ReprocessIn(BaseModel):
    ocr_profile: Literal["print", "handwriting"] = "handwriting"


class ReprocessOut(BaseModel):
    job_id: uuid.UUID
    status: str
    queue: str


@router.post("/{document_id}/reprocess", response_model=ReprocessOut, status_code=status.HTTP_202_ACCEPTED)
def reprocess_document(
    document_id: uuid.UUID, data: ReprocessIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx
) -> ReprocessOut:
    job = reprocess(db, principal, document_id, profile=data.ocr_profile, ctx=ctx)
    return ReprocessOut(job_id=job.id, status=str(job.status), queue=job.queue_name)
