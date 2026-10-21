@echo off
title Argentum Splat - Install
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
set "install_exit=%ERRORLEVEL%"
if not "%install_exit%"=="0" echo Setup needs attention. Read the message and log path above; rerun Install.cmd to retry.
pause
exit /b %install_exit%
