@echo off
title Stock Digitone MK1 OS 1.44
cd /d "%~dp0tools\digiemu"
echo Starting Stock Digitone MK1 OS 1.44...
".venv\Scripts\python.exe" -m emu.portable --worker panel "%~dp0tools\digiemu\portable\firmware\dn1-1.44-d4f200d0"
pause
