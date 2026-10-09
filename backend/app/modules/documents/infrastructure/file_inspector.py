"""Kiểm tra file upload (NFR-01): chữ ký thật (magic bytes) chứ không tin phần mở rộng,
khớp phần mở rộng, PDF không mã hóa/không hỏng, giới hạn số trang, ảnh không quá lớn."""

import io
from dataclasses import dataclass
from pathlib import PurePath
from typing import BinaryIO

import filetype
import pymupdf
from PIL import Image, UnidentifiedImageError

from app.shared.config import settings
from app.shared.errors import InvalidInputError, PayloadTooLargeError, UnsupportedMediaTypeError

ALLOWED_TYPES: dict[str, set[str]] = {
    "application/pdf": {"pdf"},
    "image/png": {"png"},
    "image/jpeg": {"jpg", "jpeg"},
}


@dataclass(frozen=True)
class FileInfo:
    mime_type: str
    ext: str
    pages: int


def safe_filename(name: str | None) -> str:
    base = PurePath((name or "").replace("\\", "/")).name.strip()
    return base[:255] or "tai-lieu"


def _pdf_pages(data: bytes) -> int:
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass or doc.is_encrypted:
                raise InvalidInputError("PDF có mật khẩu, không xử lý được", code="PDF_ENCRYPTED")
            count = int(doc.page_count)
    except InvalidInputError:
        raise
    except Exception as exc:  # noqa: BLE001 - PyMuPDF ném nhiều loại lỗi
        raise InvalidInputError("File PDF bị hỏng hoặc không đọc được", code="FILE_CORRUPT") from exc
    if count < 1:
        raise InvalidInputError("File PDF không có trang nào", code="FILE_CORRUPT")
    return count


def _check_image(data: bytes) -> None:
    try:
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise InvalidInputError("File ảnh bị hỏng hoặc không đọc được", code="FILE_CORRUPT") from exc
    if width * height > settings.MAX_IMAGE_PIXELS:
        raise InvalidInputError("Ảnh có độ phân giải quá lớn", code="IMAGE_TOO_LARGE")


def inspect(data: bytes, filename: str) -> FileInfo:
    if not data:
        raise InvalidInputError("File rỗng", code="EMPTY_FILE")
    if len(data) > settings.max_upload_bytes:
        raise PayloadTooLargeError(f"File vượt quá dung lượng cho phép ({settings.MAX_UPLOAD_MB} MB)")
    kind = filetype.guess(data[:8192])
    if kind is None or kind.mime not in ALLOWED_TYPES:
        raise UnsupportedMediaTypeError("Chỉ hỗ trợ file PDF, PNG, JPG")
    ext = PurePath(filename).suffix.lower().lstrip(".")
    if ext not in ALLOWED_TYPES[kind.mime]:
        raise UnsupportedMediaTypeError("Phần mở rộng của file không khớp với nội dung thật", code="EXTENSION_MISMATCH")
    if kind.mime == "application/pdf":
        pages = _pdf_pages(data)
        if pages > settings.MAX_PAGES:
            raise PayloadTooLargeError(
                f"Tài liệu có {pages} trang, vượt giới hạn {settings.MAX_PAGES} trang", code="TOO_MANY_PAGES"
            )
    else:
        _check_image(data)
        pages = 1
    return FileInfo(kind.mime, ext, pages)


def read_limited(stream: BinaryIO, limit: int) -> bytes:
    """Đọc theo khối, dừng ngay khi vượt giới hạn (không đọc hết file quá lớn vào RAM)."""
    buf = bytearray()
    while chunk := stream.read(1024 * 1024):
        buf.extend(chunk)
        if len(buf) > limit:
            raise PayloadTooLargeError(f"File vượt quá dung lượng cho phép ({settings.MAX_UPLOAD_MB} MB)")
    return bytes(buf)
