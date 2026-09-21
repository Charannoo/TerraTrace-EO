@echo off
cd /d "%~dp0"
title SIH26227 - TerraTrace EO
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" server.py
) else (
  python server.py
)
if errorlevel 1 (
  echo.
  echo Unable to start. Install Python 3.11+ with NumPy and Pillow, then try again.
  pause
)
