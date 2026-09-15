@echo off
cd /d %~dp0

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0updater.ps1"

python\python.exe setup\main.py
