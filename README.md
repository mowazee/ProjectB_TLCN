# Hệ thống số hóa hồ sơ tài liệu doanh nghiệp (ProjectB — SDD v0.15)

Tiểu luận chuyên ngành — UTE, Nhóm 3. Mọi yêu cầu, tên dữ liệu và hợp đồng API bám theo
**SDD v0.15** (`document/0 -Dac_ta_SDD_v0.15.docx`). Kỳ này thực hiện **MVP + toàn bộ P2 (P2-01…P2-09)**; P3 (RAG) để học kỳ sau.

**Trạng thái (11/11/2026):** MVP + P2 + phân hệ quản trị/tài khoản + bổ sung sau demo (SDD v0.13–v0.15: FR-14…FR-21,
D-12…D-16) đã hiện thực; đặc tả v0.15 khớp với code; CI xanh trên mọi PR (#1–#43). Việc còn lại chủ yếu cần **dữ liệu thật** để đo chất lượng OCR,
trích xuất, phân loại — xem [SUMMARY.md](SUMMARY.md) mục 4.

ProjectB được dựng mới hoàn toàn từ baseline v0.5 (React SPA + FastAPI API-only, modular monolith có điểm mở rộng).
ProjectA (`D:\ProjectA_TLCN`) giữ lại làm tham chiếu bản MVP cũ (Jinja2).

| Phiên bản đặc tả | Ngày | Nội dung chính |
|---|---|---|
| v0.6 | 16/10/2026 | Hợp thức hóa 10 chênh lệch giữa v0.5 và code |
| v0.7 | 18/10/2026 | Phân hệ quản trị và tài khoản (FR-09…FR-12), vai trò Người dùng thông thường |
| v0.8 | 18/10/2026 | Chia sẻ tài liệu đã xuất bản (FR-13, D-09) |
| v0.9 | 21/10/2026 | Chọn danh mục tự động khi tải lên (D-10); OCR vùng ảnh trong trang PDF có lớp chữ |
| v0.10 | 21/10/2026 | Dừng OCR, xử lý văn bản ký số, model OCR nhanh |
| v0.11 | 21/10/2026 | OCR chữ in tiếng Việt bằng VietOCR, chống nghiêng, lọc ký tự lạ (GUIDE mục 9) |
| v0.12 | 26/10/2026 | D-11 quyền sửa theo chủ sở hữu và trạng thái duyệt (Rút lại / Trả lại); nhập hàng loạt có Danh mục gợi ý |
| v0.13 | 10/11/2026 | Bổ sung sau demo: cấu hình thời gian lưu trữ (FR-14), tài liệu đi kèm (FR-15), gộp nhiều file (FR-16), thống kê (FR-17), chia sẻ ra ngoài bằng link + OTP (FR-18), bản cứng/Kho chung (D-12), tìm theo tên, OCR Editor |
| v0.14 | 11/11/2026 | Hiệu lực tài liệu (FR-19, D-14), duyệt/xuất bản/từ chối hàng loạt (FR-20), lịch sử thay đổi tài liệu không bị dọn theo thời hạn audit (D-15) |
| v0.15 | 11/11/2026 | Đồng bộ bản hiện thực: hàng đợi lưu 30 ngày, xóa vĩnh viễn không giữ nhật ký, nhập hàng loạt chỉ theo manifest.csv (D-16), trang Hướng dẫn sử dụng (FR-21) |

## Kiến trúc

```
Trình duyệt ── React SPA (Vite, TS) ──/api──► Nginx ──► FastAPI (API-only, modular layered monolith)
                                                          │  PostgreSQL (metadata, OCR, audit, FTS)
                                                          │  Redis (session TTL + hàng đợi)
                                                          ▼
                                    Celery worker (OCR in + chữ viết tay, hàng đợi default,ocr,ocr_hw) / beat
                                                          │
                                                   Private storage (file gốc, ảnh trang)
```

- **Backend** `backend/app/modules/<module>/{presentation,application,domain,infrastructure}` + `module.py` (ModuleSpec).
  Quy tắc phụ thuộc R1–R10 kiểm tự động bằng **import-linter** (5 contract).
- **6 điểm mở rộng**: module registry (`app/registry.py`), job kind registry (task chung `jobs.run`), domain event
  (phát sau commit), port (OcrEngine, StoragePort, Notifier), API truy vấn công khai, UI registry (`frontend/src/app/registry.ts`).
- **Cờ tính năng** `FEATURES_ENABLED`: router P2 chỉ gắn khi bật (tắt → 404); `/api/auth/me` trả `features` để React ẩn/hiện màn hình.
- **OCR:** chữ in đọc bằng VietOCR (PaddleOCR dò dòng), chữ viết tay bằng VietOCR trên hàng đợi `ocr_hw`; một worker
  xử lý cả hai (GUIDE mục 4.3, 9).
- **Quyền sửa (D-11):** theo người tải lên và trạng thái duyệt; API trả `permissions` để giao diện ẩn/mờ nút (GUIDE mục 3).
- **Giao diện:** design token + component dùng chung, icon `lucide-react`, nền **sáng/tối** (nút trên thanh tiêu đề:
  theo hệ thống → sáng → tối, lưu lựa chọn). Quy ước khi sửa giao diện: GUIDE mục 4.2.
- **Bổ sung v0.13:** tài liệu đi kèm + tải cả bộ, gộp nhiều file khi tải lên, nhập hàng loạt theo bộ hồ sơ, OCR
  Editor mức 1, Thống kê và Cấu hình thời gian lưu trữ (Admin), bản cứng/Kho chung khi gửi duyệt, chia sẻ ra ngoài bằng
  link + OTP email (cần SMTP — GUIDE mục 4.4). Hướng dẫn dùng: GUIDE mục 3 (Chức năng bổ sung v0.13).
- **Bổ sung v0.14–v0.15:** hiệu lực tài liệu (khai báo khi gửi duyệt, tự hết hạn, nhắc trước 7 ngày, ẩn mặc định),
  duyệt/xuất bản/từ chối hàng loạt tối đa 20 tài liệu, nhập hàng loạt chỉ theo `manifest.csv`, hàng đợi lưu 30 ngày,
  tài liệu quá hạn thùng rác bị xóa vĩnh viễn cùng nhật ký, trang Hướng dẫn sử dụng. GUIDE mục 3 (Chức năng v0.14–v0.15).
- **Sao lưu (NFR-03):** service `backup` sao lưu hằng ngày database + file, mỗi bản tự thử khôi phục (GUIDE mục 6.4).

| Module lõi (MVP) | P2 (cờ) |
|---|---|
| auth, users, categories, documents, jobs, ocr, search, dashboard, audit; v0.13: settings, analytics, sharing | workflow (P2-01), highlight (P2-02), handwriting (P2-03), extraction (P2-04), classification (P2-05), versions (P2-06), borrowing + notifications (P2-07), imports (P2-08), rollback (P2-09) |

## Cấu trúc thư mục

```
backend/            FastAPI + Celery (app/, alembic/ 0001…0116, tests/, eval/, scripts/)
frontend/           React + TypeScript + Vite (src/app, src/features/* - 19 feature, src/shared)
infra/nginx/        default.conf (SPA + reverse proxy /api, CSP)
infra/backup/       backup.sh (sao lưu/khôi phục, chạy trong service backup/restore)
docs/openapi.json   hợp đồng API (sinh types React: npm run gen:api)
document/           đặc tả v0.15: SDD, Đặc tả đề tài, Use Case/Sequence/ERD (+ khảo sát); script CSDL v0.15 (21 bảng, sinh từ Alembic)
tests/e2e/          Playwright (Python) chạy trên hệ thống thật
.github/workflows/  backend.yml, frontend.yml, e2e.yml (ma trận cờ P2), compose.yml (Docker + sao lưu)
compose.yaml        Docker Compose (profile rag, tools — tools có Mailpit thử email); compose.dev.yaml
scripts/            demo_start/stop.ps1 (demo một chạm), docker_start/stop.ps1
```

## Chạy nhanh

- **Demo trên Windows (không cần Docker/Redis):** bấm đúp `demo-start.cmd` → mở http://127.0.0.1:8080.
  Trong PowerShell phải gõ `.\demo-start.cmd` (có `.\`). Dừng: `.\demo-stop.cmd`. Đang chạy Docker ở cổng 8080 thì
  dùng `.\demo-start.cmd -Port 8081`. Chi tiết: [GUIDE.md](GUIDE.md) mục 3.
- **Docker (giống production — Redis session/broker, worker + beat trong container):** cài Docker Desktop
  (GUIDE mục 6.1, nên cấp ≥ 6 GB RAM) rồi `.\docker-start.cmd -Demo` → http://127.0.0.1:8080. Sau khi sửa code:
  `.\docker-start.cmd -Build`. Dừng: `.\docker-stop.cmd`.

Tài khoản demo: `admin / Admin@12345` (bản Docker: mật khẩu admin là `DEMO_ADMIN_PASSWORD` trong `.env`), `nhanvien`,
`kiemduyet`, `ketoan`, `nguoidung` (Người dùng thông thường: chỉ xem tài liệu đã xuất bản) / `Demo@12345`.

## Kiểm thử

| Bộ | Lệnh | Kết quả hiện tại (11/11/2026) |
|---|---|---|
| Backend (SQLite) | `cd backend; .\.venv\Scripts\python.exe -m pytest -q` | 509 passed, 1 skipped |
| Backend, mọi cờ P2 bật (NFR-09) | `$env:TEST_FEATURES="all"; ... pytest -q` | 509 passed, 1 skipped |
| Backend trên PostgreSQL 18 + Redis | CI `backend.yml` (6 tổ hợp cờ) | xanh mỗi PR |
| Frontend | `cd frontend; npm test` | 82 passed (25 file) |
| Lint/kiểu/ranh giới | ruff, mypy, lint-imports (5 contract), eslint, tsc, prettier | sạch |
| E2E | `pytest tests/e2e --browser chromium` (demo đang chạy) | xanh trên CI (ma trận mvp, p2-dot-1, p2-tat-ca) |
| Docker + sao lưu/khôi phục | CI `compose.yml` | xanh |

Tài liệu khác: [GUIDE.md](GUIDE.md) (cài đặt, sử dụng, vận hành, Git/CI, sự cố, OCR) · [SUMMARY.md](SUMMARY.md)
(trạng thái, truy vết, chênh lệch so với đặc tả, việc còn lại) · [backend/eval/README.md](backend/eval/README.md) (đánh giá NFR-08).
