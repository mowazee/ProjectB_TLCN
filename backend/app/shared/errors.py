"""Lỗi nghiệp vụ và chuẩn lỗi API (SDD mục 13): {error:{code,message,fields?,request_id}}.

Lớp application/domain ném AppError; presentation (app.shared.http) chuyển thành JSON. Không trả
stack trace, đường dẫn file nội bộ hay storage_key ra client.
"""

from typing import Any

from app.shared.logging import request_id_var


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        fields: dict[str, str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.fields = fields
        self.details = details or {}


class InvalidInputError(AppError):
    status_code = 400
    code = "INVALID_INPUT"


class UnprocessableError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class AuthenticationError(AppError):
    status_code = 401
    code = "UNAUTHENTICATED"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class GoneError(AppError):
    status_code = 410
    code = "GONE"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "FILE_TOO_LARGE"


class UnsupportedMediaTypeError(AppError):
    status_code = 415
    code = "UNSUPPORTED_FILE_TYPE"


class TooManyRequestsError(AppError):
    status_code = 429
    code = "TOO_MANY_REQUESTS"


class StorageError(AppError):
    status_code = 500
    code = "STORAGE_ERROR"


def error_body(
    code: str, message: str, fields: dict[str, str] | None = None, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message, "request_id": request_id_var.get()}
    if fields:
        err["fields"] = fields
    if details:
        err["details"] = details
    return {"error": err}
