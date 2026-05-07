REM =================================
REM PocketBell Simulator Ver 1.1.1 by JA1XPM 2026/05/07
REM =================================
@echo off
setlocal
REM Start TX/RX bridge + GUI
REM Device numbers:
REM   py dtmftest_pager.py devices

set OUTDEV=0
set INDEV=0
set COM=COM7
REM set COM=NONE  REM VOX(Signalinkを使う場合)

if /I "%COM%"=="NONE" (
start "DTMF Bridge" cmd /k py pager_tx_bridge.py --out %OUTDEV% --in %INDEV%
) else (
start "DTMF Bridge" cmd /k py pager_tx_bridge.py --out %OUTDEV% --in %INDEV% --com %COM%
)
call launch_edge_app.bat
