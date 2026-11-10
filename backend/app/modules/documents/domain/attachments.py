"""FR-15 (SDD v0.13): loại file được phép làm tài liệu đi kèm (Python thuần).

Kiểm phần mở rộng theo danh sách cho phép VÀ chữ ký nội dung (NFR-01): không nhận file thực thi, script hay
file nén (có thể giấu file thực thi).
"""

from pathlib import PurePath

_ZIP = b"PK\x03\x04"
_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# phần mở rộng -> (mime, các chữ ký hợp lệ; None = file văn bản)
ALLOWED: dict[str, tuple[str, tuple[bytes, ...] | None]] = {
    ".pdf": ("application/pdf", (b"%PDF",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", (_ZIP,)),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", (_ZIP,)),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", (_ZIP,)),
    ".odt": ("application/vnd.oasis.opendocument.text", (_ZIP,)),
    ".ods": ("application/vnd.oasis.opendocument.spreadsheet", (_ZIP,)),
    ".doc": ("application/msword", (_OLE,)),
    ".xls": ("application/vnd.ms-excel", (_OLE,)),
    ".ppt": ("application/vnd.ms-powerpoint", (_OLE,)),
    ".txt": ("text/plain", None),
    ".csv": ("text/csv", None),
}
ACCEPT = ", ".join(sorted(ALLOWED))


class AttachmentRejected(ValueError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def classify(filename: str, data: bytes) -> tuple[str, str]:
    """Trả (phần mở rộng chuẩn, mime) hoặc ném AttachmentRejected."""
    ext = PurePath(filename).suffix.lower()
    if ext not in ALLOWED:
        raise AttachmentRejected(
            f"Không nhận loại file '{ext or '(không có đuôi)'}'. Cho phép: {ACCEPT}", "UNSUPPORTED_TYPE"
        )
    if not data:
        raise AttachmentRejected("File rỗng", "EMPTY_FILE")
    mime, signatures = ALLOWED[ext]
    if signatures is None:
        if b"\x00" in data[:4096]:
            raise AttachmentRejected("File văn bản có nội dung nhị phân", "EXTENSION_MISMATCH")
    elif not any(data.startswith(sig) for sig in signatures):
        raise AttachmentRejected("Phần mở rộng của file không khớp với nội dung thật", "EXTENSION_MISMATCH")
    return (".jpg" if ext == ".jpeg" else ext), mime
