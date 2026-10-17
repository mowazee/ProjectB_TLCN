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
- Giao diện sáng/tối: nút ở thanh tiêu đề (và góc trang đăng nhập), bấm để chuyển Theo hệ thống → Sáng → Tối.

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

### 4.1 Thêm một tính năng P2/P3 (Đặc tả đề tài 4.9)
1. Backend: tạo `app/modules/<tên>/` 4 lớp + `module.py` với `feature="<tên>"`; thêm **1 dòng** vào `app/registry.py`,
   tên cờ vào `config.ALL_FEATURES` và `.env.example`; migration riêng `alembic/versions/01xx_p2_<tên>.py`.
2. Frontend: tạo `src/features/<tên>/manifest.tsx` (lazy), thêm **1 dòng** vào `src/app/registry.ts`.
3. Không sửa file của module lõi; cắm vào slot/route/event/job kind sẵn có.

### 4.2 Quy ước giao diện (sáng/tối, icon)

- **Màu chỉ dùng biến CSS** trong `src/shared/styles/global.css` (`--c-surface`, `--c-text`, `--c-muted`,
  `--c-border`, `--c-primary`, `--tone-*`, `--chart-*`...). Mỗi biến có giá trị sáng (`:root`) và tối
  (`:root[data-theme="dark"]`). Viết cứng `#fff`, `#334155`... thì nền tối sẽ sai màu. Ngoại lệ có chủ đích:
  trang scan dùng `--c-paper` (luôn trắng, vì là nội dung); sidebar và nửa trái trang đăng nhập vốn tối ở cả hai chế độ.
- Thêm màu mới: khai báo biến ở **cả hai** khối trong `global.css`, chọn giá trị tối riêng (không đảo màu tự động).
- **Biểu đồ Chart.js** không đọc được `var(--x)`: lấy màu bằng `cssVar("--chart-…")` (`src/shared/theme.ts`) và
  gắn `key={theme}` (từ `useTheme()`) để vẽ lại khi đổi chế độ — xem `DashboardPage.tsx`. Một chuỗi số liệu dùng
  `--chart-series-1`; màu trạng thái luôn kèm icon + chữ.
- **Icon:** `lucide-react`, luôn `aria-hidden`. Nút chỉ có icon phải có `aria-label` (và `title`). Không đổi tên hiển
  thị của nút mà test đang tìm (`get_by_role(..., name=...)` của Playwright khớp **chuỗi con**: nhãn phụ như nút ẩn/hiện
  mật khẩu không được chứa chữ "Mật khẩu").
- Lớp dùng chung: `.btn` (+ `btn-primary`, `btn-danger`, `btn-ghost`, `btn-sm`, `btn-icon`), `.input/.select/.textarea`,
  `.card`, `.table`; component `PageHeader` (có `icon`), `EmptyState` (có `icon`), `Badge`, `Modal`, `Tabs` trong
  `src/shared/components/ui.tsx`. Không đặt `display: flex` trực tiếp lên `<td>` (lệch hàng bảng) — bọc bằng `<div className="row">`.
- Giao diện sáng/tối được đặt trước khi React chạy bởi `public/theme-init.js` (file tĩnh, vì CSP của Nginx chặn
  script inline). Đổi khóa lưu (`theme`) thì sửa cả file này lẫn `src/shared/theme.ts`.

### 4.3 OCR chữ viết tay (P2-03, VietOCR)

Tài liệu tick **"Chữ viết tay"** khi upload (hoặc "Chạy lại OCR – chữ viết tay" ở trang chi tiết) được OCR bằng
engine riêng trên hàng đợi `ocr_hw`. `OCR_HW_ENGINE=auto` (mặc định) chọn **VietOCR** nếu đã cài, không thì lùi về
PaddleOCR (`paddleocr-hw`, model chữ in — thường không đạt với chữ viết tay).

