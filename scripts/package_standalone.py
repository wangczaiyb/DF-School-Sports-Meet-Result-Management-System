# -*- coding: utf-8 -*-
"""
校园运动会赛事成绩管理系统 - 独立免安装绿色便携版打包脚本
"""
import os
import sys
import shutil
import sqlite3
import zipfile
import subprocess
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"
TARGET_DIR_NAME = "校园运动会成绩管理系统_绿色免安装版"
PACKAGE_DIR = DIST_DIR / TARGET_DIR_NAME
ZIP_FILE = DIST_DIR / f"{TARGET_DIR_NAME}.zip"
PACKAGE_DB = PROJECT_ROOT / "build" / "package_data" / "sports_meet.db"


BAT_CONTENT = """@echo off
chcp 65001 >nul
title 校园运动会赛事成绩管理系统 - 启动器
cd /d "%~dp0"
echo ======================================================================
echo   【校园运动会赛事成绩管理系统】正在启动...
echo   说明：本系统为绿色免安装便携版，内置完整运行环境与初始数据库。
echo ======================================================================
echo.
"%~dp0校园运动会成绩管理系统.exe"
pause
"""

README_CONTENT = """================================================================================
           校园运动会赛事成绩管理系统（绿色免安装独立版）使用说明
================================================================================

一、 系统简介
本软件为“校园运动会赛事成绩管理系统”的纯绿色、免安装独立运行版本。
系统已将 Python 运行环境、后端服务、前端单页应用（Vue3+ElementPlus）以及
SQLite 数据库引擎全部整合打包。使用本系统的电脑无需安装 Python、Node.js、
MySQL 等任何运行环境或依赖，解压即用。

--------------------------------------------------------------------------------
二、 快速启动使用方法
1. 解压压缩包：
   将【校园运动会成绩管理系统_绿色免安装版.zip】完整解压到电脑任意文件夹（建议路径全为英文或普通中文，避免过深路径）。
2. 启动系统：
   直接双击运行文件夹内的【双击启动系统.bat】（推荐）或【校园运动会成绩管理系统.exe】。
3. 自动进入主页：
   系统启动后会在黑色控制台窗口中显示运行状态，并在 1~2 秒内自动拉起系统默认浏览器
   打开系统主页（默认访问地址：http://127.0.0.1:8000）。
4. 退出系统：
   直接关闭黑色的控制台窗口，即可安全退出并停止服务。

--------------------------------------------------------------------------------
三、 预置默认账号信息（开箱即用）
系统已预置开箱即用的赛事配置、演示数据及各角色账号：

1. 【体育部老师 / 赛事管理员】
   账号：admin0001
   密码：Admin123456!
   权限：拥有赛事全流程管理权限，包括赛程编排、检录、成绩初录、复核、成绩终审发布、
         成绩册导出、学院团体计分与报表统计等。

2. 【计分员 / 成绩录入员】
   账号：admin0002
   密码：Admin123456!
   权限：负责现场赛道成绩、试跳试投、跳绳赛制对抗等成绩录入与提交复核。

3. 【裁判员】
   账号：admin0003
   密码：Admin123456!
   权限：负责核对现场成绩草表、争议仲裁、成绩签字确认与审核流转。

4. 【双重职责权限（裁判+计分）】
   账号：admin0004
   密码：Admin123456!

5. 【系统开发员 / 超级管理员】
   账号：developer01
   密码：Dev123456!
   权限：系统底层配置、全局设置修改、计分模型规则管理、数据管理等。

6. 【学生运动员 / 观众查询】
   学生登录账号：学号（如 2026001001、2026001002 等）
   初始密码规则：DF + 学号后6位（例如学号 2026001001 的密码为 DF001001）
   权限：免密或初始密码直接登录、个人赛程与道次查询、个人成绩单、学院总积分与荣誉榜查看。

--------------------------------------------------------------------------------
四、 核心功能与特色
1. 完整赛事管理：
   - 支持田径、径赛、田赛以及篮球、排球、乒乓球、跳绳专用赛制工作台。
   - 检录、道次编排、初赛/晋级赛/决赛轮次自动生成。
   - 跳绳赛制包含“前单跳”、集体单摇跳和“8”字环绕跳三个规则化项目。
   - 所有管理角色均可看到跳绳赛制入口；体育部老师/开发人员负责初始化和阵容，获授权计分员负责成绩录入。
2. 成绩闭环流转与终审快照：
   - 草稿保存 -> 提交初审 -> 裁判审核 -> 体育部终审发布 -> 一键导出标准 Excel 成绩单。
3. 模板下载与名单批量导入：
   - 体育教师可在“名单录入 -> 学生资料库”中一键下载 Excel 模板并批量导入学生资料。
   - 系统内置脱敏导出与 A4 打印优化。

--------------------------------------------------------------------------------
五、 局域网 / 手机协同访问（赛场多设备使用）
如果您在运动会赛场上需要多名老师、裁判使用手机、iPad 或其他笔记本电脑协同检录或录入成绩：
1. 确保所有设备连接到同一个 Wi-Fi 热点或校园局域网。
2. 在运行本系统的电脑启动控制台中，会显示形如：
   * 局域网协同网址: http://192.168.x.x:8000
3. 手机、平板在浏览器中直接输入该网址，即可直接登录系统进行移动端协同录入与查询！

--------------------------------------------------------------------------------
六、 数据保存与备份迁移
1. 数据存储路径：
   所有赛事、账号与成绩数据均实时保存在程序目录下的【data\\sports_meet.db】中。
2. 备份与迁移：
   直接将【data】文件夹或整个解压目录复制到其他电脑或U盘，所有历史数据无缝继承，无任何外部数据库依赖。
"""


