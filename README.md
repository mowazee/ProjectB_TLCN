# Hệ thống số hóa hồ sơ tài liệu doanh nghiệp (ProjectB — SDD v0.8)

Tiểu luận chuyên ngành — UTE, Nhóm 3. Mọi yêu cầu, tên dữ liệu và hợp đồng API bám theo
**SDD v0.8** (`document/0 -Dac_ta_SDD_v0.8.docx`). Kỳ này thực hiện **MVP + toàn bộ P2 (P2-01…P2-09)**; P3 (RAG) để học kỳ sau.

ProjectB được dựng mới hoàn toàn từ baseline v0.5 (React SPA + FastAPI API-only, modular monolith có điểm mở rộng);
đặc tả nâng lên v0.6 (16/10/2026) sau khi hiện thực xong để khớp với code; v0.7 (18/10/2026) thêm phân hệ quản trị và tài khoản (FR-09…FR-12, đã hiện thực); v0.8 (18/10/2026) thêm chia sẻ tài liệu đã xuất bản (FR-13, đang hiện thực). **Trạng thái:** MVP + P2 chạy end to end,
CI xanh; việc còn lại cần dữ liệu thật để đo chất lượng OCR — xem [SUMMARY.md](SUMMARY.md) mục 4.
ProjectA (`D:\ProjectA_TLCN`) giữ lại làm tham chiếu bản MVP cũ (Jinja2).

## Kiến trúc

```
Trình duyệt ── React SPA (Vite, TS) ──/api──► Nginx ──► FastAPI (API-only, modular layered monolith)
                                                          │  PostgreSQL (metadata, OCR, audit, FTS)
                                                          │  Redis (session TTL + hàng đợi)
                                                          ▼
                                    Celery worker (OCR in) / worker-hw (chữ viết tay, hàng đợi ocr_hw) / beat
                                                          │
                                                   Private storage (file gốc, ảnh trang)
```

- **Backend** `backend/app/modules/<module>/{presentation,application,domain,infrastructure}` + `module.py` (ModuleSpec).
  Quy tắc phụ thuộc R1–R10 kiểm tự động bằng **import-linter**.
- **6 điểm mở rộng**: module registry (`app/registry.py`), job kind registry (task chung `jobs.run`), domain event
  (phát sau commit), port (OcrEngine, StoragePort, Notifier), API truy vấn công khai, UI registry (`frontend/src/app/registry.ts`).
- **Cờ tính năng** `FEATURES_ENABLED`: router P2 chỉ gắn khi bật (tắt → 404); `/api/auth/me` trả `features` để React ẩn/hiện màn hình.
- **Giao diện:** design token + component dùng chung, icon `lucide-react`, nền **sáng/tối** (nút trên thanh tiêu đề:
  theo hệ thống → sáng → tối, lưu lựa chọn). Quy ước khi sửa giao diện: GUIDE mục 4.2.
- **Sao lưu (NFR-03):** service `backup` sao lưu hằng ngày database + file, mỗi bản tự thử khôi phục (GUIDE mục 6.4).

| Module lõi (MVP) | P2 (cờ) |
|---|---|
| auth, users, categories, documents, jobs, ocr, search, dashboard, audit | workflow (P2-01), highlight (P2-02), handwriting (P2-03), extraction (P2-04), classification (P2-05), versions (P2-06), borrowing + notifications (P2-07), imports (P2-08), rollback (P2-09) |

## Cấu trúc thư mục

```
backend/            FastAPI + Celery (app/, alembic/, tests/, eval/, scripts/)
frontend/           React + TypeScript + Vite (src/app, src/features/*, src/shared)
infra/nginx/        default.conf (SPA + reverse proxy /api, CSP)
infra/backup/       backup.sh (sao lưu/khôi phục, chạy trong service backup/restore)
docs/openapi.json   hợp đồng API (sinh types React: npm run gen:api)
document/           đặc tả v0.8: SDD, Đặc tả đề tài, Use Case/Sequence/ERD (+ khảo sát); script CSDL v0.7 (lên v0.8 cùng migration 0108)
tests/e2e/          Playwright (Python) chạy trên hệ thống thật
.github/workflows/  backend.yml, frontend.yml, e2e.yml (ma trận cờ P2), compose.yml (Docker + sao lưu)
compose.yaml        Docker Compose (profile hw, rag, tools); compose.dev.yaml
scripts/            demo_start/stop.ps1 (demo một chạm), docker_start/stop.ps1
```

## Chạy nhanh

- **Demo trên Windows (không cần Docker/Redis):** bấm đúp `demo-start.cmd` → mở http://127.0.0.1:8080.
  Trong PowerShell phải gõ `.\demo-start.cmd` (có `.\`). Dừng: `.\demo-stop.cmd`. Chi tiết: [GUIDE.md](GUIDE.md).
- **Docker (giống production — Redis session/broker, worker + beat trong container):** cài Docker Desktop
  (GUIDE mục 6.1) rồi `.\docker-start.cmd -Demo` → http://127.0.0.1:8080. Dừng: `.\docker-stop.cmd`.

Tài khoản demo: `admin / Admin@12345` (bản Docker: mật khẩu admin trong `.env`), `nhanvien`, `kiemduyet`, `ketoan`, `nguoidung` (Người dùng thông thường: chỉ xem tài liệu đã xuất bản) / `Demo@12345`.

## Kiểm thử

| Bộ | Lệnh | Kết quả hiện tại |
|---|---|---|
| Backend (SQLite) | `cd backend; .\.venv\Scripts\python.exe -m pytest -q` | 127 passed, 1 skipped |
| Backend, mọi cờ P2 bật (NFR-09) | `$env:TEST_FEATURES="all"; ... pytest -q` | 127 passed, 1 skipped |
| Backend trên PostgreSQL 18 + Redis | CI `backend.yml` (6 tổ hợp cờ) | xanh mỗi PR |
| Frontend | `cd frontend; npm test` | 30 passed |
| Lint/kiểu/ranh giới | ruff, mypy, lint-imports (5 contract), eslint, tsc, prettier | sạch |
| E2E | `pytest tests/e2e --browser chromium` (demo đang chạy) | 9 passed, 1 skipped (mọi cờ bật) |
| Docker + sao lưu/khôi phục | CI `compose.yml` | xanh |

Tài liệu khác: [GUIDE.md](GUIDE.md) (cài đặt, vận hành, Git/CI, sự cố) · [SUMMARY.md](SUMMARY.md) (trạng thái, truy vết, chênh lệch so với đặc tả)
· [backend/eval/README.md](backend/eval/README.md) (đánh giá NFR-08).
