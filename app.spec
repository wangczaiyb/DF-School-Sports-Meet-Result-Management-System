# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# 收集可能需要的数据文件与子模块
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespans',
    'uvicorn.lifespans.on',
    'uvicorn.lifespans.off',
    'fastapi',
    'starlette',
    'pydantic',
    'pydantic_settings',
    'sqlalchemy',
    'sqlalchemy.sql.default_comparator',
    'openpyxl',
    'passlib',
    'passlib.handlers.bcrypt',
    'bcrypt',
    'jwt',
    'jose',
    'multipart',
    'python_multipart',
    'sqlite3',
    'alembic',
]
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('backend')
hiddenimports += collect_submodules('alembic')
hiddenimports += collect_submodules('sqlalchemy')

# 收集前端构建产物与数据库迁移脚本
datas = []
datas += collect_data_files('alembic')
frontend_dist = os.path.abspath(os.path.join('frontend', 'dist'))
if os.path.exists(frontend_dist):
    datas.append((frontend_dist, 'frontend_dist'))
alembic_ini = os.path.abspath(os.path.join('backend', 'alembic.ini'))
alembic_scripts = os.path.abspath(os.path.join('backend', 'alembic'))
if os.path.exists(alembic_ini):
    datas.append((alembic_ini, 'backend'))
if os.path.exists(alembic_scripts):
    datas.append((alembic_scripts, os.path.join('backend', 'alembic')))
template_file = os.path.abspath(os.path.join('outputs', 'sports-meet', '学生参赛名单导入模板.xlsx'))
if os.path.exists(template_file):
    datas.append((template_file, os.path.join('outputs', 'sports-meet')))

a = Analysis(
    ['run_app.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'scipy', 'IPython',
        'torch', 'torchvision', 'cv2', 'scrapy', 'streamlit',
        'django', 'tornado', 'jupyter_client', 'ipykernel',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='校园运动会成绩管理系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='校园运动会成绩管理系统_绿色免安装版',
)
