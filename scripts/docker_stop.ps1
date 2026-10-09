<#
.SYNOPSIS
    Dừng hệ thống chạy bằng Docker Compose.

    .\docker-stop.cmd           dừng container (giữ nguyên container + dữ liệu)
    .\docker-stop.cmd -Down     xóa container + mạng (dữ liệu trong volume vẫn giữ)
    .\docker-stop.cmd -Purge    xóa luôn volume: MẤT HẾT database, file đã upload, session, model OCR
#>
param(
    [switch]$Down,
    [switch]$Purge
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$Root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'docker_path.ps1')
if (-not (Find-Docker)) { throw 'Chưa cài Docker Desktop (GUIDE.md mục 6.1).' }

$ComposeArgs = @('--project-directory', $Root, '-f', (Join-Path $Root 'compose.yaml'), '--profile', 'hw')
$ErrorActionPreference = 'Continue'
if ($Purge) {
    Write-Host '==> Xóa container và TOÀN BỘ dữ liệu (volume)' -ForegroundColor Yellow
    & docker compose @ComposeArgs down --volumes --remove-orphans
} elseif ($Down) {
    Write-Host '==> Xóa container (giữ dữ liệu)' -ForegroundColor Cyan
    & docker compose @ComposeArgs down --remove-orphans
} else {
    Write-Host '==> Dừng container (giữ dữ liệu)' -ForegroundColor Cyan
    & docker compose @ComposeArgs stop
}
$code = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($code -ne 0) { throw "docker compose thất bại (mã $code)" }
Write-Host 'Đã dừng. Chạy lại: .\docker-start.cmd' -ForegroundColor Green
