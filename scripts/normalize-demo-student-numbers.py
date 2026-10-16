"""演示学号统一为8位。默认仅预览，--apply 备份后执行；不可用于真实学号转换。"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, text

from backend.app.database import SessionLocal, sqlite_db_path
from backend.app.models import Role, User
from backend.app.services import audit
from backend.app.student_maintenance import apply_demo_student_number_plan, demo_student_number_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="仅在确认全为演示数据后使用")
    parser.add_argument("--grade", help="指定演示数据的两位年级，例如26表示26级；省略时保留已有8位学号")
    args = parser.parse_args()
    if sqlite_db_path is None:
        raise SystemExit("此本地维护脚本仅支持SQLite")
    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE" if args.apply else "BEGIN"))
        plan = demo_student_number_plan(db, args.grade)
        if not args.apply or not plan:
            print(json.dumps({"applied": False, "plan": plan}, ensure_ascii=False, indent=2))
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = sqlite_db_path.parent / "backups" / f"sports_meet_{timestamp}_before_student_numbers.db"
        backup.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(sqlite_db_path.resolve().as_uri() + "?mode=ro", uri=True) as source, sqlite3.connect(backup) as destination:
            source.backup(destination)
        report = apply_demo_student_number_plan(db, plan, args.grade)
        actor = db.scalar(select(User).where(User.role == Role.DEVELOPER).order_by(User.id))
        if actor is None:
            raise ValueError("缺少维护审计所需的开发人员账号")
        audit(db, actor, "NORMALIZE_DEMO_STUDENT_NUMBERS", "student_roster", "all",
              before={"mapping": plan}, after=report,
              reason="用户确认本地学生均为演示数据，统一为8位学号，前两位表示年级"
                     + (f"；本批演示年级为{args.grade}级" if args.grade else ""))
        if db.execute(text("PRAGMA foreign_key_check")).fetchall():
            raise ValueError("关联完整性校验失败，已取消转换")
        mapping_path = sqlite_db_path.parent / "exports" / f"student_number_mapping_{timestamp}.json"
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        mapping_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        db.commit()
        print(json.dumps({"applied": True, **report, "backup": str(backup), "mapping": str(mapping_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
