<#
.SYNOPSIS
    Khởi động bản demo ProjectB: PostgreSQL riêng + migration + dữ liệu mẫu + worker OCR + beat + API + React.

.DESCRIPTION
    Mọi dữ liệu demo nằm trong .demo\ (không đụng PostgreSQL đã cài trên máy). Database demo dùng bộ cài
    PostgreSQL có sẵn, chạy ở cổng 55434, chỉ nhận kết nối từ 127.0.0.1. Hàng đợi dùng chính PostgreSQL làm
    broker và session lưu trong bộ nhớ API (máy dev không chạy được Redis) - chỉ cho demo, production dùng Redis.

    Chạy: bấm đúp demo-start.cmd, hoặc trong PowerShell:  .\demo-start.cmd [-Reset] [-NoBrowser] [-Port 8080] [-Mvp]

.PARAMETER Reset   Xóa dữ liệu demo cũ (.demo\) rồi tạo lại.
.PARAMETER Mvp     Chỉ chạy lõi MVP (tắt mọi cờ P2).
.PARAMETER Rebuild Build lại giao diện React.
#>
param(
    [switch]$Reset,
    [switch]$NoBrowser,
    [switch]$Mvp,
    [switch]$Rebuild,
    [int]$Port = 8080
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$Root     = Split-Path -Parent $PSScriptRoot
$Backend  = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$Demo     = Join-Path $Root '.demo'
$PgData   = Join-Path $Demo 'pgdata'
$Logs     = Join-Path $Demo 'logs'
$Storage  = Join-Path $Demo 'storage'
$PidFile  = Join-Path $Demo 'pids.txt'
$PgPort   = 55434
$ApiPort  = 8000
$DbName   = 'dms_demo'
$Py       = Join-Path $Backend '.venv\Scripts\python.exe'
$AllFeatures = 'workflow,highlight,handwriting,extraction,classification,versions,borrowing,notifications,imports,rollback'

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

function Find-PgBin {
    $found = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\pg_ctl.exe' -ErrorAction SilentlyContinue |
        Sort-Object { $n = 0; [void][int]::TryParse($_.Directory.Parent.Name, [ref]$n); $n } -Descending |
        Select-Object -First 1
    if (-not $found) { throw 'Không tìm thấy PostgreSQL trong C:\Program Files\PostgreSQL (xem GUIDE.md mục 2).' }
    return $found.DirectoryName
}

function Wait-Url($url, $seconds) {
    for ($i = 0; $i -lt $seconds; $i++) {
        try { Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true } catch { Start-Sleep 1 }
    }
    return $false
}

# Node (cài theo user bằng winget) có thể chưa có trong PATH của phiên này
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
if (-not (Test-Path $Py)) { throw 'Chưa có backend\.venv. Làm theo GUIDE.md mục 2 rồi chạy lại.' }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Chưa cài Node.js (GUIDE.md mục 2).' }
$PgBin = Find-PgBin

if ($Reset -and (Test-Path $Demo)) {
    Step 'Dừng demo đang chạy và xóa dữ liệu demo cũ'
    & (Join-Path $PSScriptRoot 'demo_stop.ps1') -Quiet
    Start-Sleep 2
    Remove-Item $Demo -Recurse -Force
}
foreach ($p in @($Port, $ApiPort)) {
    if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) {
        throw "Cổng $p đang được dùng (có thể demo đã chạy). Chạy .\demo-stop.cmd trước, hoặc dùng -Port khác."
    }
}
New-Item -ItemType Directory -Force $Logs, $Storage | Out-Null

# ---------------------------------------------------------------- PostgreSQL riêng cho demo
if (-not (Test-Path (Join-Path $PgData 'PG_VERSION'))) {
    Step "Tạo PostgreSQL cluster cho demo ($PgData)"
    & "$PgBin\initdb.exe" -D $PgData -U postgres -A trust -E UTF8 --locale=C | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'initdb thất bại' }
    Add-Content -Path (Join-Path $PgData 'postgresql.conf') -Encoding ASCII -Value @(
        '', '# demo', "listen_addresses = '127.0.0.1'", "port = $PgPort"
    )
}
& "$PgBin\pg_ctl.exe" -D $PgData status *> $null
if ($LASTEXITCODE -ne 0) {
    Step "Khởi động PostgreSQL demo (cổng $PgPort)"
    Start-Process -FilePath "$PgBin\pg_ctl.exe" -WindowStyle Hidden `
        -ArgumentList @('-D', "`"$PgData`"", '-l', "`"$Logs\postgres.log`"", 'start')
}
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    & "$PgBin\pg_isready.exe" -h 127.0.0.1 -p $PgPort *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep 1
}
if (-not $ready) { throw "PostgreSQL demo không khởi động được, xem $Logs\postgres.log" }
$exists = & "$PgBin\psql.exe" -h 127.0.0.1 -p $PgPort -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DbName'"
if ("$exists".Trim() -ne '1') {
    Step "Tạo database $DbName"
    & "$PgBin\psql.exe" -h 127.0.0.1 -p $PgPort -U postgres -qc "CREATE DATABASE $DbName" | Out-Null
}

