@echo off
cd /d "%~dp0"
where pythonw >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw "%~dp0run.pyw"
) else (
    start "" python "%~dp0run.pyw"
)
