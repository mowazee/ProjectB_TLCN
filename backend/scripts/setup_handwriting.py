"""Chuẩn bị và kiểm tra nhanh OCR chữ viết tay (P2-03).

    python scripts/setup_handwriting.py            # tải model vào cache + chạy thử
    python scripts/setup_handwriting.py ảnh.png    # chạy thử trên ảnh của bạn (in text nhận được)

1. Cho biết engine sẽ dùng (OCR_HW_ENGINE=auto -> vietocr nếu đã cài, không thì paddleocr-hw).
2. VietOCR: tải cấu hình + weights MỘT lần vào cache (VIETOCR_CACHE_DIR, mặc định ~/.cache/vietocr),
   để job chữ viết tay đầu tiên trong worker không phải chờ tải.
3. Nạp engine và nhận dạng một ảnh: ảnh của bạn, hoặc ảnh tự vẽ bằng font kiểu viết tay của Windows.

Ảnh tự vẽ chỉ để kiểm tra cài đặt chạy được — KHÔNG dùng làm số liệu độ chính xác (NFR-08 cần chữ viết tay
thật: eval/README.md, hoặc eval/handwriting_from_app.py trên tài liệu đã sửa trong ứng dụng).
"""

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))

from app.modules.ocr.infrastructure.engines import handwriting  # noqa: E402
from app.shared.config import settings  # noqa: E402

SAMPLE = ["Hôm nay tôi đi họp tổ", "Biên bản bàn giao hồ sơ", "Ngày 17 tháng 10 năm 2026"]
FONTS = ["Inkfree.ttf", "segoepr.ttf", "comic.ttf"]  # font kiểu viết tay có sẵn trên Windows


def _sample_image() -> tuple["Image.Image", str]:
    from PIL import Image, ImageDraw, ImageFont

    font_dir = Path("C:/Windows/Fonts")
    font_file = next((font_dir / f for f in FONTS if (font_dir / f).is_file()), None)
    font = ImageFont.truetype(str(font_file), 44) if font_file else ImageFont.load_default()
    img = Image.new("RGB", (1100, 90 * len(SAMPLE) + 60), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(SAMPLE):
        draw.text((40, 30 + 90 * i), line, fill=(20, 30, 90), font=font)
    return img, f"ảnh tự vẽ bằng font {font_file.name if font_file else 'mặc định'}"


def main() -> int:
    import numpy as np
    from PIL import Image

    name = handwriting.resolved_engine_name()
    print(f"OCR_HW_ENGINE={settings.OCR_HW_ENGINE} -> dùng engine: {name}")
    if name == "paddleocr-hw" and settings.OCR_HW_ENGINE == "auto":
        print("  (chưa cài vietocr: pip install -r requirements-hw.txt -c constraints.txt rồi")
        print("   pip install vietocr==0.3.13 --no-deps — xem GUIDE mục 4.3)")
    if name == "vietocr":
        t = time.perf_counter()
        cfg = handwriting.prepare_vietocr()
        weights = Path(cfg["weights"]).name
        print(f"  cache: {handwriting.vietocr_cache_dir()}  weights: {weights} ({time.perf_counter() - t:.1f}s)")

    if len(sys.argv) > 1:
        img, source = Image.open(sys.argv[1]).convert("RGB"), sys.argv[1]
        expected = None
    else:
        img, source = _sample_image()
        expected = SAMPLE
    t = time.perf_counter()
    engine = handwriting.create_handwriting_engine()
    print(f"Nạp engine {engine.name} {engine.version}: {time.perf_counter() - t:.1f}s")
    t = time.perf_counter()
    out = engine.recognize(np.asarray(img)[:, :, ::-1].copy())  # RGB -> BGR như worker
    print(f"Nhận dạng {source}: {time.perf_counter() - t:.1f}s, {len(out.lines)} dòng")
    for line in out.lines:
        print(f"  [{line.score or 0:.2f}] {line.text}")
    if expected:
        from metrics import char_accuracy

        got = "\n".join(line.text for line in out.lines)
        acc = char_accuracy("\n".join(expected), got)
        print(f"Độ chính xác ký tự trên ảnh tự vẽ (chỉ để kiểm tra cài đặt): {acc:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
