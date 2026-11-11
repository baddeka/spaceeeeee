@echo off
rem Rens Office: one click starts the newest version. Double-click this file, or the desktop shortcut
rem that "Add desktop shortcut.bat" makes for it.
chcp 65001 >nul
title Rens Office
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
  echo Git was not found, so the office starts as it is, without updating.
) else (
  echo Getting the newest version...
  git pull --ff-only
  if errorlevel 1 echo Could not update ^(no internet, or local changes^). Starting the version that is here.
)

set "PY=python"
where py >nul 2>nul && set "PY=py"
if not exist ".venv\Scripts\python.exe" (
  echo First start: setting up, this takes a minute...
  %PY% -m venv .venv
  if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -e .
if errorlevel 1 goto :failed

where claude >nul 2>nul
if errorlevel 1 echo Claude Code was not found. Install it and sign in with: claude

echo Starting the office. Close this window to stop it.
".venv\Scripts\python.exe" -m office.server --lang ru --open %*
if errorlevel 1 pause
exit /b

:failed
echo.
echo The office could not be set up. Check that Python 3.11 or newer is installed.
pause
exit /b 1
