<#
.SYNOPSIS
    Dừng demo ProjectB: giao diện, API, worker, beat và PostgreSQL demo. Dữ liệu trong .demo\ được giữ lại.
    Chạy: bấm đúp demo-stop.cmd, hoặc trong PowerShell:  .\demo-stop.cmd
#>
param([switch]$Quiet)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$Root    = Split-Path -Parent $PSScriptRoot
$Demo    = Join-Path $Root '.demo'
$PgData  = Join-Path $Demo 'pgdata'
$PidFile = Join-Path $Demo 'pids.txt'

function Say($msg) { if (-not $Quiet) { Write-Host $msg } }

if (Test-Path $PidFile) {
    foreach ($procId in Get-Content $PidFile) {
        if ($procId -and (Get-Process -Id $procId -ErrorAction SilentlyContinue)) {
            & taskkill.exe /PID $procId /T /F *> $null
        }
    }
    Remove-Item $PidFile -Force
}
# Dự phòng: tiến trình demo của project này còn sót (khi file PID bị mất)
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -and $_.CommandLine -like "*$Root*" -and
                   ($_.CommandLine -match 'celery_app:celery_app' -or $_.CommandLine -match 'vite\.js.+preview') } |
    ForEach-Object { & taskkill.exe /PID $_.ProcessId /T /F *> $null }
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId = $($_.OwningProcess)"
    if ($p.CommandLine -match 'uvicorn app\.main:app') { & taskkill.exe /PID $_.OwningProcess /T /F *> $null }
}
Say 'Đã dừng giao diện, API, worker và beat.'

$pgCtl = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\pg_ctl.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pgCtl -and (Test-Path (Join-Path $PgData 'PG_VERSION'))) {
    & $pgCtl.FullName -D $PgData status *> $null
    if ($LASTEXITCODE -eq 0) {
        & $pgCtl.FullName -D $PgData stop -m fast *> $null
        Say 'Đã dừng PostgreSQL demo.'
    }
}
Say 'Dữ liệu demo vẫn giữ trong .demo\ (chạy .\demo-start.cmd -Reset để làm mới).'
