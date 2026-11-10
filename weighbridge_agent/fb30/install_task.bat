@echo off
rem Run as Administrator. Starts the agent at every boot, even with nobody logged in.
rem Python must be installed "for all users" (e.g. C:\Program Files\Python38) and on PATH.
cd /d "%~dp0"
schtasks /Create /TN "RotanaWeighbridgeAgent" /TR "\"%~dp0run_agent.bat\"" /SC ONSTART /RU SYSTEM /RL HIGHEST /F
if errorlevel 1 goto :eof
schtasks /Run /TN "RotanaWeighbridgeAgent"
echo Installed. Check logs\agent.log
