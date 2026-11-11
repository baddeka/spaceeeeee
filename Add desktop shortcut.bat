@echo off
rem Puts a "Rens Office" shortcut on the desktop. Run once; run again if this folder moves.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop = [Environment]::GetFolderPath('Desktop'); $link = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Rens Office.lnk')); $link.TargetPath = (Join-Path (Get-Location) 'Rens Office.bat'); $link.WorkingDirectory = (Get-Location).Path; $link.Description = 'Rens Office'; $link.Save(); Write-Host ('Shortcut created: ' + (Join-Path $desktop 'Rens Office.lnk'))"
if errorlevel 1 echo Could not create the shortcut.
pause
