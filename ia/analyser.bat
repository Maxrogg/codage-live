@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
if "%~1"=="" (
  echo.
  echo  Glisse la video du match sur ce fichier pour l'analyser.
  echo  ^(enregistrement d'ecran du lecteur Veo, radar 2D affiche en haut a droite^)
  echo.
  pause
  exit /b
)
%PY% analyser.py "%~1" --ouvrir
if errorlevel 1 (
  echo.
  echo  Probleme. Python est-il installe ? Sinon : double-clic sur installer.bat
)
echo.
pause