Cài VietOCR một lần (thêm PyTorch ~ vài trăm MB; **không** dùng `pip install vietocr` thường vì gói ghim Pillow cũ):

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-hw.txt -c constraints.txt
.\.venv\Scripts\python.exe -m pip install vietocr==0.3.13 --no-deps
.\.venv\Scripts\python.exe scripts\setup_handwriting.py           # tải model (~150 MB) vào cache + chạy thử
.\.venv\Scripts\python.exe scripts\setup_handwriting.py anh.jpg   # thử trên ảnh của bạn, in text nhận được
```

Model lưu ở `VIETOCR_CACHE_DIR` (mặc định `%USERPROFILE%\.cache\vietocr`), tải một lần, sau đó chạy không cần mạng.
Demo (mục 3) tự kiểm tra và in "Engine chữ viết tay: VietOCR" khi khởi động. Docker: `.\docker-start.cmd -Hw`
build image riêng `docso-backend-hw` (PyTorch CPU) cho `worker-hw`; image chung của api/worker không mang thêm.

**Đo độ chính xác (mục tiêu > 70%, D-06) ngay trên dữ liệu trong ứng dụng:** upload ảnh chữ viết tay → OCR tự chạy →
mở OCR Editor, sửa text cho **đúng hoàn toàn** với bản gốc (cả dấu, xuống dòng) → Lưu → chạy
`.\.venv\Scripts\python.exe eval\handwriting_from_app.py` (đọc database demo; `--database-url` cho nơi khác).
Script so text OCR thô với bản đã sửa, in độ chính xác từng trang và theo engine, ghi JSON vào `eval\reports\`.
Chưa đạt thì thử engine/cấu hình khác (`OCR_HW_ENGINE`, `VIETOCR_CONFIG`), chạy lại OCR các tài liệu đó
("Chạy lại OCR – chữ viết tay"), sửa lại và đo lại — script chỉ tính bản sửa mới hơn lần OCR gần nhất.

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
4. Sao lưu tự động đã chạy cùng `docker compose up -d` (service `backup`, mục 6.4). Đặt `BACKUP_DIR` ra ổ khác
   và chép định kỳ ra ngoài máy; chạy thử một lần khôi phục trước khi đưa vào dùng (NFR-03).

CI `compose.yml` chạy đúng quy trình này trên GitHub (build → up → E2E qua Nginx → restart Redis → sao lưu,
xóa dữ liệu, khôi phục).

### 6.4 Sao lưu và khôi phục (NFR-03)

Service `backup` (script `infra/backup/backup.sh`) mỗi ngày lúc `BACKUP_AT` (giờ **UTC**; mặc định `19:30` =
02:30 giờ Việt Nam) tạo một thư mục trong `BACKUP_DIR` (mặc định `./backups`, đã `.gitignore`):

| File | Nội dung |
|---|---|
| `db.dump` | `pg_dump -Fc` toàn bộ database |
| `storage.tar.gz` | toàn bộ volume `storage` (file gốc, ảnh trang) |
| `SHA256SUMS`, `info.txt`, `counts.txt` | checksum; thời điểm, revision Alembic, dung lượng; số dòng các bảng chính |
| `STATUS` | `OK`, `WARN` hoặc `FAILED` (chi tiết trong `STATUS.detail`, `verify.log`) |

**Mỗi bản sao lưu đều được tự thử khôi phục:** script khôi phục `db.dump` vào database tạm, so revision Alembic
và số bảng, kiểm tra `audit_logs` không nhiều hơn hiện tại (audit chỉ ghi thêm), kiểm tra mọi file mà database
tham chiếu đều có trong `storage.tar.gz`, rồi xóa database tạm. `WARN` khi thiếu file (chỉ xảy ra nếu purge xóa
file đúng lúc sao lưu); `FAILED` khi checksum/khôi phục lỗi. Giữ `BACKUP_KEEP` bản gần nhất không `FAILED`.

```powershell
docker compose logs backup                                   # lịch và kết quả các lần sao lưu
docker compose exec backup sh /backup/backup.sh run          # sao lưu ngay (vd. trước khi nâng cấp)
docker compose exec backup sh /backup/backup.sh list         # danh sách bản sao lưu + kết quả kiểm tra
```

Khôi phục (ghi đè database **và** storage bằng bản đã chọn):

```powershell
docker compose stop api worker beat                          # bắt buộc: không còn ai ghi dữ liệu
docker compose --profile tools run --rm restore 20261016-193000 --yes
docker compose up -d
```

Lệnh `restore` từ chối chạy nếu thiếu `--yes`, nếu bản đã chọn `FAILED` hoặc sai checksum, hoặc nếu còn kết nối
tới database (quên dừng api/worker/beat; `--force` để bỏ qua). Trước khi ghi đè, nó tự tạo bản `…-pre-restore`
của trạng thái hiện tại, nên khôi phục nhầm vẫn quay lại được. Thứ tự sao lưu là database trước, file sau: file
upload trong lúc sao lưu chỉ thành file thừa, không có bản ghi trỏ tới file thiếu.

Bản sao lưu nằm trên cùng máy thì không chống được hỏng ổ hay mất máy: chép `BACKUP_DIR` ra ngoài (ổ ngoài,
Google Drive, máy khác) theo lịch. Demo Windows (mục 3, `.demo\`) là dữ liệu thử, không sao lưu.

## 7. Git, GitHub và CI

Repo: https://github.com/mowazee/ProjectB_TLCN (public từ 13/10/2026; nhánh chính `main`).

### 7.1 Quy trình làm việc (nhánh + Pull Request)

```powershell
git switch main; git pull                        # luôn bắt đầu từ main mới nhất
git switch -c feat/p2-05-nguong-phan-loai        # 1 nhánh / 1 việc: feat/..., fix/..., docs/..., ci/...
# ... sửa code, chạy test local (mục 5) ...
git add -A; git commit -m "feat(classification): ..."
git push -u origin HEAD
gh pr create --fill                              # hoặc mở PR trên web
gh pr checks --watch                             # xem CI chạy
# CI xanh + 1 bạn review "Approve" -> Squash and merge trên web (hoặc: gh pr merge --squash --delete-branch)
git switch main; git pull
```

Quy ước nhóm: **không push thẳng vào `main`**, **không merge khi CI đỏ**, mỗi PR có ít nhất 1 người review.

Repo public nên GitHub cho dùng ruleset. Ruleset `protect-main` (Settings → Rules → Rulesets, từ 13/10/2026) tự chặn:

| Luật | Ý nghĩa |
|---|---|
| Require a pull request | Không push thẳng vào `main`; cần **1 approve**, phải resolve hết comment; push thêm commit thì approve cũ bị hủy |
| Allowed merge methods: Squash | Chỉ "Squash and merge": cả PR thành 1 commit trên `main` |
| Require linear history | Lịch sử `main` thẳng, không có merge commit |
| Block force pushes, Restrict deletions | Không force-push, không xóa `main` |
| Bypass: Admin (chỉ qua PR) | Admin được merge PR khi chưa đủ điều kiện (vd. làm một mình, không ai approve); vẫn không push thẳng được |

Ruleset **chưa có** "Require status checks to pass": CI đỏ vẫn bấm merge được, nên quy ước "không merge khi CI đỏ"
vẫn phải tự giữ. Muốn GitHub tự chặn: sửa ruleset → bật *Require status checks to pass* → thêm các check
`lint`, `test`, `migrations`, `build`, `openapi-drift`, `e2e (mvp)` (không thêm `compose`: workflow này chỉ chạy
khi PR đổi Docker/infra, check bắt buộc mà không chạy sẽ treo PR ở "pending").

Squash merge làm commit trên nhánh khác commit trên `main` (cùng nội dung), nên sau khi merge xóa nhánh bằng
`git branch -D <nhánh>` (hoặc `gh pr merge --squash --delete-branch` làm luôn).

### 7.2 CI chạy những gì

| Workflow | Khi nào | Kiểm tra |
|---|---|---|
| `backend.yml` | mọi PR; push `main` khi đổi backend | ruff, mypy, import-linter, bandit, pip-audit (báo cáo); pytest × 6 tổ hợp cờ P2 trên PostgreSQL 18 + Redis thật; Alembic upgrade → check → downgrade → upgrade |
| `frontend.yml` | mọi PR; push `main` khi đổi frontend/API | ESLint, tsc, Prettier, Vitest, build; `openapi-drift` (types React phải khớp API) |
| `e2e.yml` | mọi PR | Playwright trên hệ thống thật × 3 tổ hợp cờ (MVP, P2 đợt 1, tất cả) |
| `compose.yml` | PR đổi Docker/infra; push `main` | build image → `docker compose up` → E2E qua Nginx → restart Redis → sao lưu, xóa dữ liệu, khôi phục (NFR-03) |

Khi CI đỏ: mở PR → tab Checks → job đỏ → bước đỏ để xem log; hoặc `gh run view <id> --log-failed`.

### 7.3 Khóa phiên bản thư viện

`backend/constraints.txt` ghi đúng phiên bản đã kiểm thử; CI, Dockerfile và mục 2 đều cài với `-c constraints.txt`
(không có nó, CI từng tự kéo pydantic/FastAPI mới hơn máy dev → kết quả khác nhau). Nâng cấp thư viện = một PR riêng:
sửa phiên bản trong file, chạy test, để CI xác nhận.

## 8. Sự cố thường gặp

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
| Sửa frontend nhưng demo vẫn hiện giao diện cũ | Demo phục vụ bản build: `.\demo-start.cmd -Rebuild` (hoặc `cd frontend; npm run build`) rồi Ctrl+F5. Bản Docker: `.\docker-start.cmd -Build`. |
| Một phần giao diện vẫn sáng khi bật nền tối | Màu bị viết cứng trong CSS/TSX: đổi sang biến (mục 4.2). Tìm nhanh: `grep -rnE "#[0-9a-fA-F]{3,6}" frontend/src --include=*.css`. |
| npm báo xung đột TypeScript | Giữ `typescript ~5.9` (typescript-eslint và openapi-typescript chưa hỗ trợ TS 6/7). |
