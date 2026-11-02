@echo off
rem Called by the OneNote converter after each sync ($AfterSync in its settings.ps1).
rem Files every new, changed, moved or deleted page into the wiki with Claude Code.
setlocal
set "BRAIN=%~dp0"
where py >nul 2>nul && (py -3 "%BRAIN%sb.py" auto & exit /b %ERRORLEVEL%)
python "%BRAIN%sb.py" auto
exit /b %ERRORLEVEL%
