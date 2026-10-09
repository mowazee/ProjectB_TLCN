# Đánh giá chất lượng (NFR-08, D-06, P2-04, P2-05)

Con số báo cáo là **độ chính xác ký tự = 1 − CER** đo trên **tập test giữ riêng**, không phải confidence của model.
Mục tiêu đã chốt (D-06): file scan in **> 90%**, chữ viết tay (P2-03) **> 70%**. PDF có lớp chữ báo cáo riêng.

## 1. Chuẩn bị dữ liệu (không commit tài liệu thật — `eval/data/` nằm trong `.gitignore`)

```
eval/data/
  dev/                      # dùng để hiệu chỉnh ngưỡng needs_review
    digital_pdf/  a.pdf  a.gt.txt
    scan_clear/   b.png  b.gt.txt
    scan_hard/    c.jpg  c.gt.txt
    handwriting/  d.png  d.gt.txt
  test/                     # chỉ dùng cho con số báo cáo cuối
    ... cùng cấu trúc ...
```

- `*.gt.txt`: text đúng (UTF-8, giữ dấu). File nhiều trang: các trang ngăn cách bằng ký tự form feed `\f`.
- Đề xuất tối thiểu 30 trang mỗi loại cho tập test; dev và test **không trùng** tài liệu.
- Chạy thử quy trình với dữ liệu tổng hợp: `python eval/make_synthetic.py --n 10` (không dùng để báo cáo).

## 2. Chạy đánh giá OCR

```powershell
cd backend
.\.venv\Scripts\python.exe eval\ocr_eval.py --split test --profile print --types digital_pdf scan_clear scan_hard
.\.venv\Scripts\python.exe eval\ocr_eval.py --split test --profile handwriting --types handwriting
```

Kết quả in bảng theo loại (số mẫu, số trang, độ chính xác, WER, giây/trang, đạt/chưa đạt) và ghi JSON đầy đủ
vào `eval/reports/` (kèm cấu hình máy, engine, DPI) để đưa vào báo cáo.

## 3. Hiệu chỉnh ngưỡng needs_review (trên tập dev)

```powershell
.\.venv\Scripts\python.exe eval\ocr_eval.py --split dev --profile print
.\.venv\Scripts\python.exe eval\calibrate_threshold.py eval\reports\ocr_dev_print_<thời_gian>.json --target 0.90
```

Đặt giá trị đề xuất vào `NEEDS_REVIEW_THRESHOLD` trong `.env` (mặc định 85).

## 4. Trích xuất trường (P2-04) và phân loại (P2-05)

```powershell
.\.venv\Scripts\python.exe eval\extraction_eval.py eval\data\extraction.jsonl
.\.venv\Scripts\python.exe eval\classification_eval.py eval\data\classification.jsonl --test-ratio 0.3
```

- `extraction.jsonl`: `{"text": "...", "category_code": "CONG-VAN", "fields": {"so_hieu": "...", "ngay_ban_hanh": "2026-03-05"}}`
- `classification.jsonl`: `{"text": "...", "category": "HOP-DONG"}`

## 5. Mẫu báo cáo NFR-08

| Loại | Số mẫu | Số trang | Độ chính xác (1−CER) | WER | Giây/trang | Mục tiêu | Kết quả |
|---|---|---|---|---|---|---|---|
| PDF có lớp chữ | | | | | | (báo cáo riêng) | |
| Scan rõ | | | | | | > 90% | |
| Scan khó | | | | | | > 90% | |
| Chữ viết tay | | | | | | > 70% | |

Ghi kèm: engine + phiên bản, DPI render, CPU/GPU, ngưỡng needs_review đã hiệu chỉnh.
