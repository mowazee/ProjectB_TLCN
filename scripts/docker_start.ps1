<#
.SYNOPSIS
    Chạy toàn bộ hệ thống bằng Docker Compose (giống production): Postgres, Redis, migrate, API,
    worker OCR, beat, web (Nginx + React).

.DESCRIPTION
    Redis dùng cho session đăng nhập + broker Celery; worker/beat chạy trong container Linux.
    Lần đầu: tạo .env (mật khẩu ngẫu nhiên), build image (~10-20 phút, tải PaddlePaddle) và worker
    tải model OCR (~vài phút). Các lần sau khởi động trong ~1 phút.

    .\docker-start.cmd                 production (chỉ tạo tài khoản admin)
    .\docker-start.cmd -Demo           + tài khoản demo và 4 tài liệu mẫu (để thử nghiệm)
    .\docker-start.cmd -Hw             + worker chữ viết tay (P2-03, profile hw)
    .\docker-start.cmd -Dev            mở cổng Postgres 55433 / Redis 6379 / API 8000, API tự reload
    .\docker-start.cmd -Build          build lại image (sau khi sửa code)

.PARAMETER Demo     Nạp dữ liệu demo (tài khoản mật khẩu công khai Demo@12345 - KHÔNG dùng khi triển khai thật).
#>
param(
    [switch]$Demo,
    [switch]$Hw,
    [switch]$Dev,
    [switch]$Build,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$Root = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $Root '.env'

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

function Read-DotEnv($path) {
    $map = @{}
    foreach ($line in Get-Content $path -Encoding UTF8) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') { $map[$Matches[1]] = $Matches[2] }
    }
    return $map
}

function New-Secret([int]$len = 24) {
    # Chỉ chữ + số: mật khẩu nằm trong DATABASE_URL, ký tự đặc biệt phải escape
    $chars = [char[]]'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
    $bytes = New-Object byte[] $len
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

function Invoke-Compose {
    # docker ghi tiến trình ra stderr; không để PowerShell coi đó là lỗi
    $ErrorActionPreference = 'Continue'
    & docker compose @ComposeArgs @args
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($code -ne 0) { throw "docker compose $($args -join ' ') thất bại (mã $code)" }
}

# ---------------------------------------------------------------- kiểm tra Docker
. (Join-Path $PSScriptRoot 'docker_path.ps1')
if (-not (Find-Docker)) {
    throw 'Chưa cài Docker Desktop. Xem GUIDE.md mục 6.1 để cài.'
}
$ErrorActionPreference = 'Continue'
docker info *> $null
$dockerOk = $LASTEXITCODE -eq 0
$ErrorActionPreference = 'Stop'
if (-not $dockerOk) { throw 'Docker chưa chạy. Mở Docker Desktop, đợi biểu tượng cá voi báo "Engine running" rồi chạy lại.' }

# ---------------------------------------------------------------- .env
if (-not (Test-Path $EnvFile)) {
    Step 'Tạo .env từ .env.docker.example (mật khẩu ngẫu nhiên)'
    $lines = Get-Content (Join-Path $Root '.env.docker.example') -Encoding UTF8 | ForEach-Object {
        if ($_ -match '__RANDOM__') { $_ -replace '__RANDOM__', (New-Secret) } else { $_ }
    }
    [IO.File]::WriteAllLines($EnvFile, [string[]]$lines, (New-Object Text.UTF8Encoding $false))
}
$envMap = Read-DotEnv $EnvFile
$port = if ($envMap['WEB_PORT']) { $envMap['WEB_PORT'] } else { '8080' }

$ComposeArgs = @('--project-directory', $Root, '-f', (Join-Path $Root 'compose.yaml'))
if ($Dev) { $ComposeArgs += @('-f', (Join-Path $Root 'compose.dev.yaml')) }
if ($Hw) { $ComposeArgs += @('--profile', 'hw') }

# ---------------------------------------------------------------- build + up
$images = docker image ls --format '{{.Repository}}:{{.Tag}}'
if ($Build -or -not ($images -contains 'docso-backend:0.5') -or -not ($images -contains 'docso-web:0.5')) {
    Step 'Build image (lần đầu ~10-20 phút: tải PaddlePaddle, npm ci)'
    Invoke-Compose build
}
Step 'Khởi động postgres, redis, migrate, api, worker, beat, web'
Invoke-Compose up -d --remove-orphans

Step 'Chờ API sẵn sàng (database + storage + redis)'
$ready = $false
for ($i = 0; $i -lt 180; $i++) {
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$port/api/health/ready" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep 2 }
}
if (-not $ready) {
    Invoke-Compose ps
    throw "API chưa sẵn sàng sau 6 phút. Xem log: docker compose logs migrate api"
}

# ---------------------------------------------------------------- tài khoản / dữ liệu
$seedArgs = @('python', 'scripts/seed_demo.py')
if ($Demo) { $seedArgs += '--allow-demo-in-production' } else { $seedArgs += '--admin-only' }
Step $(if ($Demo) { 'Nạp dữ liệu demo' } else { 'Tạo tài khoản admin (nếu chưa có)' })
Invoke-Compose run --rm --no-deps api @seedArgs

Step 'Chờ worker OCR nạp model (lần đầu tải model ~1-5 phút)'
$workerOk = $false
for ($i = 0; $i -lt 150; $i++) {
    $ErrorActionPreference = 'Continue'
    $log = (& docker compose @ComposeArgs logs --no-color worker 2>&1) -join "`n"
    $ErrorActionPreference = 'Stop'
    if ($log -match 'celery@\S+ ready') { $workerOk = $true; break }
    if ($log -match 'KHONG NAP DUOC OCR ENGINE') { break }
    Start-Sleep 2
}
if (-not $workerOk) {
    Write-Host '    Worker chưa sẵn sàng - xem: docker compose logs -f worker (job vẫn nằm trong hàng đợi Redis)' -ForegroundColor Yellow
}

Write-Host ''
Write-Host "Hệ thống đang chạy trong Docker: http://127.0.0.1:$port" -ForegroundColor Green
Write-Host "  Tài khoản admin: admin / $($envMap['DEMO_ADMIN_PASSWORD'])   (lưu trong .env; đổi sau lần đăng nhập đầu)"
if ($Demo) { Write-Host '  Tài khoản demo:  nhanvien | kiemduyet | ketoan / Demo@12345' }
if ($Dev) { Write-Host '  Dev: API http://127.0.0.1:8000/docs, Postgres 127.0.0.1:55433, Redis 127.0.0.1:6379' }
Write-Host '  Trạng thái:  docker compose ps        Log: docker compose logs -f api worker'
Write-Host '  Dừng:        .\docker-stop.cmd        (dữ liệu giữ trong volume Docker)'
if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$port" }