# ---------------------------------------------------------------- cấu hình cho tiến trình con
$env:APP_ENV            = 'development'
$env:DATABASE_URL       = "postgresql+psycopg://postgres@127.0.0.1:$PgPort/$DbName"
$env:CELERY_BROKER_URL  = "sqla+postgresql+psycopg://postgres@127.0.0.1:$PgPort/$DbName"
$env:SESSION_BACKEND    = 'memory'
$env:STORAGE_ROOT       = $Storage
$env:FEATURES_ENABLED   = $(if ($Mvp) { '' } else { $AllFeatures })
$env:ALLOWED_ORIGINS    = "http://127.0.0.1:$Port,http://localhost:$Port"
$env:WORKER_OCR_PROFILES = 'print'
$env:PYTHONIOENCODING   = 'utf-8'
$env:PYTHONUTF8         = '1'
$env:VITE_DEV_API_TARGET = "http://127.0.0.1:$ApiPort"

$procs = @()
Push-Location $Backend
try {
    Step 'Cập nhật schema (alembic upgrade head)'
    $ErrorActionPreference = 'Continue'   # alembic ghi INFO ra stderr
    & (Join-Path $Backend '.venv\Scripts\alembic.exe') upgrade head *>> "$Logs\alembic.log"
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($code -ne 0) { throw "Migration thất bại, xem $Logs\alembic.log" }

    Step 'Nạp dữ liệu mẫu'
    & $Py (Join-Path $Backend 'scripts\seed_demo.py')
    if ($LASTEXITCODE -ne 0) { throw 'Nạp dữ liệu mẫu thất bại' }

    if (-not $Mvp) {
        # P2-03: OCR_HW_ENGINE=auto -> VietOCR nếu đã cài (backend\requirements-hw.txt). Tải trước cấu hình +
        # weights (~150 MB, một lần) để job chữ viết tay đầu tiên không phải chờ tải. Lỗi ở đây không chặn demo.
        Step 'Chuẩn bị OCR chữ viết tay (P2-03)'
        $ErrorActionPreference = 'Continue'   # import torch/paddle ghi cảnh báo ra stderr
        $hwEngine = & $Py -c "from app.modules.ocr.infrastructure.engines import handwriting as h; n = h.resolved_engine_name(); n == 'vietocr' and h.prepare_vietocr(); print(n)" 2>> "$Logs\handwriting.log"
        $code = $LASTEXITCODE
        $ErrorActionPreference = 'Stop'
        if ($code -ne 0) {
            Write-Host "    Không chuẩn bị được model chữ viết tay (xem $Logs\handwriting.log); OCR chữ in vẫn chạy." -ForegroundColor Yellow
        } elseif ($hwEngine -eq 'vietocr') {
            Write-Host '    Engine chữ viết tay: VietOCR (model đã sẵn trong cache)'
        } else {
            Write-Host "    Engine chữ viết tay: $hwEngine (chưa cài VietOCR - xem GUIDE mục 4.3)" -ForegroundColor Yellow
        }
    }

    # GUIDE 9: chữ in đọc bằng VietOCR khi đã cài (OCR_ENGINE=auto). Tải trước weights model chữ in (một lần) để worker
    # không phải chờ tải lúc khởi động.
    Step 'Chuẩn bị OCR chữ in'
    $ErrorActionPreference = 'Continue'
    $printEngine = & $Py -c "from app.modules.ocr.application.engines import resolved_print_engine as r; from app.shared.config import settings as s; n = r(); n == 'vietocr' and __import__('app.modules.ocr.infrastructure.engines.vietocr', fromlist=['x']).prepare_vietocr(s.OCR_VIETOCR_CONFIG); print(n)" 2>> "$Logs\handwriting.log"
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($code -ne 0) {
        Write-Host "    Không chuẩn bị được VietOCR (xem $Logs\handwriting.log)" -ForegroundColor Yellow
    } elseif ($printEngine -eq 'vietocr') {
        Write-Host '    Engine chữ in: VietOCR (đọc đúng dấu tiếng Việt)'
    } else {
        Write-Host "    Engine chữ in: $printEngine - chưa cài VietOCR nên dấu tiếng Việt kém (GUIDE mục 4.3, 9)" -ForegroundColor Yellow
    }

    Step 'Khởi động worker OCR (nạp model ~10-30 giây; hàng đợi default, ocr, ocr_hw)'
    $celery = Join-Path $Backend '.venv\Scripts\celery.exe'
    $worker = Start-Process -PassThru -WindowStyle Hidden -WorkingDirectory $Backend -FilePath $celery `
        -ArgumentList @('-A', 'app.workers.celery_app:celery_app', 'worker', '-Q', 'default,ocr,ocr_hw', '-P', 'solo', '-l', 'info') `
        -RedirectStandardOutput "$Logs\worker.log" -RedirectStandardError "$Logs\worker.err.log"
    $procs += $worker.Id
    $workerOk = $false
    for ($i = 0; $i -lt 180; $i++) {
        if ($worker.HasExited) { break }
        $log = Get-Content "$Logs\worker.err.log" -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
        if ($log -match 'celery@\S+ ready') { $workerOk = $true; break }
        Start-Sleep 1
    }
    if (-not $workerOk) {
        Get-Content "$Logs\worker.err.log" -Encoding UTF8 -Tail 5 | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
        throw ("Worker OCR không khởi động được (xem $Logs\worker.err.log). Nếu thấy 'Application Control policy " +
               "has blocked this file': Windows Smart App Control đang chặn một DLL, xem GUIDE.md mục Sự cố.")
    }

    Step 'Khởi động Celery beat (purge quá hạn, gửi lại job kẹt, nhắc mượn quá hạn)'
    $beat = Start-Process -PassThru -WindowStyle Hidden -WorkingDirectory $Backend -FilePath $celery `
        -ArgumentList @('-A', 'app.workers.celery_app:celery_app', 'beat', '-l', 'info', '-s', "`"$Demo\celerybeat-schedule`"") `
        -RedirectStandardOutput "$Logs\beat.log" -RedirectStandardError "$Logs\beat.err.log"
    $procs += $beat.Id

    Step "Khởi động API (http://127.0.0.1:$ApiPort)"
    $api = Start-Process -PassThru -WindowStyle Hidden -WorkingDirectory $Backend -FilePath $Py `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$ApiPort") `
        -RedirectStandardOutput "$Logs\api.log" -RedirectStandardError "$Logs\api.err.log"
    $procs += $api.Id
} finally {
    Pop-Location
    Set-Content -Path $PidFile -Value $procs -Encoding ASCII
}
if (-not (Wait-Url "http://127.0.0.1:$ApiPort/health" 60)) { throw "API không khởi động được, xem $Logs\api.err.log" }

