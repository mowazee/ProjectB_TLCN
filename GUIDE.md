# Hướng dẫn cài đặt, vận hành và phát triển (ProjectB)

## 1. Yêu cầu

| Thành phần | Phiên bản đã dùng | Ghi chú |
|---|---|---|
| Python | 3.12 | `backend/.venv` |
| Node.js | 24 (npm 11) | cài bằng `winget install OpenJS.NodeJS.LTS` (theo user) |
| PostgreSQL | 14+ (máy dev: 18) | demo tạo cluster riêng trong `.demo\`, không đụng service đã cài |
| Redis | 7+ (Docker: 8) | bắt buộc ở production (session + hàng đợi). Redis không có bản Windows chính thức → chạy trong Docker (mục 6); demo mục 3 dùng session bộ nhớ + broker PostgreSQL |
| Docker Desktop | Compose v2, WSL2 | chạy giống production (`docker-start.cmd`, mục 6) |

## 2. Cài đặt lần đầu

```powershell
# Backend
cd D:\ProjectB_TLCN\backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt -c constraints.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt -c constraints.txt   # PaddleOCR (worker OCR); scikit-learn (P2-05) đã có trong requirements.txt
Copy-Item .env.example .env   # rồi sửa DATABASE_URL, REDIS_URL, mật khẩu

# Frontend
cd ..\frontend
npm ci
npm run gen:api               # sinh types từ docs/openapi.json
```

## 3. Demo một chạm (Windows)

```powershell
cd D:\ProjectB_TLCN
.\demo-start.cmd              # lần đầu: tạo DB demo, migrate, seed, worker, beat, API, build React
.\demo-start.cmd -Reset       # xóa sạch dữ liệu demo và tạo lại
.\demo-start.cmd -Mvp         # chỉ MVP (tắt mọi cờ P2)
.\demo-start.cmd -Rebuild     # build lại giao diện sau khi sửa frontend
.\demo-stop.cmd               # dừng tất cả (dữ liệu giữ trong .demo\)
```

PowerShell không chạy file ở thư mục hiện tại nếu thiếu `.\` — lỗi `demo-stop.cmd is not recognized` nghĩa là bạn quên `.\`.
Bấm đúp file `.cmd` trong Explorer cũng được.

- Giao diện: http://127.0.0.1:8080 · API docs: http://127.0.0.1:8000/docs
- Cổng: 8080 (React, `vite preview` + proxy `/api`), 8000 (FastAPI), 55434 (PostgreSQL demo, chỉ 127.0.0.1).
- Nhật ký: `.demo\logs\` (api, worker, beat, web, postgres).

| Vai trò | Đăng nhập | Mật khẩu |
|---|---|---|
| Quản trị viên | admin | Admin@12345 |
| Nghiệp vụ (P. Hành chính) | nhanvien | Demo@12345 |
| Kiểm duyệt (P. Hành chính) | kiemduyet | Demo@12345 |
| Nghiệp vụ (P. Kế toán) | ketoan | Demo@12345 |

Gợi ý kịch bản demo: đăng nhập `nhanvien` → Tài liệu → mở hợp đồng mẫu → xem trang/sửa OCR (thử mở 2 tab để thấy 409) →
Tìm kiếm "nghiem thu" → mở kết quả (khung highlight) → gửi duyệt → đăng nhập `kiemduyet` (tab ẩn danh) → Duyệt tài liệu →
xuất bản; Mượn hồ sơ; Nhập hàng loạt (ZIP); `admin` → Nhật ký → Khôi phục.

## 4. Phát triển hằng ngày

```powershell
# Terminal 1: API (cần PostgreSQL + Redis, hoặc SESSION_BACKEND=memory cho dev)
cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
# Terminal 2: worker (+ beat)
.\.venv\Scripts\celery.exe -A app.workers.celery_app:celery_app worker -Q default,ocr -P solo -l info
.\.venv\Scripts\celery.exe -A app.workers.celery_app:celery_app beat -l info
# Terminal 3: React (Vite proxy /api -> 127.0.0.1:8000)
cd frontend; npm run dev        # http://localhost:5173
```

Worker chữ viết tay (P2-03) chạy riêng: `$env:WORKER_OCR_PROFILES="handwriting"; celery ... worker -Q ocr_hw`.

Khi đổi API: `python scripts/export_openapi.py` rồi `npm run gen:api` và commit cả `docs/openapi.json` lẫn `schema.d.ts`
(CI `frontend.yml` báo lỗi nếu lệch).

### Thêm một tính năng P2/P3 (Đặc tả đề tài 4.9)
1. Backend: tạo `app/modules/<tên>/` 4 lớp + `module.py` với `feature="<tên>"`; thêm **1 dòng** vào `app/registry.py`,
   tên cờ vào `config.ALL_FEATURES` và `.env.example`; migration riêng `alembic/versions/01xx_p2_<tên>.py`.
2. Frontend: tạo `src/features/<tên>/manifest.tsx` (lazy), thêm **1 dòng** vào `src/app/registry.ts`.
3. Không sửa file của module lõi; cắm vào slot/route/event/job kind sẵn có.

## 5. Kiểm thử và chất lượng

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q                         # SQLite tạm, session trên fakeredis
$env:TEST_REDIS_URL="redis://127.0.0.1:6379/15"   # session trên Redis thật (docker-start -Dev); DB 15 bị xóa mỗi test
$env:TEST_FEATURES="all"; .\.venv\Scripts\python.exe -m pytest -q; $env:TEST_FEATURES=$null   # NFR-09
$env:TEST_DATABASE_URL="postgresql+psycopg://postgres@127.0.0.1:55434/dms_test"   # chạy trên PostgreSQL
.\.venv\Scripts\ruff.exe check . ; .\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m mypy app scripts eval ; .\.venv\Scripts\lint-imports.exe

cd ..\frontend
npm run lint; npm run typecheck; npm run format:check; npm test; npm run build

# E2E (khi demo đang chạy)
cd ..; backend\.venv\Scripts\python.exe -m playwright install chromium   # lần đầu
backend\.venv\Scripts\python.exe -m pytest tests\e2e --browser chromium
```

