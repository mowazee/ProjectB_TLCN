"""FR-04 (v0.9): trang PDF có lớp chữ vẫn OCR phần chữ nằm trong ảnh nhúng.

Python thuần (R3). Toạ độ là (x, y, w, h) theo pixel ảnh trang đã render.
- Chỉ OCR ảnh đủ lớn (min_area_ratio diện tích trang) và bên trong CHƯA có chữ của lớp chữ: ảnh nền/khung trang
  hay bản scan đã có lớp chữ phủ lên (OCR sẵn) bị bỏ qua, không OCR lại.
- Ghép kết quả theo thứ tự đọc: giữ nguyên thứ tự các dòng lớp chữ, chèn cả khối dòng của mỗi ảnh ngay trước dòng
  lớp chữ đầu tiên nằm dưới mép trên của ảnh.
"""

from app.modules.ocr.domain.ports import OcrLine

Box = tuple[int, int, int, int]


def _center_inside(box: Box, region: Box) -> bool:
    x, y, w, h = box
    rx, ry, rw, rh = region
    cx, cy = x + w / 2, y + h / 2
    return rx <= cx <= rx + rw and ry <= cy <= ry + rh


def _chars(text: str) -> int:
    return len("".join(text.split()))


def regions_to_ocr(
    image_boxes: list[Box],
    lines: list[OcrLine],
    page_width: int,
    page_height: int,
    *,
    min_area_ratio: float,
    max_regions: int,
    min_text_chars: int,
) -> list[Box]:
    """Vùng ảnh cần OCR, lớn trước (tối đa max_regions), trả theo thứ tự từ trên xuống."""
    page_area = max(page_width * page_height, 1)
    picked = []
    for box in image_boxes:
        _, _, w, h = box
        if w * h < min_area_ratio * page_area or w < 32 or h < 16:
            continue  # logo, biểu tượng nhỏ
        inside = sum(_chars(ln.text) for ln in lines if _center_inside(ln.box, box))
        if inside >= min_text_chars:
            continue  # đã có chữ: ảnh nền dưới văn bản, hoặc scan có lớp chữ OCR sẵn
        picked.append(box)
    picked.sort(key=lambda b: b[2] * b[3], reverse=True)
    return sorted(picked[:max_regions], key=lambda b: (b[1], b[0]))


def merge_reading_order(text_lines: list[OcrLine], blocks: list[tuple[Box, list[OcrLine]]]) -> list[OcrLine]:
    """Chèn khối dòng OCR của từng ảnh vào giữa các dòng lớp chữ theo vị trí dọc của ảnh."""
    out: list[OcrLine] = []
    pending = sorted((b for b in blocks if b[1]), key=lambda b: (b[0][1], b[0][0]))
    for line in text_lines:
        while pending and pending[0][0][1] <= line.box[1]:
            out.extend(pending.pop(0)[1])
        out.append(line)
    for _, region_lines in pending:
        out.extend(region_lines)
    return out
