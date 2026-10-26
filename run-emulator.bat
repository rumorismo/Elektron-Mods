@echo off
title Digitone Emulator Launcher
cd /d "%~dp0tools\digiemu"
echo Starting digiemu launcher...
".venv\Scripts\python.exe" -m emu.portable
pause
