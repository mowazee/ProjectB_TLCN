@echo off
rem Dung he thong Docker (xem GUIDE.md). Trong PowerShell go: .\docker-stop.cmd [-Down] [-Purge]
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\docker_stop.ps1" %*
