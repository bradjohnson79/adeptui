@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0AdeptUI-Beta-Health.ps1" %*
