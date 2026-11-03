@echo off
rem ============================================================
rem  Build script for KOSPI200 Crawler (exe)
rem  Requires: pip install pyinstaller PyQt6 requests beautifulsoup4 openpyxl
rem  Output  : dist\Kospi200Crawler.exe
rem            release\Kospi200Crawler_<date>.zip  (exe + README for distribution)
rem ============================================================
cd /d "%~dp0"

python -m PyInstaller --noconfirm --clean Kospi200Crawler.spec

if errorlevel 1 (
    echo.
    echo [FAILED] Build failed.
    exit /b 1
)

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set STAMP=%%d
if not exist release mkdir release
powershell -NoProfile -Command "Compress-Archive -Force -Path dist\Kospi200Crawler.exe, README.txt -DestinationPath release\Kospi200Crawler_%STAMP%.zip"

echo.
echo [DONE] dist\Kospi200Crawler.exe
echo [DONE] release\Kospi200Crawler_%STAMP%.zip
