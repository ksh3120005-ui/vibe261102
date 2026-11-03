@echo off
rem ============================================================
rem  Build script for Naver News Crawler (exe)
rem  Requires: pip install pyinstaller PyQt6 requests beautifulsoup4 openpyxl
rem  Output  : dist\NaverNewsCrawler.exe
rem ============================================================
cd /d "%~dp0"

python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name NaverNewsCrawler ^
    --icon app.ico ^
    --add-data "app.ico;." ^
    --exclude-module tkinter ^
    naver_news_gui.py

if errorlevel 1 (
    echo.
    echo [FAILED] Build failed.
    exit /b 1
)

echo.
echo [DONE] dist\NaverNewsCrawler.exe
