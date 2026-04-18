REM =================================
REM PocketBell Simulator Ver 1.1 by JA1XPM 2026/04/16
REM =================================
@echo off
setlocal
set EDGE="%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if exist %EDGE% goto run
set EDGE="%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if exist %EDGE% goto run
start "" "index.html"
goto :eof
:run
%EDGE% --user-data-dir="%~dp0edge_profile" --app="file:///%~dp0index.html" --window-size=800,800
