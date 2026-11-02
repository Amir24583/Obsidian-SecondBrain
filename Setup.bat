@echo off
rem Create or update your second-brain vault. Asks for the folders, then runs setup.py.
setlocal
set /p VAULT="Vault folder (new or existing Obsidian vault): "
set /p CONV="OneNote converter folder (Enter to skip): "
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
if "%CONV%"=="" (
  %PY% "%~dp0setup.py" --vault "%VAULT%"
) else (
  %PY% "%~dp0setup.py" --vault "%VAULT%" --converter "%CONV%"
)
pause
