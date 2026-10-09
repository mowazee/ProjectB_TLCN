"""Sinh bộ dữ liệu TỔNG HỢP nhỏ để chạy thử quy trình đánh giá (KHÔNG thay thế tập test thật của NFR-08).

    python eval/make_synthetic.py --out eval/data --n 10

Tạo dev/test x {digital_pdf, scan_clear, scan_hard} từ câu tiếng Việt mẫu: scan_clear = ảnh rõ;
scan_hard = nghiêng + nhiễu + mờ. Chữ viết tay không thể tổng hợp đáng tin -> nhóm phải thu thập mẫu thật.
"""

import argparse
import random
import sys
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SENTENCES = [
    "Căn cứ Luật Lưu trữ số 33/2024/QH15 ngày 21 tháng 6 năm 2024",
    "Công ty TNHH Số hóa Tài liệu Việt đề nghị các phòng ban phối hợp",
    "Hợp đồng có hiệu lực kể từ ngày ký và được lập thành 02 bản",
    "Giá trị hợp đồng là 150.000.000 đồng, đã bao gồm thuế giá trị gia tăng",
    "Biên bản nghiệm thu khối lượng hoàn thành giai đoạn một",
    "Quyết định về việc bổ nhiệm Trưởng phòng Hành chính - Tổng hợp",
    "Kính gửi: Ủy ban nhân dân phường Bình Thọ, thành phố Thủ Đức",
    "Đề nghị hoàn thành báo cáo trước ngày 31 tháng 12 năm 2026",
    "Người đại diện theo pháp luật: Nguyễn Thị Hồng Nhung",
    "Số điện thoại liên hệ: 028 3896 1234, thư điện tử: vanthu@example.vn",
]
FONT = next(
    (f for f in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") if Path(f).exists()),
    None,
)


def _lines(rng: random.Random) -> list[str]:
    return rng.sample(SENTENCES, 4)


def _render(lines: list[str]) -> Image.Image:
    img = Image.new("L", (1700, 120 + 80 * len(lines)), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 36) if FONT else ImageFont.load_default()
    for i, line in enumerate(lines):
        draw.text((60, 60 + 80 * i), line, fill=0, font=font)
    return img


def _hard(img: Image.Image, rng: random.Random) -> Image.Image:
    img = img.rotate(rng.uniform(-3, 3), fillcolor=255, expand=True).filter(ImageFilter.GaussianBlur(1.2))
    arr = np.asarray(img, dtype=np.int16)
    noise = np.random.default_rng(rng.randint(0, 10**6)).normal(0, 18, arr.shape)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "data")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    for split in ("dev", "test"):
        for i in range(args.n):
            lines = _lines(rng)
            gt = "\n".join(lines)
            for kind in ("scan_clear", "scan_hard"):
                d = args.out / split / kind
                d.mkdir(parents=True, exist_ok=True)
                img = _render(lines) if kind == "scan_clear" else _hard(_render(lines), rng)
                img.save(d / f"s{i:03d}.png")
                (d / f"s{i:03d}.gt.txt").write_text(gt, encoding="utf-8")
            d = args.out / split / "digital_pdf"
            d.mkdir(parents=True, exist_ok=True)
            doc = pymupdf.open()
            page = doc.new_page()
            if FONT:
                page.insert_font(fontname="vn", fontfile=FONT)
            for j, line in enumerate(lines):
                page.insert_text((50, 80 + 24 * j), line, fontname="vn" if FONT else "helv", fontsize=11)
            doc.save(d / f"s{i:03d}.pdf")
            (d / f"s{i:03d}.gt.txt").write_text(gt, encoding="utf-8")
    print(f"Đã sinh dữ liệu tổng hợp tại {args.out} (chỉ để chạy thử quy trình)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
