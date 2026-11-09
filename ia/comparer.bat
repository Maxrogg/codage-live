@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
if "%~2"=="" (
  echo.
  echo  Selectionne les DEUX fichiers ensemble et glisse-les sur ce fichier :
  echo   - l'export de l'onglet Video de l'appli ^(actions_video_....json^)
  echo   - le match_ia.json du dossier resultats_...
  echo.
  pause
  exit /b
)
%PY% comparer.py "%~1" "%~2"
echo.
pause
