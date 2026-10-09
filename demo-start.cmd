@echo off
rem Khoi dong demo (xem GUIDE.md). Trong PowerShell go: .\demo-start.cmd  [-Reset] [-Mvp] [-Port 8080]
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\demo_start.ps1" %*
if errorlevel 1 pause
