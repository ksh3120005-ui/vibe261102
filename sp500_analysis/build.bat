@echo off
rem ============================================================
rem  Build script for S&P 500 Analytics (exe)
rem  Requires: pip install pyinstaller PyQt6 pandas numpy matplotlib openpyxl pillow
rem  Output  : dist\SP500Analytics.exe
rem            release\SP500Analytics_<date>.zip  (exe + README for distribution)
rem ============================================================
cd /d "%~dp0"

python -m PyInstaller --noconfirm --clean SP500Analytics.spec

if errorlevel 1 (
    echo.
    echo [FAILED] Build failed.
    exit /b 1
)

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set STAMP=%%d
if not exist release mkdir release
powershell -NoProfile -Command "Compress-Archive -Force -Path dist\SP500Analytics.exe, README.txt -DestinationPath release\SP500Analytics_%STAMP%.zip"

echo.
echo [DONE] dist\SP500Analytics.exe
echo [DONE] release\SP500Analytics_%STAMP%.zip