Đánh giá chất lượng OCR (NFR-08): xem `backend/eval/README.md`.

## 6. Chạy bằng Docker (Redis + Celery worker trong container, giống production)

Khác với demo ở mục 3 (session bộ nhớ + broker PostgreSQL), bản Docker chạy đúng kiến trúc SDD:
Redis giữ session đăng nhập (ADR-AUTH-003) và làm broker Celery; worker OCR, beat chạy trong container Linux.

### 6.1 Cài Docker Desktop trên Windows (một lần, cần quyền Administrator)

```powershell
# PowerShell "Run as administrator"
wsl --install --no-distribution          # bật WSL2 + Virtual Machine Platform -> KHỞI ĐỘNG LẠI MÁY
winget install -e --id Docker.DockerDesktop
```

Mở Docker Desktop, chấp nhận điều khoản (không cần đăng nhập), đợi góc dưới trái báo **Engine running**.
Windows Home không có Hyper-V nên Docker luôn chạy bằng WSL2 và **không hiện** tùy chọn "Use WSL 2 based engine" —
không cần chọn gì. Kiểm tra: `docker version` (Server: linux) và `wsl -l -v` (docker-desktop, VERSION 2).
RAM cho Docker do WSL2 tự cấp (mặc định ~50% RAM máy); worker OCR cần ~2-3 GB.

### 6.2 Chạy

```powershell
cd D:\ProjectB_TLCN
.\docker-start.cmd -Demo        # lần đầu: tạo .env (mật khẩu ngẫu nhiên), build image ~10-20 phút, seed dữ liệu demo
.\docker-start.cmd              # các lần sau / môi trường thật: chỉ tạo admin nếu chưa có
.\docker-start.cmd -Hw          # + worker chữ viết tay (P2-03, hàng đợi ocr_hw)
.\docker-start.cmd -Dev         # mở Postgres 127.0.0.1:55433, Redis 127.0.0.1:6379, API :8000 (reload theo code)
.\docker-start.cmd -Build       # build lại image sau khi sửa code
.\docker-stop.cmd               # dừng (giữ dữ liệu)   -Down: xóa container   -Purge: XÓA HẾT dữ liệu
```

Không chạy song song với demo mục 3 (cùng cổng 8080): `.\demo-stop.cmd` trước.
Mật khẩu admin nằm trong `.env` (`DEMO_ADMIN_PASSWORD`). Lệnh thường dùng:

```powershell
docker compose ps                          # trạng thái (api/web/postgres/redis: healthy)
docker compose logs -f api worker          # log
docker compose up -d --scale worker=2      # thêm worker OCR (mỗi worker ~2-3 GB RAM)
docker compose exec redis redis-cli info keyspace   # session/hàng đợi trong Redis
```

