# Danh mục nợ kỹ thuật và kế hoạch xử lý

Cập nhật: 28/11/2026. Mỗi mục: vì sao là nợ, rủi ro, kế hoạch. Mức ưu tiên: **Cao** = ảnh hưởng nghiệm thu/vận hành,
**TB** = nên làm trong kỳ, **Thấp** = để học kỳ sau.

| # | Nợ kỹ thuật | Rủi ro | Kế hoạch xử lý | Ưu tiên |
|---|---|---|---|---|
| 1 | Chưa có staging công khai và triển khai tự động (mới có image phiên bản trên GHCR, workflow `release.yml`) | Không có môi trường cho người dùng thật, demo phụ thuộc máy cá nhân | Chọn máy (VPS hoặc máy nhà + Cloudflare Tunnel), thêm chặng deploy sau CI, cảnh báo uptime | Cao |
| 2 | Lịch beat lưu trong container (`/tmp/celerybeat-schedule`), khởi động lại thì bộ đếm chạy lại từ đầu | Tác vụ chu kỳ dài có thể không chạy (đã giảm chu kỳ dọn còn 1 giờ ở PR #45) | Lưu schedule vào volume hoặc dùng scheduler đọc mốc chạy cuối từ DB | TB |
| 3 | Job gửi email `EMAIL` dùng chung worker với OCR | OTP/link chia sẻ đến chậm khi đang OCR tài liệu dài | Tách hàng đợi `mail` + worker nhẹ | TB |
| 4 | `NEEDS_REVIEW_THRESHOLD`, ngưỡng "dòng tin cậy thấp" (0,8) trong OCR Editor đặt cố định | Gắn cờ cần xem lại chưa sát dữ liệu thật | Hiệu chỉnh bằng `eval/calibrate_threshold.py` trên ≥ 30 trang thật | TB |
| 5 | NFR-08 (độ chính xác OCR) mới đo trên tập nhỏ (3 trang scan thật) | Số liệu chưa đủ tin cậy để công bố | Lập tập test ≥ 30 trang mỗi loại (scan rõ, scan khó, chữ viết tay) | Cao |
| 6 | Độ phủ test frontend 66,6% số dòng (backend 93%) | Lỗi giao diện ít được bắt tự động | Bổ sung test cho trang admin (Thống kê, Cấu hình), OCR Editor | TB |
| 7 | Hàng chờ duyệt không hiện vị trí bản cứng (module workflow không phụ thuộc borrowing) | Kiểm duyệt phải mở từng tài liệu để xem vị trí | Thêm API truy vấn công khai của borrowing cho workflow đọc (điểm mở rộng có sẵn) | Thấp |
| 8 | Trang Hướng dẫn sử dụng (FR-21) đang trống | Người dùng mới chưa có tài liệu trong app | Chốt hình thức (PDF tải lên hay nội dung soạn sẵn), viết nội dung từ GUIDE | TB |
| 9 | Kiểm thử tải chưa chạy trên môi trường giống production | NFR-04 (p95 ≤ 2 giây) chưa có số liệu đo ở quy mô đồng thời | Chạy kịch bản tải trên staging khi có (mục 1) | TB |
| 10 | Hỏi đáp tài liệu (P3-01, RAG) chưa làm | Ngoài phạm vi kỳ này | Học kỳ sau theo SDD mục 5 | Thấp |
