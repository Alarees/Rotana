@echo off
schtasks /End /TN "RotanaWeighbridgeAgent"
schtasks /Delete /TN "RotanaWeighbridgeAgent" /F
taskkill /F /IM python.exe /FI "WINDOWTITLE eq RotanaWeighbridgeAgent*" >nul 2>&1
echo Removed. If python.exe is still running the agent, stop it from Task Manager.
