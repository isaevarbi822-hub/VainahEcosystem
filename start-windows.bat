@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
    echo Python 3.12+ is required. Install Python and reopen this file.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto :fail
)
".venv\Scripts\python.exe" -m pip install -r requirements-desktop.txt
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" apps\desktop\run.py %*
if errorlevel 1 goto :fail
exit /b 0
:fail
echo Vainah could not start. Check the error above.
pause
exit /b 1
