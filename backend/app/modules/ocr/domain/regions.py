"""FR-04 (v0.9): trang PDF có lớp chữ vẫn OCR phần chữ nằm trong ảnh nhúng.

Python thuần (R3). Toạ độ là (x, y, w, h) theo pixel ảnh trang đã render.
- Chỉ OCR ảnh đủ lớn (min_area_ratio diện tích trang) và bên trong CHƯA có chữ của lớp chữ: ảnh nền/khung trang
  hay bản scan đã có lớp chữ phủ lên (OCR sẵn) bị bỏ qua, không OCR lại. "Đã có chữ" = đủ ký tự VÀ chữ trải trên ít
  nhất MIN_TEXT_COVER diện tích ảnh: khối chữ ký số nhỏ đè lên bản scan (vd. "Người ký: …" ở góc trang 1) không làm
  bỏ sót nội dung bản scan.
- Dòng OCR trùng vị trí dòng lớp chữ (chữ ký số hiển thị trên ảnh trang) bị bỏ để không lặp nội dung.
- Ghép kết quả theo thứ tự đọc: giữ nguyên thứ tự các dòng lớp chữ, chèn cả khối dòng của mỗi ảnh ngay trước dòng
  lớp chữ đầu tiên nằm dưới mép trên của ảnh.
"""

from app.modules.ocr.domain.ports import OcrLine

Box = tuple[int, int, int, int]
MIN_TEXT_COVER = 0.25  # khung bao các dòng lớp chữ trong ảnh / diện tích ảnh


def _center_inside(box: Box, region: Box) -> bool:
    x, y, w, h = box
    rx, ry, rw, rh = region
    cx, cy = x + w / 2, y + h / 2
    return rx <= cx <= rx + rw and ry <= cy <= ry + rh


def _chars(text: str) -> int:
    return len("".join(text.split()))


def _cover(lines: list[OcrLine], region: Box) -> float:
    """Tỷ lệ khung bao các dòng chữ so với diện tích vùng ảnh."""
    x0 = min(ln.box[0] for ln in lines)
    y0 = min(ln.box[1] for ln in lines)
    x1 = max(ln.box[0] + ln.box[2] for ln in lines)
    y1 = max(ln.box[1] + ln.box[3] for ln in lines)
    return (x1 - x0) * (y1 - y0) / max(region[2] * region[3], 1)


def drop_duplicates(ocr_lines: list[OcrLine], text_lines: list[OcrLine]) -> list[OcrLine]:
    """Bỏ dòng OCR nằm trên dòng lớp chữ (cùng nội dung đã có, vd. khối chữ ký số hiện trên ảnh trang)."""

    def covered(line: OcrLine) -> bool:
        for t in text_lines:
            x, y, w, h = t.box
            pad = h * 0.5
            if _center_inside(line.box, (round(x - pad), round(y - pad), round(w + 2 * pad), round(h + 2 * pad))):
                return True
        return False

    return [ln for ln in ocr_lines if not covered(ln)]


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
        inside = [ln for ln in lines if _center_inside(ln.box, box)]
        if sum(_chars(ln.text) for ln in inside) >= min_text_chars and _cover(inside, box) >= MIN_TEXT_COVER:
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
