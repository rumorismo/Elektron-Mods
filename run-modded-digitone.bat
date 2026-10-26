@echo off
title Digitone MK1 MODDED OS 144S (Release 0.1)
cd /d "%~dp0tools\digiemu"
set "PYTHONPATH=%~dp0tools\digiemu"
echo Starting Digitone MK1 OS 144S (Release 0.1: Monomachine, Plaits MACRO, SOPHIE)...
echo Long-press T1, T2, T3, or T4 on the front panel to open the MOD MENU and select MACHINES!
".venv\Scripts\python.exe" -m emu.portable --worker panel "%~dp0tools\digiemu\portable\firmware\dn1-144s-02af17fd"
pause
