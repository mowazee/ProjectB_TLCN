"""API borrowing (SDD 7.2, P2-07):
GET/POST /api/borrow-requests; POST /api/borrow-requests/{id}/{approve|reject|return}  (trùng thời gian 409)
GET/POST /api/storage-locations; PATCH /api/storage-locations/{id}                   (ghi chỉ Admin)
GET/PUT  /api/documents/{id}/storage-location   vị trí bản cứng của hồ sơ (bổ sung, cần cho UC-11)
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_feature
from app.modules.borrowing.application import locations, requests
from app.modules.borrowing.domain.rules import BorrowAction
from app.shared.http import page_params
from app.shared.pagination import Page, PageParams

router = APIRouter(tags=["borrowing"], dependencies=[Depends(require_feature("borrowing"))])


class LocationIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_.\-]+$")


class LocationPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = Field(default=None, min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_.\-]+$")


class LocationOut(BaseModel):
    id: int
    name: str
    code: str


class DocLocationIn(BaseModel):
    storage_location_id: int | None


class DocLocationOut(BaseModel):
    storage_location: LocationOut | None


class BorrowIn(BaseModel):
    document_id: uuid.UUID
    from_date: date
    to_date: date
    purpose: str | None = Field(default=None, max_length=1000)


class BorrowOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    document_title: str | None
    storage_location: str | None
    requester_id: uuid.UUID | None
    requester_name: str | None
    approver_id: uuid.UUID | None
    approver_name: str | None
    status: str
    from_date: date
    to_date: date
    purpose: str | None
    created_at: datetime
    is_overdue: bool = Field(description="Tính từ to_date, không lưu cột")


def _loc(loc: object) -> LocationOut:
    return LocationOut.model_validate(loc, from_attributes=True)


# ---------------------------------------------------------------- yêu cầu mượn
@router.get("/api/borrow-requests", response_model=Page[BorrowOut])
def list_requests(
    db: DbSession,
    principal: CurrentPrincipal,
    params: Annotated[PageParams, Depends(page_params)],
    status_: Annotated[Literal["pending", "approved", "rejected", "returned"] | None, Query(alias="status")] = None,
    document_id: uuid.UUID | None = None,
    overdue: bool = False,
    mine: bool = False,
) -> Page[BorrowOut]:
    items, total = requests.list_requests(
        db, principal, params, status=status_, document_id=document_id, overdue=overdue, mine=mine
    )
    return Page(
        items=[BorrowOut(**v.__dict__) for v in items], total=total, page=params.page, page_size=params.page_size
    )


@router.post("/api/borrow-requests", response_model=BorrowOut, status_code=status.HTTP_201_CREATED)
def create_request(data: BorrowIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> BorrowOut:
    v = requests.create_request(
        db,
        principal,
        document_id=data.document_id,
        from_date=data.from_date,
        to_date=data.to_date,
        purpose=data.purpose,
        ctx=ctx,
    )
    return BorrowOut(**v.__dict__)


@router.post("/api/borrow-requests/{request_id}/{action}", response_model=BorrowOut)
def act(request_id: uuid.UUID, action: BorrowAction, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> BorrowOut:
    return BorrowOut(**requests.act(db, principal, request_id, action, ctx).__dict__)


# ---------------------------------------------------------------- kho lưu trữ
@router.get("/api/storage-locations", response_model=list[LocationOut])
def list_locations(db: DbSession, principal: CurrentPrincipal) -> list[LocationOut]:
    return [_loc(x) for x in locations.list_locations(db)]


@router.post("/api/storage-locations", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
def create_location(data: LocationIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> LocationOut:
    return _loc(locations.create_location(db, principal, name=data.name, code=data.code, ctx=ctx))


@router.patch("/api/storage-locations/{location_id}", response_model=LocationOut)
def update_location(
    location_id: int, data: LocationPatch, db: DbSession, principal: CurrentPrincipal, ctx: Ctx
) -> LocationOut:
    return _loc(locations.update_location(db, principal, location_id, data.model_dump(exclude_unset=True), ctx))


@router.get("/api/documents/{document_id}/storage-location", response_model=DocLocationOut)
def get_doc_location(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> DocLocationOut:
    loc = locations.get_document_location(db, principal, document_id)
    return DocLocationOut(storage_location=_loc(loc) if loc else None)


@router.put("/api/documents/{document_id}/storage-location", response_model=DocLocationOut)
def set_doc_location(
    document_id: uuid.UUID, data: DocLocationIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx
) -> DocLocationOut:
    loc = locations.set_document_location(db, principal, document_id, data.storage_location_id, ctx)
    return DocLocationOut(storage_location=_loc(loc) if loc else None)
