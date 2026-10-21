"""Sinh trang A4 TỔNG HỢP kiểu văn bản hành chính để đo OCR chữ in tiếng Việt (GUIDE 9.3). Không thay thế mẫu thật.

    python eval/make_pages.py --out eval/data --n 6

Tạo <split>/synth_page_clear và synth_page_hard: Times New Roman 13pt (bold cho tiêu đề) ở 200 DPI như máy scan văn
phòng, nhiều chữ có dấu chồng và chữ hoa có dấu; ground truth sinh tự động (một dòng ảnh = một dòng text).
- clear: mờ nhẹ + nhiễu nhẹ (scan tốt);
- hard: nghiêng ±1,5°, mờ hơn, nhiễu, tương phản thấp, nén JPEG chất lượng 35 (scan/photo kém);
- lowres: bản clear thu nhỏ còn ~120 DPI (ảnh chụp/scan nén) - đo tác dụng của phóng to ảnh chữ nhỏ (GUIDE 9 PA 2).
Font: Windows (times.ttf) hoặc Linux (Liberation Serif/DejaVu Serif).
"""

import argparse
import io
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

DPI = 200
PAGE = (1654, 2339)  # A4 ở 200 DPI
MARGIN_L, MARGIN_R, MARGIN_T = 236, 158, 160  # lề 3 cm / 2 cm / 2 cm
FONTS = {
    "regular": (
        "C:/Windows/Fonts/times.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ),
    "bold": (
        "C:/Windows/Fonts/timesbd.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    ),
}
HEADINGS = [
    "Điều 1. Phạm vi điều chỉnh và đối tượng áp dụng",
    "Điều 2. Giải thích từ ngữ",
    "Điều 3. Nguyên tắc quản lý hồ sơ, tài liệu điện tử",
    "Điều 4. Trách nhiệm của các cơ quan, tổ chức, cá nhân",
    "Điều 5. Điều khoản thi hành",
    "QUYẾT ĐỊNH VỀ VIỆC BAN HÀNH QUY CHẾ LƯU TRỮ",
    "BIÊN BẢN NGHIỆM THU KHỐI LƯỢNG HOÀN THÀNH",
    "HỢP ĐỒNG CUNG ỨNG DỊCH VỤ SỐ HÓA TÀI LIỆU",
]
PARAGRAPHS = [
    "Quy chế này quy định việc tiếp nhận, phân loại, số hóa, lưu trữ và khai thác hồ sơ, tài liệu của Tổng công ty; "
    "áp dụng đối với các phòng, ban, chi nhánh, văn phòng đại diện và người lao động có liên quan.",
    "Hồ sơ điện tử là tập hợp các tài liệu điện tử có liên quan với nhau về một vấn đề, một sự việc hoặc có cùng đặc "
    "điểm về hình thức, hình thành trong quá trình theo dõi, giải quyết công việc thuộc phạm vi chức năng, nhiệm vụ.",
    "Việc chuyển đổi tài liệu giấy sang định dạng điện tử phải bảo đảm tính toàn vẹn, xác thực, tin cậy và khả năng "
    "truy cập; bản số hóa có độ phân giải tối thiểu 200 dpi, tỷ lệ số hóa 100%, định dạng PDF phiên bản 1.4 trở lên.",
    "Thủ trưởng các đơn vị chịu trách nhiệm chỉ đạo, kiểm tra, đôn đốc việc lập hồ sơ và nộp lưu hồ sơ, tài liệu vào "
    "Lưu trữ cơ quan đúng thời hạn; người được giao nhiệm vụ phải bảo quản an toàn, không để hư hỏng, thất lạc.",
    "Giá trị hợp đồng là 1.250.000.000 đồng (Bằng chữ: Một tỷ hai trăm năm mươi triệu đồng chẵn), đã bao gồm thuế giá "
    "trị gia tăng 10%; thanh toán thành ba đợt bằng hình thức chuyển khoản trong vòng 15 ngày làm việc.",
    "Bên B có nghĩa vụ bồi thường toàn bộ thiệt hại phát sinh nếu để lộ, lọt thông tin, dữ liệu của Bên A trong quá "
    "trình thực hiện hợp đồng; trường hợp bất khả kháng, hai bên thỏa thuận gia hạn thời gian thực hiện.",
    "Hội đồng nghiệm thu gồm đại diện Phòng Hành chính - Tổng hợp, Phòng Kế toán và đơn vị tư vấn giám sát đã kiểm "
    "tra thực tế khối lượng, chất lượng sản phẩm, đối chiếu với hồ sơ thiết kế và thống nhất các nội dung sau đây.",
    "Quyết định này có hiệu lực kể từ ngày ký. Chánh Văn phòng, Trưởng các phòng, ban chuyên môn, Giám đốc các chi "
    "nhánh và cá nhân có liên quan chịu trách nhiệm thi hành Quyết định này./.",
    "Kính gửi: Ủy ban nhân dân tỉnh Đồng Nai; Sở Nội vụ; Sở Thông tin và Truyền thông; Chi cục Văn thư - Lưu trữ.",
    "Trong quá trình thực hiện, nếu có khó khăn, vướng mắc, đề nghị các đơn vị phản ánh kịp thời về Văn phòng (qua "
    "Tổ Văn thư - Lưu trữ, số điện thoại 0251 3822 456, thư điện tử vanthu@dongnai.gov.vn) để tổng hợp, báo cáo.",
    "Người đại diện theo pháp luật: Ông Nguyễn Hữu Thưởng, chức vụ Tổng giám đốc; số định danh cá nhân "
    "079083001234, cấp ngày 12 tháng 8 năm 2021 tại Cục Cảnh sát quản lý hành chính về trật tự xã hội.",
    "Ước tính khối lượng tài liệu cần chỉnh lý khoảng 85 mét giá, trong đó tài liệu hành chính chiếm 62%, tài liệu kế "
    "toán chiếm 31%, còn lại là tài liệu chuyên môn, nghiệp vụ hình thành từ năm 1998 đến năm 2024.",
]


def _font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    path = next((f for f in FONTS[kind] if Path(f).exists()), None)
    if path is None:
        sys.exit("Không tìm thấy font Times New Roman / Liberation Serif / DejaVu Serif")
    return ImageFont.truetype(path, size)


def _wrap(text: str, font: ImageFont.FreeTypeFont, width: int, indent: int) -> list[tuple[str, int]]:
    """(dòng, lề trái thêm): dòng đầu đoạn thụt lề như văn bản hành chính."""
    out: list[tuple[str, int]] = []
    cur, pad = "", indent
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if font.getlength(trial) + pad <= width:
            cur = trial
        else:
            out.append((cur, pad))
            cur, pad = word, 0
    if cur:
        out.append((cur, pad))
    return out


def render_page(rng: random.Random) -> tuple[Image.Image, str]:
    size = round(13 * DPI / 72)  # 13pt
    body, bold = _font("regular", size), _font("bold", size)
    img = Image.new("L", PAGE, 255)
    draw = ImageDraw.Draw(img)
    width = PAGE[0] - MARGIN_L - MARGIN_R
    y = MARGIN_T
    gt: list[str] = []
    blocks: list[tuple[str, ImageFont.FreeTypeFont, int]] = []
    for _ in range(4):
        blocks.append((rng.choice(HEADINGS), bold, 0))
        blocks += [(p, body, round(size * 1.3)) for p in rng.sample(PARAGRAPHS, 2)]
    for text, font, indent in blocks:
        for line, pad in _wrap(text, font, width, indent):
            if y + size * 1.5 > PAGE[1] - MARGIN_T:
                return img, "\n".join(gt)
            draw.text((MARGIN_L + pad, y), line, fill=0, font=font)
            gt.append(line)
            y += round(size * 1.5)
        y += round(size * 0.6)
    return img, "\n".join(gt)


def degrade(img: Image.Image, rng: random.Random, hard: bool) -> Image.Image:
    if hard:
        img = img.rotate(rng.uniform(-1.5, 1.5), resample=Image.Resampling.BICUBIC, fillcolor=255)
    img = img.filter(ImageFilter.GaussianBlur(0.9 if hard else 0.5))
    arr = np.asarray(img, dtype=np.float32)
    if hard:
        arr = 70 + arr * 0.68  # tương phản thấp: giấy xám, mực nhạt
    arr += np.random.default_rng(rng.randint(0, 10**6)).normal(0, 14 if hard else 6, arr.shape)
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if hard:
        buf = io.BytesIO()
        out.save(buf, "JPEG", quality=35)
        out = Image.open(io.BytesIO(buf.getvalue())).convert("L")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "data")
    ap.add_argument("--n", type=int, default=6, help="số trang mỗi split")
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    for split in ("dev", "test"):
        for i in range(args.n):
            page, gt = render_page(rng)
            for kind in ("synth_page_clear", "synth_page_hard", "synth_page_lowres"):
                d = args.out / split / kind
                d.mkdir(parents=True, exist_ok=True)
                img = degrade(page, rng, hard=kind.endswith("hard"))
                if kind.endswith("lowres"):
                    img = img.resize((PAGE[0] * 3 // 5, PAGE[1] * 3 // 5), Image.Resampling.LANCZOS)
                img.save(d / f"p{i:03d}.png", dpi=(DPI, DPI))
                (d / f"p{i:03d}.gt.txt").write_text(gt, encoding="utf-8")
    print(f"Đã sinh trang tổng hợp tại {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
