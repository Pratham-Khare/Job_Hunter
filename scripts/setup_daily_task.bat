@echo off
set "PROJECT=%~dp0.."
schtasks /Create /TN "Job Hunter Daily Alerts" /TR "\"%PROJECT%\scripts\run_daily.bat\"" /SC DAILY /ST 09:00 /F
if errorlevel 1 (
  echo Failed to create the task.
  exit /b 1
)
echo Daily Job Hunter task created for 09:00.
echo Edit this file if you want another time, then run it again.
