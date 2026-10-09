@echo off
rem Chay he thong bang Docker (xem GUIDE.md). Trong PowerShell go: .\docker-start.cmd [-Demo] [-Hw] [-Dev] [-Build]
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\docker_start.ps1" %*
if errorlevel 1 pause
