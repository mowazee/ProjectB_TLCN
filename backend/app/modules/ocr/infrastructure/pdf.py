"""PyMuPDF: kiểm tra PDF, render từng trang thành ảnh PNG, lấy text layer nếu có.

Trang có lớp chữ (digital PDF) lấy text trực tiếp, không OCR (notebook 02: CER 0.013). Từ v0.9 (FR-04) còn trả
vị trí các ảnh nhúng trong trang để OCR riêng phần chữ nằm trong ảnh (con dấu, bảng scan, ảnh chụp văn bản).
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from app.shared.errors import InvalidInputError


@dataclass(frozen=True)
class TextLine:
    text: str
    box: tuple[int, int, int, int]  # x, y, w, h theo pixel ảnh trang đã render


@dataclass
class RenderedPage:
    number: int  # bắt đầu từ 1
    png: bytes
    width: int
    height: int
    lines: list[TextLine] = field(default_factory=list)
    image_boxes: list[tuple[int, int, int, int]] = field(default_factory=list)  # x, y, w, h theo pixel, đã cắt mép

    @property
    def text_char_count(self) -> int:
        return sum(len("".join(ln.text.split())) for ln in self.lines)


def _clean(text: str) -> str:
    """Soft hyphen -> '-', các loại khoảng trắng Unicode (NBSP...) -> dấu cách thường."""
    text = text.replace("­", "-")
    return "".join(" " if ch.isspace() else ch for ch in text).strip()


def inspect_pdf(data: bytes) -> int:
    """Trả số trang; từ chối PDF hỏng hoặc có mật khẩu."""
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass or doc.is_encrypted:
                raise InvalidInputError("PDF có mật khẩu, không xử lý được", code="PDF_ENCRYPTED")
            count = doc.page_count
    except InvalidInputError:
        raise
    except Exception as exc:  # noqa: BLE001 - PyMuPDF ném nhiều loại lỗi khác nhau
        raise InvalidInputError("File PDF bị hỏng hoặc không đọc được", code="FILE_CORRUPT") from exc
    if count < 1:
        raise InvalidInputError("File PDF không có trang nào", code="FILE_CORRUPT")
    return count


def page_count(path: Path) -> int:
    with pymupdf.open(path) as doc:
        return int(doc.page_count)


def render_pages(path: Path, dpi: int) -> Iterator[RenderedPage]:
    zoom = dpi / 72
    with pymupdf.open(path) as doc:
        for index, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            lines: list[TextLine] = []
            for block in page.get_text("dict", sort=True)["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block["lines"]:
                    text = _clean("".join(span["text"] for span in line["spans"]))
                    if not text:
                        continue
                    x0, y0, x1, y1 = (v * zoom for v in line["bbox"])
                    lines.append(TextLine(text, (round(x0), round(y0), round(x1 - x0), round(y1 - y0))))
            yield RenderedPage(
                index + 1,
                pix.tobytes("png"),
                pix.width,
                pix.height,
                lines,
                _image_boxes(page, zoom, pix.width, pix.height),
            )


def _image_boxes(page: pymupdf.Page, zoom: float, width: int, height: int) -> list[tuple[int, int, int, int]]:
    """Vùng hiển thị của các ảnh nhúng (pixel ảnh trang), cắt theo mép trang, bỏ trùng lặp."""
    boxes: set[tuple[int, int, int, int]] = set()
    for info in page.get_image_info():
        x0, y0, x1, y1 = (v * zoom for v in info["bbox"])
        x0, y0 = max(0, round(x0)), max(0, round(y0))
        x1, y1 = min(width, round(x1)), min(height, round(y1))
        if x1 > x0 and y1 > y0:
            boxes.add((x0, y0, x1 - x0, y1 - y0))
    return sorted(boxes, key=lambda b: (b[1], b[0]))
