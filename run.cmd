@echo off
rem Build/deploy, create a fresh default profile with all mods enabled, and start through Steam
rem (same as: python tools/run.py). See tools/run.py for the steps and flags.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" tools\run.py %*
) else (
  where uv >nul 2>nul
  if %errorlevel%==0 (uv run python tools\run.py %*) else (python tools\run.py %*)
)
if errorlevel 1 pause
