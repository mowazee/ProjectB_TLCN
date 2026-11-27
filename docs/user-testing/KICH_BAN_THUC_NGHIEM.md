# Kịch bản thực nghiệm người dùng (TC2.7)

## 1. Mục tiêu và chỉ số (xác định trước khi thực nghiệm)

| Chỉ số | Cách đo | Mục tiêu |
|---|---|---|
| Tỉ lệ hoàn thành tác vụ | Số tác vụ hoàn thành không cần trợ giúp / tổng số tác vụ | ≥ 90% |
| Thời gian hoàn thành mỗi tác vụ | Người điều phối bấm giờ | Ghi nhận, so sánh vòng 1 – vòng 2 |
| Số lỗi thao tác | Số lần đi sai luồng, phải hỏi | Giảm ở vòng 2 |
| Điểm SUS | Phiếu SUS 10 câu ([PHIEU_SUS.md](PHIEU_SUS.md)) | ≥ 80 |

## 2. Người tham gia

- **≥ 10 người thuộc nhóm mục tiêu**: nhân viên văn phòng, văn thư/lưu trữ, kế toán, người quản lý duyệt hồ sơ
  (không chỉ sinh viên cùng lớp). Ghi danh sách **ẩn danh** (P01, P02…) kèm vai trò, số năm kinh nghiệm.
- Mỗi người ký đồng ý tham gia (bằng lời hoặc phiếu), được biết dữ liệu là dữ liệu demo, có thể dừng bất kỳ lúc nào.

## 3. Chuẩn bị

1. Hệ thống chạy trên staging (hoặc máy demo) với dữ liệu demo; mỗi người một tài khoản thử theo vai trò.
2. Thư mục file mẫu: 2 PDF scan, 3 ảnh trang (để gộp), file `manifest.csv` + ZIP mẫu.
3. Người điều phối: đọc kịch bản, không gợi ý trừ khi người tham gia bế tắc quá 2 phút (ghi là "cần trợ giúp").
4. Ghi chép vào `ket_qua_thuc_nghiem.csv` (cùng thư mục).

## 4. Tác vụ

| Mã | Vai trò | Tác vụ (đọc cho người tham gia) | Hoàn thành khi |
|---|---|---|---|
| T1 | Nghiệp vụ | Tải lên file "Quyết định 12.pdf" vào danh mục Quyết định | Tài liệu xuất hiện trong danh sách, OCR chạy |
| T2 | Nghiệp vụ | Mở trang 1, sửa một từ OCR sai rồi lưu | Lưu thành công, có phiên bản mới |
| T3 | Nghiệp vụ | Tìm tài liệu có chứa cụm "nghiệm thu" và mở đúng trang | Mở được trang có từ khóa được tô sáng |
| T4 | Nghiệp vụ | Gửi duyệt tài liệu, khai báo không có bản cứng và còn hiệu lực đến 31/12 năm nay | Trạng thái "Chờ duyệt" |
| T5 | Nghiệp vụ | Nhập hàng loạt bằng file ZIP mẫu có `manifest.csv` (trong đó 3 ảnh gộp thành 1 tài liệu) | Báo cáo lô: các tài liệu đã nhập |
| T6 | Kiểm duyệt | Duyệt và xuất bản cùng lúc 3 tài liệu đang chờ duyệt | 3 tài liệu "Đã xuất bản" |
| T7 | Kiểm duyệt | Đổi một tài liệu đã xuất bản sang "Hết hiệu lực" (có nhập lý do) | Nhãn "Hết hiệu lực", tài liệu ẩn khỏi danh sách mặc định |
| T8 | Kiểm duyệt | Chia sẻ một tài liệu ra ngoài cho email của người điều phối, thời hạn 2 giờ | Email nhận được link |
| T9 | Admin | Tìm trong Nhật ký hệ thống các thao tác trên tài liệu "Quyết định 12" | Danh sách nhật ký lọc đúng |

Người tham gia làm các tác vụ đúng vai trò của mình (văn thư/kế toán: T1–T5; quản lý: T6–T8; quản trị: T9).

## 5. Quy trình mỗi buổi (≈ 30 phút)

1. Giới thiệu (2 phút), không hướng dẫn chi tiết giao diện.
2. Thực hiện tác vụ, nghĩ thành lời; người điều phối bấm giờ và ghi lỗi.
3. Điền phiếu SUS (3 phút) và trả lời 3 câu mở: điều thích nhất, điều khó nhất, đề xuất.
4. Ghi kết quả vào CSV.

## 6. Vòng cải tiến và đo lại

1. **Vòng 1**: ≥ 10 người. Tổng hợp bằng `python sus_score.py ket_qua_thuc_nghiem.csv --round 1`.
2. Gom phản hồi thành danh sách vấn đề (mức độ, số người gặp), tạo GitHub Issue cho từng vấn đề, sửa bằng PR.
3. **Vòng 2**: tối thiểu 5 người (có thể là người mới), cùng kịch bản.
4. So sánh trước – sau: `python sus_score.py ket_qua_thuc_nghiem.csv --compare` (SUS, tỉ lệ hoàn thành, thời gian).
5. Viết báo cáo thực nghiệm: thiết kế, người tham gia (ẩn danh), số liệu hai vòng, các cải tiến đã làm.
