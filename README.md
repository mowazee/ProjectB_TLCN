# Hệ thống số hóa hồ sơ tài liệu doanh nghiệp (ProjectB — SDD v0.5)

Tiểu luận chuyên ngành — UTE, Nhóm 3. Mọi yêu cầu, tên dữ liệu và hợp đồng API bám theo
**SDD v0.5** (`Tài liệu/0 -Dac_ta_SDD_v0.5.docx`). Kỳ này thực hiện **MVP + toàn bộ P2 (P2-01…P2-09)**; P3 (RAG) để học kỳ sau.

ProjectB được dựng mới hoàn toàn theo baseline v0.5 (React SPA + FastAPI API-only, modular monolith có điểm mở rộng).
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

| Module lõi (MVP) | P2 (cờ) |
|---|---|
| auth, users, categories, documents, jobs, ocr, search, dashboard, audit | workflow (P2-01), highlight (P2-02), handwriting (P2-03), extraction (P2-04), classification (P2-05), versions (P2-06), borrowing + notifications (P2-07), imports (P2-08), rollback (P2-09) |

## Cấu trúc thư mục

```
backend/            FastAPI + Celery (app/, alembic/, tests/, eval/, scripts/)
frontend/           React + TypeScript + Vite (src/app, src/features/*, src/shared)
infra/nginx/        default.conf (SPA + reverse proxy /api)
docs/openapi.json   hợp đồng API (sinh types React: npm run gen:api)
tests/e2e/          Playwright (Python) chạy trên hệ thống thật
.github/workflows/  backend.yml, frontend.yml, e2e.yml (ma trận cờ P2)
compose.yaml        Docker Compose (profile hw, rag); compose.dev.yaml
scripts/            demo_start.ps1 / demo_stop.ps1 (demo một chạm trên Windows)
```

## Chạy nhanh

- **Demo trên Windows (không cần Docker/Redis):** bấm đúp `demo-start.cmd` → mở http://127.0.0.1:8080.
  Trong PowerShell phải gõ `.\demo-start.cmd` (có `.\`). Dừng: `.\demo-stop.cmd`. Chi tiết: [GUIDE.md](GUIDE.md).
- **Docker (giống production — Redis session/broker, worker + beat trong container):** cài Docker Desktop
  (GUIDE mục 6.1) rồi `.\docker-start.cmd -Demo` → http://127.0.0.1:8080. Dừng: `.\docker-stop.cmd`.

Tài khoản demo: `admin / Admin@12345` (bản Docker: mật khẩu admin trong `.env`), `nhanvien`, `kiemduyet`, `ketoan` / `Demo@12345`.

## Kiểm thử

| Bộ | Lệnh | Kết quả hiện tại |
|---|---|---|
| Backend (SQLite) | `cd backend; .\.venv\Scripts\python.exe -m pytest -q` | 93 passed |
| Backend, mọi cờ P2 bật (NFR-09) | `$env:TEST_FEATURES="all"; ... pytest -q` | 93 passed |
| Backend trên PostgreSQL | `$env:TEST_DATABASE_URL="postgresql+psycopg://..."` | 90/90 passed (cả tắt/bật cờ) |
| Frontend | `cd frontend; npm test` | 17 passed |
| Lint/kiểu/ranh giới | ruff, mypy, lint-imports (5 contract), eslint, tsc, prettier | sạch |
| E2E | `pytest tests/e2e --browser chromium` (hệ thống đang chạy) | xem SUMMARY.md |

Tài liệu khác: [GUIDE.md](GUIDE.md) (cài đặt, vận hành, sự cố) · [SUMMARY.md](SUMMARY.md) (trạng thái, truy vết, chênh lệch so với đặc tả)
· [backend/eval/README.md](backend/eval/README.md) (đánh giá NFR-08).
