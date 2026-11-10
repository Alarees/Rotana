@echo off
rem Keeps the agent running: restarts it 30 seconds after any crash.
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
:loop
python agent.py run >> logs\console.log 2>&1
timeout /t 30 /nobreak >nul
goto loop
