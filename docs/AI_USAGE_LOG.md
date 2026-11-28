# Nhật ký sử dụng AI (AI Usage Log)

Kê khai theo rubric TC2.3. Nhóm **có sử dụng** công cụ AI. Nhật ký phải khớp với lịch sử Git và Pull Request: mỗi dòng
ghi PR tương ứng để hội đồng đối chiếu.

> **Lưu ý về lịch sử Git:** từ PR #29 trở đi, theo yêu cầu của nhóm, commit và mô tả PR **không ghi dòng đồng tác giả
> AI** (Co-Authored-By / "Generated with Claude Code"). Việc dùng AI được kê khai đầy đủ tại đây thay cho các dòng đó.

## 1. Công cụ và cách dùng

| Công cụ | Phiên bản | Dùng cho | Không dùng cho |
|---|---|---|---|
| Claude Code (Anthropic), chạy trong VS Code | Claude Opus | Phân tích tác động yêu cầu; soạn đặc tả (SDD, file 2, file 3) theo quyết định của nhóm; sinh mã backend/frontend, migration, test; chạy test, lint, CI; vẽ sơ đồ (Graphviz); viết README/GUIDE/SUMMARY | Ra quyết định nghiệp vụ (nhóm chốt: D-11…D-16, KPI, phạm vi); merge PR (nhóm review và merge); dữ liệu thật của người dùng |
| _(nhóm điền thêm nếu có: ChatGPT, Gemini…)_ | | | |

## 2. Quy trình kiểm soát đầu ra AI

1. Nhóm nêu yêu cầu → AI **đánh giá tác động** và đề xuất phương án → **nhóm chốt quyết định** (ghi vào SDD mục 11).
2. AI cập nhật đặc tả trước (PR riêng), nhóm đọc và merge; sau đó AI hiện thực trên nhánh riêng.
3. Mỗi PR: AI chạy toàn bộ test (backend SQLite + mọi cờ P2, frontend), lint (ruff, mypy, import-linter, ESLint, tsc);
   CI chạy lại trên PostgreSQL + Redis thật và E2E. **Không merge khi CI chưa xanh.**
4. Nhóm review theo checklist [CONTRIBUTING.md](../CONTRIBUTING.md) mục 5 (đọc hiểu, đối chiếu tài liệu chính thức,
   giấy phép, dữ liệu nhạy cảm) rồi mới merge.
5. Lỗi của AI phát hiện được ghi vào mục 4 kèm nguyên nhân và nơi sửa.

## 3. Nhật ký theo PR

| PR | Ngày | Nội dung | Phần AI thực hiện | Phần nhóm thực hiện / quyết định |
|---|---|---|---|---|
| #1–#28 | 09/10–02/11 | MVP + P2, CI, giao diện, OCR tiếng Việt | _(nhóm điền: phần nào dùng AI, phần nào tự làm)_ | _(nhóm điền)_ |
| #29 | 10/11 | Đặc tả v0.13 (FR-14…FR-18, D-12, D-13), vẽ lại Hình 1, 2b, 8 | Đánh giá tác động 8 tính năng, soạn đặc tả, vẽ sơ đồ | Chốt: audit ≥ 180 ngày, manifest, Kho chung, thống kê chỉ Admin, link ≤ 24 giờ + OTP, Gmail SMTP |
| #30–#37 | 10/11 | Hiện thực FR-06, D-12, FR-14, FR-05, FR-16, FR-17, FR-15, FR-18 | Mã, migration 0111–0115, test, tài liệu | Review, thử trên Docker, merge |
| #38 | 10/11 | README, GUIDE, SUMMARY, script CSDL v0.13 | Soạn tài liệu, sinh script từ Alembic | Review |
| #39 | 11/11 | Đặc tả v0.14 (FR-19, FR-20, D-14, D-15) | Đánh giá tác động, soạn đặc tả, Hình 2c, 9 | Chốt: 23:59, ẩn mặc định, lý do bắt buộc, ≤ 20 tài liệu, nhắc trước hạn, lịch sử tài liệu không bị xóa |
| #40–#42 | 11/11 | D-15, FR-19 hiệu lực, FR-20 duyệt hàng loạt | Mã, migration 0116, test | Review, merge |
| #43 | 11/11 | Hàng đợi 30 ngày, xóa vĩnh viễn không giữ nhật ký, chỉ manifest, trang Hướng dẫn | Mã, test | Đề xuất 4 điều chỉnh sau khi chạy thử |
| #44 | 11/11 | Đặc tả v0.15; gộp nhiều file qua `file_name`, file mẫu ZIP | Đặc tả, mã, test | Yêu cầu tên file gộp theo `title`, hướng dẫn nằm trong file mẫu |
| #45, #46 | 11/11 | Beat dọn mỗi giờ, lọc nhật ký theo tên, cột Tên tài liệu | Tìm nguyên nhân, mã, test | Phát hiện lỗi khi dùng thử (thùng rác, ô lọc), chọn phương án cột riêng |
| #47–#58 | 28/11 | Cải tiến theo rubric: CI bảo mật, độ phủ, tài liệu kiểm thử/thiết kế, xử lý issue SonarCloud | Cấu hình CI, tài liệu, script | Chọn phạm vi, hoãn staging |
| #59 | 28/11 | Admin tải lên tài liệu Hướng dẫn sử dụng; sửa yêu cầu mượn bị treo khi tài liệu bị xóa | Tìm nguyên nhân lỗi treo, thiết kế module guides, mã, test, giao diện theo ảnh mẫu | Đưa ảnh mẫu giao diện, phát hiện lỗi khi dùng thử, nghiệm thu |
| #60 | 28/11 | Kiểm thử tải NFR-04 | Sửa script (cookie Secure), chạy 2 mức tải, ghi kết quả | Build lại hệ thống, xem số liệu |
| #61 | 28/11 | Đặc tả v0.16 (file 0, 2, 3, 4) | Đối chiếu code để ghi đúng thực tế, sửa docx giữ định dạng, vẽ Hình 2d và 8b, sinh script CSDL | Yêu cầu cập nhật, duyệt nội dung |

