@echo off
echo 🚀 Starting Codebase to Clipboard Web Application...
echo.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe run.py
) else (
    python run.py
)
pause