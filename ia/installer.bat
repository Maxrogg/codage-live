@echo off
chcp 65001 >nul
set PY=python
where python >nul 2>nul || set PY=py
echo Installation des outils d'analyse (une seule fois)...
%PY% -m pip install --upgrade opencv-python numpy matplotlib
if errorlevel 1 (
  echo.
  echo  Python introuvable. Installe-le depuis python.org en cochant "Add Python to PATH", puis relance.
) else (
  echo.
  echo  Termine. Glisse maintenant une video sur analyser.bat
)
echo.
pause
