"""FR-16 (SDD v0.13): gộp nhiều ảnh/PDF thành một PDF theo đúng thứ tự.

Ảnh thành một trang, chuẩn hóa về chiều rộng khổ A4 (giữ tỉ lệ, không phụ thuộc DPI của ảnh); PDF giữ nguyên
các trang (kể cả lớp chữ, FR-04 vẫn OCR vùng ảnh nhúng).
"""

import pymupdf

A4_WIDTH_PT = 595.0


def merge_to_pdf(parts: list[tuple[bytes, str]]) -> bytes:
    """parts: [(dữ liệu, phần mở rộng "pdf" | "png" | "jpg")] đã được file_inspector kiểm tra."""
    out = pymupdf.open()
    try:
        for data, ext in parts:
            if ext == "pdf":
                with pymupdf.open(stream=data, filetype="pdf") as src:
                    out.insert_pdf(src)
                continue
            with pymupdf.open(stream=data, filetype=ext) as img:
                rect = img[0].rect
                pdf_bytes = img.convert_to_pdf()
            height = A4_WIDTH_PT * rect.height / rect.width if rect.width else A4_WIDTH_PT
            page = out.new_page(width=A4_WIDTH_PT, height=height)
            with pymupdf.open(stream=pdf_bytes, filetype="pdf") as one:
                page.show_pdf_page(page.rect, one, 0)
        return out.tobytes(garbage=3, deflate=True)
    finally:
        out.close()
