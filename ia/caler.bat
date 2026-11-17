@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
if "%~1"=="" (
  echo.
  echo  Glisse sur ce fichier une video de la CAMERA Veo ^(1-2 min, le jeu va d'un but a l'autre^)
  echo  pour caler le terrain par clics.
  echo.
  pause
  exit /b
)
echo.
set /p NOM= Nom du terrain (ex. stade_club) :
set /p LONG= Longueur du terrain en metres (ligne de but a ligne de but) :
set /p LARG= Largeur du terrain en metres (touche a touche) :
set /p SURF= Surface de reparation : profondeur et largeur en metres (ex. 16.5 40.32) :
set /p BUT= Surface de but : profondeur et largeur en metres (ex. 5.5 18.32) :
%PY% caler.py "%~1" --nom "%NOM%" --longueur %LONG% --largeur %LARG% --surface %SURF% --but %BUT%
if errorlevel 1 (
  echo.
  echo  Probleme. Python est-il installe ? Sinon : double-clic sur installer.bat
)
echo.
pause
