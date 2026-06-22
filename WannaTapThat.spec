# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[('resources', 'resources')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WannaTapThat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources/icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WannaTapThat',
)
app = BUNDLE(
    coll,
    name='WannaTapThat.app',
    icon='resources/icon.icns',
    bundle_identifier='com.saltxd.wannatapthat',
    version='1.0.1',
    info_plist={
        'CFBundleName': 'WannaTapThat',
        'CFBundleDisplayName': 'WannaTapThat',
        'CFBundleShortVersionString': '1.0.1',
        'CFBundleVersion': '1.0.1',
        'LSMinimumSystemVersion': '15.0',
        'NSHighResolutionCapable': True,
        'LSApplicationCategoryType': 'public.app-category.social-networking',
    },
)
