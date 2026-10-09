@echo off
rem Dung demo (xem GUIDE.md). Trong PowerShell go: .\demo-stop.cmd
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\demo_stop.ps1" %*
