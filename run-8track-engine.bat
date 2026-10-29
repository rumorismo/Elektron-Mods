@echo off
title Digitone MK1 8Track-Engine2 (tag 1490)
cd /d "%~dp0tools\digiemu"
set "PYTHONPATH=%~dp0tools\digiemu"
".venv\Scripts\python.exe" -m emu.portable --worker panel "%~dp0tools\digiemu\portable\firmware\dn1-1490-38aa5ba5"
pause
