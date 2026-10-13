"""用户指定的七学院清理。默认预览，--apply先备份再执行。"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from backend.app.college_policy import DEFAULT_COLLEGES
from backend.app.config import get_settings


from backend.app.college_maintenance import placeholders, targets, retain_colleges


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--no-backup', action='store_true', help='用户明确要求不备份时使用')
    args = parser.parse_args()
    url = get_settings().database_url
    if not url.startswith('sqlite:///'):
        raise SystemExit('仅支持项目本地SQLite数据库')
    database = Path(url.removeprefix('sqlite:///')).resolve()
    expected = (PROJECT_ROOT / 'data' / 'sports_meet.db').resolve()
    if database != expected or not database.is_file():
        raise SystemExit('数据库必须为已核对的项目data/sports_meet.db')
    if not args.apply:
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            print(json.dumps({'removed_teams': targets(db), 'retained_colleges': list(DEFAULT_COLLEGES)}, ensure_ascii=False))
        return
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    backup_dir = (PROJECT_ROOT / 'data' / 'backups').resolve()
    if not backup_dir.is_relative_to(PROJECT_ROOT.resolve()):
        raise SystemExit('备份路径必须位于项目目录内')
    if not args.no_backup:
        backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f'sports_meet_{stamp}_before_seven_colleges.db'
    with sqlite3.connect(database, timeout=30) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        if not args.no_backup:
            with sqlite3.connect(backup_path) as backup:
                db.backup(backup)
                if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('备份完整性校验失败，未修改正式数据')
        db.execute('BEGIN IMMEDIATE')
        try:
            report = retain_colleges(db, backed_up=not args.no_backup)
            db.commit()
        except Exception:
            db.rollback()
            raise
    report['backup'] = None if args.no_backup else str(backup_path)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