# ---------------------------------------------------------------- React (build + vite preview, proxy /api)
Push-Location $Frontend
try {
    if (-not (Test-Path 'node_modules')) {
        Step 'Cài thư viện frontend (npm ci)'
        & npm ci --no-audit --no-fund *>> "$Logs\npm.log"
        if ($LASTEXITCODE -ne 0) { throw "npm ci thất bại, xem $Logs\npm.log" }
    }
    if ($Rebuild -or -not (Test-Path 'dist\index.html')) {
        Step 'Build giao diện React'
        & npm run build *>> "$Logs\npm.log"
        if ($LASTEXITCODE -ne 0) { throw "Build frontend thất bại, xem $Logs\npm.log" }
    }
    Step "Khởi động giao diện (http://127.0.0.1:$Port)"
    $web = Start-Process -PassThru -WindowStyle Hidden -WorkingDirectory $Frontend -FilePath 'node' `
        -ArgumentList @('node_modules\vite\bin\vite.js', 'preview', '--host', '127.0.0.1', '--port', "$Port", '--strictPort') `
        -RedirectStandardOutput "$Logs\web.log" -RedirectStandardError "$Logs\web.err.log"
    Add-Content -Path $PidFile -Value $web.Id -Encoding ASCII
} finally {
    Pop-Location
}
if (-not (Wait-Url "http://127.0.0.1:$Port/" 60)) { throw "Giao diện không khởi động được, xem $Logs\web.err.log" }

Write-Host ''
Write-Host "Demo đang chạy: http://127.0.0.1:$Port   (API docs: http://127.0.0.1:$ApiPort/docs)" -ForegroundColor Green
Write-Host "Cờ P2: $(if ($Mvp) { '(tắt - chỉ MVP)' } else { 'bật tất cả' })"
Write-Host ''
Write-Host '  Vai trò                Tên đăng nhập   Mật khẩu'
Write-Host '  Quản trị viên          admin           Admin@12345'
Write-Host '  Nhân viên nghiệp vụ    nhanvien        Demo@12345   (Phòng Hành chính - Tổng hợp)'
Write-Host '  Kiểm duyệt viên        kiemduyet       Demo@12345   (Phòng Hành chính - Tổng hợp)'
Write-Host '  Nhân viên nghiệp vụ    ketoan          Demo@12345   (Phòng Kế toán)'
Write-Host '  Người dùng thông thường nguoidung       Demo@12345   (Phòng Hành chính - Tổng hợp; chỉ xem tài liệu đã xuất bản)'
Write-Host ''
Write-Host 'Tài liệu mẫu được OCR ở nền trong khoảng 1-2 phút.'
Write-Host "Nhật ký: $Logs     Dừng demo: .\demo-stop.cmd"
if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port" }
