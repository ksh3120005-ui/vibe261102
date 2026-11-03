# -*- mode: python ; coding: utf-8 -*-
# 빌드: python -m PyInstaller --noconfirm --clean Kospi200Crawler.spec  (또는 build.bat)


a = Analysis(
    ['kospi200_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('app.ico', '.')],
    hiddenimports=['openpyxl'],  # save_excel 안에서 늦게 import 하므로 명시
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 쓰지 않는 큰 모듈을 빼서 exe 크기를 줄인다
    excludes=['tkinter', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtQml',
              'PyQt6.QtQuick', 'PyQt6.QtMultimedia', 'PyQt6.QtPdf', 'PyQt6.QtSql',
              'numpy', 'pandas', 'matplotlib', 'PIL'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Kospi200Crawler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 검은 콘솔 창 없이 GUI만
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'],
    version='version_info.txt',
)
