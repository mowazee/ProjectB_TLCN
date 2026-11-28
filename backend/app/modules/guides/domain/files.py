"""Loại file được phép cho tài liệu hướng dẫn sử dụng (FR-21, v0.16). Python thuần.

Kiểm tra theo phần mở rộng VÀ chữ ký nội dung (magic bytes) - không tin Content-Type của trình duyệt (NFR-01).
PDF, ảnh, video MP4 xem trực tiếp trên trình duyệt; Word/Excel/PowerPoint tải về.
"""

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class GuideType:
    mime: str
    inline: bool  # mở trực tiếp trên trình duyệt (True) hay tải về


TYPES: dict[str, GuideType] = {
    ".pdf": GuideType("application/pdf", True),
    ".png": GuideType("image/png", True),
    ".jpg": GuideType("image/jpeg", True),
    ".jpeg": GuideType("image/jpeg", True),
    ".mp4": GuideType("video/mp4", True),
    ".docx": GuideType("application/vnd.openxmlformats-officedocument.wordprocessingml.document", False),
    ".xlsx": GuideType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", False),
    ".pptx": GuideType("application/vnd.openxmlformats-officedocument.presentationml.presentation", False),
}
ALLOWED_TEXT = "PDF, Word, Excel, PowerPoint, ảnh PNG/JPG, video MP4"


def extension(file_name: str) -> str:
    return PurePosixPath(file_name.replace("\\", "/")).suffix.lower()


def safe_name(file_name: str) -> str:
    """Tên file gốc chỉ để hiển thị/tải về: bỏ đường dẫn và ký tự điều khiển, giới hạn độ dài."""
    base = PurePosixPath((file_name or "").replace("\\", "/")).name.strip()
    base = "".join(ch for ch in base if ch.isprintable() and ch not in '<>:"/\\|?*')
    return base[:255] or "huong-dan"


def content_matches(ext: str, head: bytes) -> bool:
    """Chữ ký nội dung khớp phần mở rộng."""
    if ext == ".pdf":
        return head.startswith(b"%PDF-")
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == ".mp4":
        return head[4:8] == b"ftyp"
    if ext in (".docx", ".xlsx", ".pptx"):
        return head.startswith(b"PK\x03\x04")  # Office Open XML là file ZIP
    return False
