@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto :fail
)
".venv\Scripts\python.exe" -m pip install -r requirements-desktop.txt "pyinstaller>=6.0,<8"
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onefile --name Vainah-Ecosystem --add-data "apps\web;apps\web" --collect-submodules services --collect-submodules uvicorn --collect-all webview apps\desktop\run.py
if errorlevel 1 goto :fail
echo EXE created: dist\Vainah-Ecosystem.exe
pause
exit /b 0
:fail
echo Build failed. Check errors above.
pause
exit /b 1