| Container | Vai trò | Ghi chú ổn định |
|---|---|---|
| postgres | CSDL | volume `pgdata`; không mở cổng ra ngoài (trừ `-Dev`) |
| redis | session + broker | AOF (`appendonly yes`) → restart không mất session/job đang chờ; `noeviction` |
| migrate | `alembic upgrade head` rồi thoát | api/worker/beat chỉ chạy sau khi migrate thành công |
| api | FastAPI | healthcheck `/health`; Redis mất → API trả 503 `SERVICE_UNAVAILABLE` (không treo) |
| worker | Celery `-P solo`, hàng đợi `default,ocr` | worker chết giữa job → khi container khởi động lại tự nhận lại job dở (log "Nhận lại … job bị bỏ dở"); worker chết hẳn → beat gửi lại sau `JOB_STALE_SECONDS`; runner claim theo DB nên không chạy trùng; mất Redis → tự kết nối lại. Chạy nhiều worker ngoài Docker trên cùng máy: đặt `WORKER_NAME` khác nhau |
| beat | purge, gửi lại job kẹt, nhắc quá hạn | chỉ chạy **1** bản |
| web | Nginx + React | chỉ nghe `127.0.0.1:8080` (đổi `WEB_BIND` trong `.env`) |

### 6.3 Lên server thật

1. Sao chép `.env.docker.example` → `.env`, đặt mật khẩu mạnh, `ALLOWED_ORIGINS=https://ten-mien`, `WEB_BIND=127.0.0.1`.
2. Đặt reverse proxy HTTPS (Caddy/Nginx/Traefik) phía trước cổng `WEB_PORT`; cookie session là `Secure` khi `APP_ENV=production`.
3. `docker compose up -d --build` rồi `docker compose run --rm --no-deps api python scripts/seed_demo.py --admin-only`
   (ở production script từ chối tạo tài khoản demo và bắt buộc có `DEMO_ADMIN_PASSWORD`).
4. Sao lưu: `docker compose exec postgres pg_dump -U dms dms > backup.sql` + volume `storage` (cùng thời điểm);
   thử khôi phục trước khi đưa vào dùng (NFR-03).

CI `compose.yml` chạy đúng quy trình này trên GitHub (build → up → E2E qua Nginx → restart Redis).

## 7. Sự cố thường gặp

| Hiện tượng | Nguyên nhân / cách xử lý |
|---|---|
| Worker dừng ngay, log có `Application Control policy has blocked this file` | Windows Smart App Control chặn DLL (libpaddle, sklearn `_liblinear` — PaddleX tự import scikit-learn). Tắt Smart App Control (Windows Security → App & browser control) hoặc chạy worker bằng Docker (mục 6). |
| Worker khởi động rất lâu (~2 phút) | PaddleX kiểm tra nguồn model; giữ `OCR_MODEL_SOURCE_CHECK=false`. |
| `paddle` lỗi oneDNN | Dùng `paddlepaddle>=3.2,<3.3` (đã ghim trong requirements-ocr.txt). |
| Job đứng ở "Đang chờ" | Worker chưa chạy hoặc không nghe đúng hàng đợi (`default,ocr`, chữ viết tay `ocr_hw`); beat gửi lại job kẹt sau `JOB_REQUEUE_AFTER_SECONDS`. |
| 403 `CSRF_FAILED` / `ORIGIN_REJECTED` | Truy cập khác origin cấu hình: thêm origin vào `ALLOWED_ORIGINS`; tải lại trang để lấy CSRF token mới. |
| `Cổng 8080 đang được dùng` | Demo đang chạy → `.\demo-stop.cmd`, hoặc `.\demo-start.cmd -Port 8081`. |
| Gõ `docker ...` báo "not recognized" | Terminal mở trước khi cài Docker nên PATH cũ: mở terminal mới (hoặc khởi động lại VS Code). `docker-start.cmd`/`docker-stop.cmd` tự xử lý được. |
| `docker-start` báo "Docker chưa chạy" | Mở Docker Desktop, đợi "Engine running". Lỗi WSL → `wsl --update` (admin) rồi khởi động lại. |
| Container worker restart liên tục | `docker compose logs worker`: thiếu RAM (tăng RAM cho Docker) hoặc không tải được model (mạng). Job vẫn nằm trong Redis, chạy lại khi worker lên. |
| API trả 503 `SERVICE_UNAVAILABLE` | Redis không truy cập được: `docker compose ps redis`, `docker compose restart redis`. |
| npm báo xung đột TypeScript | Giữ `typescript ~5.9` (typescript-eslint và openapi-typescript chưa hỗ trợ TS 6/7). |
