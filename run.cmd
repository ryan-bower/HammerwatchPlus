@echo off
rem Double-click to set up, build, deploy the mods into your Steam install and start the game
rem (same as: python tools/run.py). See tools/run.py for the steps and flags.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" tools\run.py %*
) else (
  where uv >nul 2>nul
  if %errorlevel%==0 (uv run python tools\run.py %*) else (python tools\run.py %*)
)
if errorlevel 1 pause