def build_frontend():
    print("[1/6] 检查并构建最新前端产物...")
    frontend_dir = PROJECT_ROOT / "frontend"
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    cmd = [npm_cmd, "--prefix", str(frontend_dir), "run", "build"]
    print(f"      执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise RuntimeError(f"前端构建失败，退出码: {result.returncode}")
    print("      [OK] 前端构建成功！产物位于: frontend/dist")


def prepare_database():
    print("[2/6] 创建干净的开箱即用数据库...")
    PACKAGE_DB.parent.mkdir(parents=True, exist_ok=True)
    for candidate in [PACKAGE_DB, Path(f"{PACKAGE_DB}-wal"), Path(f"{PACKAGE_DB}-shm")]:
        candidate.unlink(missing_ok=True)

    # 分发包始终使用全新的演示数据库，避免把开发机上的正式数据、测试记录
    # 或审计日志误打进发给他人的压缩包。这里只影响构建目录，不修改项目数据库。
    previous_database_url = os.environ.get("DATABASE_URL")
    previous_auto_seed = os.environ.get("AUTO_SEED")
    os.environ["DATABASE_URL"] = f"sqlite:///{PACKAGE_DB.as_posix()}"
    os.environ["AUTO_SEED"] = "true"

    sys.path.insert(0, str(PROJECT_ROOT))
    from backend.app.database import upgrade_database_to_head, ensure_sqlite_team_registration_schema, Base, engine, SessionLocal
    from backend.app.seed import seed_database
    from backend.app.services import sync_event_rounds

    upgrade_database_to_head()
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_team_registration_schema()

    with SessionLocal() as db:
        seed_database(db)
        sync_event_rounds(db)
        db.commit()

    engine.dispose()

    if PACKAGE_DB.exists():
        print("      执行 SQLite WAL checkpoint 和 VACUUM 整理...")
        with sqlite3.connect(str(PACKAGE_DB)) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
        print("      [OK] 数据库已整理为干净独立单文件！")

    if previous_database_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_database_url
    if previous_auto_seed is None:
        os.environ.pop("AUTO_SEED", None)
    else:
        os.environ["AUTO_SEED"] = previous_auto_seed


def run_pyinstaller():
    print("[3/6] 执行 PyInstaller 编译打包...")
    spec_file = PROJECT_ROOT / "app.spec"
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "-y", str(spec_file)]
    print(f"      执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        raise RuntimeError(f"PyInstaller 打包失败，退出码: {result.returncode}")
    print("      [OK] 二进制编译完成！")


def populate_package_assets():
    print("[4/6] 组装分发目录资源与配置...")
    if not PACKAGE_DIR.exists():
        raise RuntimeError(f"未找到打包输出目录: {PACKAGE_DIR}")

    # 1. 准备 data 目录与干净数据库
    target_data = PACKAGE_DIR / "data"
    target_data.mkdir(exist_ok=True)
    (target_data / "exports").mkdir(exist_ok=True)
    (target_data / "backups").mkdir(exist_ok=True)

    src_db = PACKAGE_DB
    dst_db = target_data / "sports_meet.db"
    shutil.copy2(str(src_db), str(dst_db))

    # 清理可能随复制带入的 shm/wal/log 临时文件
    for temp_f in target_data.glob("*.db-*"):
        try:
            temp_f.unlink()
        except Exception:
            pass
    for log_f in target_data.glob("*.log"):
        try:
            log_f.unlink()
        except Exception:
            pass
    for pid_f in target_data.glob("*.pid"):
        try:
            pid_f.unlink()
        except Exception:
            pass

    # 2. 拷贝 outputs 模板目录
    src_outputs = PROJECT_ROOT / "outputs" / "sports-meet"
    dst_outputs = PACKAGE_DIR / "outputs" / "sports-meet"
    dst_outputs.mkdir(parents=True, exist_ok=True)
    if src_outputs.exists():
        for f in src_outputs.glob("*"):
            if f.is_file():
                shutil.copy2(str(f), str(dst_outputs / f.name))

    # 3. 写入启动脚本与使用说明
    bat_path = PACKAGE_DIR / "双击启动系统.bat"
    bat_path.write_text(BAT_CONTENT, encoding="utf-8")

    readme_path = PACKAGE_DIR / "使用说明.txt"
    readme_path.write_text(README_CONTENT, encoding="utf-8")

    build_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    version_info = f"""校园运动会赛事成绩管理系统 - 最新版构建信息
构建时间：{build_time}

本分发包已确认包含：
1. 篮球赛制工作台
2. 排球赛制工作台
3. 乒乓球赛制工作台
4. 跳绳赛制工作台（前单跳、集体单摇跳、8字环绕跳）
5. 分届次名单与学院代表队
6. 分轮次检录、赛程、晋级与成绩管理
7. 成绩审核、终审发布及不可变发布快照
8. 公开成绩中心与 Excel 导入导出

跳绳赛制入口对 developer01、admin0001、admin0002、admin0003、admin0004 全部可见；
其中初始化和阵容配置仅限 developer01、admin0001，成绩录入按项目权限执行。
"""
    (PACKAGE_DIR / "版本信息_确认最新版.txt").write_text(version_info, encoding="utf-8")

    print(f"      [OK] 目录资源填充完成: {PACKAGE_DIR}")


def create_zip_archive():
    print("[5/6] 压缩打包为便于分发的 ZIP 归档...")
    if ZIP_FILE.exists():
        try:
            ZIP_FILE.unlink()
        except Exception as e:
            print(f"      注意：删除旧 zip 失败 ({e})，尝试覆盖写入...")

    total_files = 0
    with zipfile.ZipFile(str(ZIP_FILE), "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(str(PACKAGE_DIR)):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(PACKAGE_DIR.parent)
                zf.write(file_path, arcname=str(rel_path))
                total_files += 1

    size_mb = ZIP_FILE.stat().st_size / (1024 * 1024)
    print(f"      [OK] ZIP 压缩包生成完成！")
    print(f"        文件路径: {ZIP_FILE}")
    print(f"        压缩包大小: {size_mb:.2f} MB")
    print(f"        包含文件数: {total_files} 个")


def print_summary():
    print("\n" + "=" * 72)
    print("  [SUCCESS] 【校园运动会赛事成绩管理系统】最新免安装便携版打包完成！")
    print("=" * 72)
    print(f"  * 绿色便携压缩包: {ZIP_FILE}")
    print(f"  * 解压运行文件夹: {PACKAGE_DIR}")
    print("  * 使用方式: 将上面的【.zip 压缩包】直接发给别人，解压后双击【双击启动系统.bat】即可！")
    print("  * 提示: 对方电脑无需安装 Python、Node.js、MySQL 等任何环境，开箱即用！")
    print("=" * 72 + "\n")


def main():
    try:
        build_frontend()
        prepare_database()
        run_pyinstaller()
        populate_package_assets()
        create_zip_archive()
        print_summary()
    except Exception as e:
        print(f"\n[ERROR] 打包过程遇到异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
