@echo off
chcp 65001 >nul
title AutoDiag Video Studio - Compilar EXE
echo ============================================================
echo   AutoDiag Video Studio - Generando ejecutable portable
echo ============================================================
cd /d "%~dp0"
where python >nul 2>nul || (echo [X] Instala Python 3.11+ desde python.org ^(marca "Add to PATH"^) & pause & exit /b 1)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || (echo [X] Error instalando dependencias & pause & exit /b 1)
if not exist cloud (
  if exist ..\cloud (xcopy /E /I /Y ..\cloud cloud >nul) else (echo [X] Falta la carpeta cloud & pause & exit /b 1)
)
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name AutoDiagStudio ^
  --icon icon.ico ^
  --add-data "cloud;cloud" ^
  --add-data "icon.ico;." ^
  --collect-data customtkinter ^
  --collect-all edge_tts ^
  --collect-data certifi ^
  autodiag_studio_win.py || (echo [X] PyInstaller fallo & pause & exit /b 1)
echo.
echo [OK] Listo: dist\AutoDiagStudio.exe
echo      Copialo a cualquier PC con Windows 10/11. Crea config_profiles.json y Videos_Listos a su lado.
pause
