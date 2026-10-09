"""Phần dùng chung của lớp presentation (FastAPI): xử lý lỗi theo chuẩn SDD mục 13 và tham số phân trang.

Tách khỏi errors.py/pagination.py để lớp application/domain không phụ thuộc FastAPI (R2).
"""

import logging
from typing import Annotated, Any

from fastapi import FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis import exceptions as redis_exc
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.errors import AppError, error_body
from app.shared.pagination import PageParams

logger = logging.getLogger("app.errors")


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PageParams:
    return PageParams(page, page_size)


def _json(status: int, body: dict[str, Any]) -> JSONResponse:
    return JSONResponse(jsonable_encoder(body), status_code=status)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _json(exc.status_code, error_body(exc.code, exc.message, exc.fields, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for e in exc.errors():
            loc = [str(p) for p in e.get("loc", []) if p not in ("body", "query", "path", "form")]
            fields[".".join(loc) or "_"] = str(e.get("msg"))
        return _json(422, error_body("VALIDATION_ERROR", "Dữ liệu không hợp lệ", fields))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = "Không tìm thấy" if exc.status_code == 404 else str(exc.detail)
        return _json(exc.status_code, error_body(f"HTTP_{exc.status_code}", message))

    @app.exception_handler(redis_exc.ConnectionError)
    @app.exception_handler(redis_exc.TimeoutError)
    async def _redis_down(request: Request, exc: Exception) -> JSONResponse:
        # Session store (Redis) mất kết nối: báo tạm thời không phục vụ được, không phải lỗi dữ liệu
        logger.error("Redis không truy cập được (%s): %s %s", type(exc).__name__, request.method, request.url.path)
        return _json(503, error_body("SERVICE_UNAVAILABLE", "Hệ thống tạm thời gián đoạn, vui lòng thử lại sau"))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Lỗi không xử lý được: %s %s", request.method, request.url.path)
        return _json(500, error_body("INTERNAL_ERROR", "Lỗi hệ thống, vui lòng thử lại sau"))
