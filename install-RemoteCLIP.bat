@echo off
cd /d "%~dp0"
title SIH26227 - RemoteCLIP setup
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements-remoteclip.txt
python -m scripts.download_remoteclip
python -m scripts.build_remoteclip_index
echo.
echo RemoteCLIP setup finished. Start the prototype with start-SIH26227.bat.
pause

