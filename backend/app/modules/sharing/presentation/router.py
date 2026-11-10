"""API chia sẻ ra ngoài (SDD v0.13 mục 7.1, FR-18, D-13).

Nội bộ (đăng nhập): GET/POST /api/documents/{id}/external-shares; DELETE /api/external-shares/{id}
Công khai (không đăng nhập, NFR-02): /api/public/shares/{token} [/otp, /verify, /pages/{n}/image, /file,
/attachments/{id}, /bundle] - phiên xem là cookie riêng của link (Path theo token), không dùng session người dùng.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Path, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, check_origin
from app.modules.documents.application import attachments as attachments_app
from app.modules.documents.application import queries as documents
from app.modules.sharing.application import links
from app.shared.config import settings
from app.shared.email import email_enabled
from app.shared.errors import NotFoundError, PermissionDeniedError
from app.shared.storage import get_storage

router = APIRouter(tags=["sharing"])
public_router = APIRouter(prefix="/api/public/shares", tags=["sharing-public"])

VIEW_COOKIE = "share_view"
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
}


class LinkIn(BaseModel):
    recipient_email: str = Field(max_length=255)
    expires_in_hours: int = Field(default=24, description="1 đến EXTERNAL_SHARE_MAX_HOURS (24)")
    allow_download: bool = False


class LinkOut(BaseModel):
    id: uuid.UUID
    recipient_email: str
    allow_download: bool
    expires_at: datetime
    revoked_at: datetime | None
    email_status: str
    created_by: str | None
    created_at: datetime
    last_accessed_at: datetime | None
    access_count: int
    status: str


class LinksOut(BaseModel):
    enabled: bool = Field(description="Đã cấu hình SMTP (chưa thì ẩn tính năng)")
    max_hours: int
    items: list[LinkOut]


class LinkCreated(BaseModel):
    link: LinkOut
    url: str = Field(description="Chỉ trả một lần; đã gửi qua email cho người nhận")


@router.get("/api/documents/{document_id}/external-shares", response_model=LinksOut)
def list_links(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> LinksOut:
    items = [LinkOut(**v.__dict__) for v in links.list_links(db, principal, document_id)]
    return LinksOut(enabled=email_enabled(), max_hours=settings.EXTERNAL_SHARE_MAX_HOURS, items=items)


@router.post(
    "/api/documents/{document_id}/external-shares", response_model=LinkCreated, status_code=status.HTTP_201_CREATED
)
def create_link(
    document_id: uuid.UUID, data: LinkIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx
) -> LinkCreated:
    view, url = links.create_link(
        db,
        principal,
        document_id,
        recipient_email=data.recipient_email,
        expires_in_hours=data.expires_in_hours,
        allow_download=data.allow_download,
        ctx=ctx,
    )
    return LinkCreated(link=LinkOut(**view.__dict__), url=url)


@router.delete("/api/external-shares/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_link(link_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> Response:
    links.revoke_link(db, principal, link_id, ctx)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- công khai
Token = Annotated[str, Path(min_length=20, max_length=100)]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


class PublicPage(BaseModel):
    page_number: int
    width: int
    height: int


class PublicAttachment(BaseModel):
    id: uuid.UUID
    file_name: str
    bytes: int


class PublicShareOut(BaseModel):
    title: str
    expires_at: datetime
    recipient: str = Field(description="Email đã che một phần")
    allow_download: bool
    verified: bool
    file_name: str | None = None
    pages: list[PublicPage] = []
    attachments: list[PublicAttachment] = []


class OtpOut(BaseModel):
    sent_to: str


class VerifyIn(BaseModel):
    code: str = Field(min_length=4, max_length=10)


def _sid(request: Request) -> str | None:
    return request.cookies.get(VIEW_COOKIE)


@public_router.get("/{token}", response_model=PublicShareOut)
def public_share(token: Token, request: Request, response: Response, db: DbSession, ctx: Ctx) -> PublicShareOut:
    response.headers.update(SECURITY_HEADERS)
    link, doc = links.resolve(db, token, _ip(request))
    base: dict[str, Any] = {
        "title": doc.title,
        "expires_at": link.expires_at,
        "recipient": links._mask(link.recipient_email),
        "allow_download": link.allow_download,
    }
    try:
        links.require_view(db, token, _sid(request), None)
    except Exception:
        return PublicShareOut(**base, verified=False)
    links.touch(db, link, "external_view", ctx)
    pages = [PublicPage(page_number=n, width=w, height=h) for n, w, h in documents.page_numbers(db, doc.id)]
    atts = [
        PublicAttachment(id=a.id, file_name=a.file_name, bytes=a.bytes)
        for a in attachments_app.list_for_document(db, doc.id)
    ]
    return PublicShareOut(**base, verified=True, file_name=doc.file_name, pages=pages, attachments=atts)


@public_router.post("/{token}/otp", response_model=OtpOut, dependencies=[Depends(check_origin)])
def request_otp(token: Token, request: Request, response: Response, db: DbSession) -> OtpOut:
    response.headers.update(SECURITY_HEADERS)
    return OtpOut(sent_to=links.request_otp(db, token, _ip(request)))


@public_router.post("/{token}/verify", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(check_origin)])
def verify(token: Token, data: VerifyIn, request: Request, db: DbSession, ctx: Ctx) -> Response:
    sid, ttl = links.verify_otp(db, token, data.code, _ip(request), ctx)
    resp = Response(status_code=status.HTTP_204_NO_CONTENT, headers=SECURITY_HEADERS)
    resp.set_cookie(
        VIEW_COOKIE,
        sid,
        max_age=ttl,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=f"/api/public/shares/{token}",
    )
    return resp


@public_router.get("/{token}/pages/{page_number}/image", response_class=FileResponse)
def page_image(token: Token, page_number: Annotated[int, Path(ge=1)], request: Request, db: DbSession) -> FileResponse:
    _, doc = links.require_view(db, token, _sid(request), _ip(request))
    page = documents.get_page(db, doc.id, page_number)
    if not page.image_key:
        raise NotFoundError("Trang chưa có ảnh")
    return FileResponse(get_storage().path(page.image_key), media_type="image/png", headers=SECURITY_HEADERS)


def _download(link: Any) -> None:
    if not link.allow_download:
        raise PermissionDeniedError("Link này chỉ cho phép xem, không cho tải", code="DOWNLOAD_NOT_ALLOWED")


@public_router.get("/{token}/file", response_class=FileResponse)
def download_file(token: Token, request: Request, db: DbSession, ctx: Ctx) -> FileResponse:
    link, doc = links.require_view(db, token, _sid(request), _ip(request))
    _download(link)
    path, name, mime = get_storage().path(doc.storage_key), doc.file_name, doc.mime_type
    links.touch(db, link, "external_download", ctx, {"file": name})
    return FileResponse(
        path, media_type=mime, filename=name, content_disposition_type="attachment", headers=SECURITY_HEADERS
    )


@public_router.get("/{token}/attachments/{attachment_id}", response_class=FileResponse)
def download_attachment(
    token: Token, attachment_id: uuid.UUID, request: Request, db: DbSession, ctx: Ctx
) -> FileResponse:
    link, doc = links.require_view(db, token, _sid(request), _ip(request))
    _download(link)
    att = next((a for a in attachments_app.list_for_document(db, doc.id) if a.id == attachment_id), None)
    if att is None:
        raise NotFoundError("Không tìm thấy tài liệu đi kèm")
    path, name, mime = get_storage().path(att.storage_key), att.file_name, att.mime_type
    links.touch(db, link, "external_download", ctx, {"file": name})
    return FileResponse(
        path, media_type=mime, filename=name, content_disposition_type="attachment", headers=SECURITY_HEADERS
    )


@public_router.get("/{token}/bundle", response_class=StreamingResponse)
def download_bundle(token: Token, request: Request, db: DbSession, ctx: Ctx) -> StreamingResponse:
    link, doc = links.require_view(db, token, _sid(request), _ip(request))
    _download(link)
    path = attachments_app.build_bundle(doc, attachments_app.list_for_document(db, doc.id))
    name = attachments_app.bundle_name(doc)
    links.touch(db, link, "external_download", ctx, {"file": name})
    return StreamingResponse(
        attachments_app.iter_and_remove(path),
        media_type="application/zip",
        headers={**SECURITY_HEADERS, "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
    )