## 4. Lỗi / ảo giác của AI đã phát hiện và sửa

| # | Lỗi | Phát hiện bằng | Nguyên nhân | Sửa tại |
|---|---|---|---|---|
| 1 | Thêm bắt buộc chọn hiệu lực khi gửi duyệt nhưng **không cập nhật test E2E**, CI e2e đỏ (nút Xác nhận bị khóa) | CI e2e | AI chỉ chạy test backend/frontend ở máy, bỏ sót bộ E2E | PR #41 (commit sửa `submit_for_review`) |
| 2 | Lọc/tra tên tài liệu trong nhật ký **không khớp UUID trên SQLite** (cột khai báo không có kiểu) | Test mới thất bại | Dùng `table()` không gắn kiểu `Uuid`, SQLite lưu UUID dạng 32 ký tự hex | PR #46 |
| 3 | Migration 0112 khai báo cột `value` **cho phép NULL** trong khi model là NOT NULL | `alembic check` trên CI | Viết migration tay lệch với model | PR #32 |
| 4 | Test đọc lại dữ liệu sau tác vụ nền **thấy dữ liệu cũ** (tưởng câu lệnh xóa không chạy) | Test thất bại khi chạy bộ đầy đủ | Session SQLite của test giữ snapshot; phải `rollback()` trước khi đọc | PR #45 |
| 5 | Lệnh git trong một chuỗi lệnh **xóa nhầm script CSDL v0.13** khi bước trước lỗi | Kiểm tra `git status` | Ghép lệnh bằng `;` thay vì `&&`, bước sau vẫn chạy | PR #44 (khôi phục trước khi commit) |
| 6 | **Xóa nhánh khi PR #46 chưa merge xong**, GitHub tự đóng PR | Kiểm tra `main` sau khi xóa | Tin vào thông báo "đã merge" mà không kiểm tra trạng thái PR trước | Khôi phục nhánh, mở lại PR #46 |
| 7 | `ruff format` **định dạng lại cả file E2E** theo cấu hình sai thư mục | Xem `git diff` | Chạy formatter từ thư mục gốc không có cấu hình backend | Hoàn lại file trước khi commit (PR #43) |
| 8 | Test thứ tự nhật ký **chập chờn** trên PostgreSQL | CI | Không có `ORDER BY`, PostgreSQL không bảo đảm thứ tự | PR #31 (`order_by(AuditLog.id)`) |
| 9 | Tác vụ dọn thùng rác 24 giờ **không bao giờ chạy** khi hệ thống được build lại thường xuyên | Nhóm thấy tài liệu quá hạn vẫn còn | Beat lưu lịch trong container, khởi động lại thì bộ đếm chạy lại; AI không lường trước khi đặt chu kỳ | PR #45 (chu kỳ 1 giờ) |
| 10 | Graphviz **lỗi segfault** khi vẽ ERD | Chạy lệnh vẽ | Thẻ `<font>` rỗng trong nhãn HTML | PR #29 |

## 5. Vấn đáp: các vị trí mã nên luyện giải thích

Chọn ngẫu nhiên để luyện (mỗi vị trí trả lời: làm gì, vì sao có, dữ liệu/thư viện từ đâu, bỏ đi thì sao):

- `backend/app/modules/documents/domain/policies.py` — quyền D-11 theo chủ sở hữu và trạng thái duyệt.
- `backend/app/modules/workflow/domain/state_machine.py` và `application/approvals.py` (`transition`, `bulk`).
- `backend/app/modules/documents/domain/validity.py` — quy tắc hết hiệu lực sau 23:59.
- `backend/app/modules/jobs/application/runner.py` — chạy job idempotent, retry.
- `backend/app/modules/ocr/` — pipeline OCR (PaddleOCR dò dòng, VietOCR đọc chữ, chống nghiêng).
- `backend/app/modules/sharing/application/links.py` — token băm, OTP, phiên xem riêng.
- `backend/app/modules/audit/application/retention.py` — phạm vi dọn nhật ký (D-15, D-16).
- `backend/app/modules/imports/domain/bundles.py` — phân tích manifest, gộp file.
- `frontend/src/features/workflow/ReviewsPage.tsx` — duyệt hàng loạt, checklist.
- `.github/workflows/*.yml` — các chặng CI và vì sao từng chặng chặn merge.
