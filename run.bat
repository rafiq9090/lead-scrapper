@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing_python
".venv\Scripts\python.exe" --version >nul 2>&1
if errorlevel 1 goto missing_python
".venv\Scripts\python.exe" manage.py check
if errorlevel 1 goto failed

echo Starting DevLead OS at http://127.0.0.1:8000/
echo Sign in with your Django staff account.
start "" "http://127.0.0.1:8000/"
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000 --noreload
goto finished

:missing_python
echo Python environment is missing or broken. Follow the setup steps in README.md.
goto failed

:failed
echo Startup failed. Review the message above.
:finished
pause
endlocal
