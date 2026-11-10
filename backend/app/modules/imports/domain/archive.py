"""Giải nén ZIP an toàn và tách manifest.csv cho bulk import (P2-08, NFR-01). Thư viện chuẩn, không I/O đĩa.

Chặn: đường dẫn tuyệt đối / vượt thư mục (..), file mã hóa, ZIP lồng nhau, tỉ lệ nén bất thường
(zip bomb), tổng dung lượng sau giải nén và số file vượt cấu hình; kích thước thật được đếm khi đọc,
không tin header.
"""

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

MANIFEST_NAME = "manifest.csv"  # v0.14: cách khai báo lô duy nhất (bắt buộc)
_CHUNK = 1024 * 1024


class ArchiveError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Entry:
    name: str  # đường dẫn trong lô (vd. "lo1.zip/hop-dong/a.pdf")
    data: bytes | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def filename(self) -> str:
        return PurePosixPath(self.name).name


@dataclass
class Budget:
    max_files: int
    max_total_bytes: int
    max_ratio: int
    files: int = 0
    total: int = 0

    def take_file(self) -> None:
        self.files += 1
        if self.files > self.max_files:
            raise ArchiveError("TOO_MANY_FILES", f"Lô vượt quá {self.max_files} file")

    def take_bytes(self, n: int) -> None:
        self.total += n
        if self.total > self.max_total_bytes:
            raise ArchiveError("BATCH_TOO_LARGE", "Tổng dung lượng lô (sau giải nén) vượt giới hạn")


@dataclass
class Expanded:
    entries: list[Entry] = field(default_factory=list)
    manifest: bytes | None = None


def safe_member_name(name: str) -> str | None:
    """Tên an toàn (posix, tương đối, không '..'); None nếu nguy hiểm."""
    n = name.replace("\\", "/")
    if not n or n.startswith("/") or (len(n) > 1 and n[1] == ":"):
        return None
    parts = PurePosixPath(n).parts
    if any(p in ("..", "") for p in parts):
        return None
    return "/".join(parts)


def _read_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo, budget: Budget) -> bytes:
    buf = bytearray()
    with zf.open(info) as fh:
        while chunk := fh.read(_CHUNK):
            buf.extend(chunk)
            budget.take_bytes(len(chunk))
            if len(buf) > info.file_size:  # header khai sai kích thước
                raise ArchiveError("ZIP_BOMB_SUSPECTED", "Kích thước giải nén không khớp header")
    return bytes(buf)


def expand_zip(name: str, data: bytes, budget: Budget, out: Expanded) -> None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ArchiveError("FILE_CORRUPT", "File ZIP hỏng") from exc
    with zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            safe = safe_member_name(info.filename)
            label = f"{name}/{safe or info.filename}"
            if safe is None:
                out.entries.append(
                    Entry(label, error_code="UNSAFE_PATH", error_message="Đường dẫn trong ZIP không an toàn")
                )
                continue
            base = PurePosixPath(safe).name
            if safe.startswith("__MACOSX/") or base.startswith("."):
                continue
            if PurePosixPath(safe).name.lower() == MANIFEST_NAME and "/" not in safe:
                if info.file_size > 5 * 1024 * 1024:
                    raise ArchiveError("METADATA_TOO_LARGE", "manifest.csv quá lớn")
                out.manifest = _read_member(zf, info, budget)
                continue
            budget.take_file()
            if info.flag_bits & 0x1:
                out.entries.append(Entry(label, error_code="ENCRYPTED", error_message="File trong ZIP có mật khẩu"))
                continue
            if base.lower().endswith(".zip"):
                out.entries.append(
                    Entry(label, error_code="NESTED_ARCHIVE", error_message="Không hỗ trợ ZIP lồng nhau")
                )
                continue
            if info.compress_size and info.file_size / info.compress_size > budget.max_ratio:
                out.entries.append(
                    Entry(label, error_code="ZIP_BOMB_SUSPECTED", error_message="Tỉ lệ nén bất thường, bỏ qua file")
                )
                continue
            if budget.total + info.file_size > budget.max_total_bytes:
                raise ArchiveError("BATCH_TOO_LARGE", "Tổng dung lượng lô (sau giải nén) vượt giới hạn")
            out.entries.append(Entry(label, data=_read_member(zf, info, budget)))


def expand_batch(files: list[tuple[str, bytes]], budget: Budget) -> Expanded:
    """files: (tên gốc, nội dung) theo thứ tự upload. ZIP được giải nén; file khác giữ nguyên."""
    out = Expanded()
    for name, data in files:
        if name.lower() == MANIFEST_NAME:
            out.manifest = data
        elif name.lower().endswith(".zip"):
            expand_zip(name, data, budget, out)
        else:
            budget.take_file()
            budget.take_bytes(len(data))
            out.entries.append(Entry(name, data=data))
    return out
