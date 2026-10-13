"""补齐 10 个开发人员、50 个管理人员，并导出全部现有账号密码清单。"""

from collections import Counter
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sqlite3
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, text

from backend.app.config import get_settings
from backend.app.database import SessionLocal, sqlite_db_path
from backend.app.models import AdministratorProfile, Role, User, UserStatus
from backend.app.schemas import AccountCreate
from backend.app.security import hash_password, initial_student_password, verify_password
from backend.app.services import ADMIN_ROLES, audit, validate_account_quota


ROLE_LABELS = {
    Role.DEVELOPER: "开发人员",
    Role.SPORTS_TEACHER: "体育部老师",
    Role.SCORER: "计分员",
    Role.REFEREE: "裁判员",
    Role.REFEREE_SCORER: "裁判兼计分员",
    Role.STUDENT: "学生",
}
MANAGEMENT_ROLES = (
    Role.SPORTS_TEACHER, Role.SCORER, Role.REFEREE, Role.REFEREE_SCORER,
)


def account_definitions():
    settings = get_settings()
    definitions = []
    for index in range(1, 11):
        definitions.append(AccountCreate(
            username=settings.initial_developer_username if index == 1 else f"developer{index:02d}",
            display_name=f"开发人员{index:02d}",
            password=settings.initial_developer_password,
            role=Role.DEVELOPER,
            department="信息中心",
        ))
    for index in range(1, 51):
        role = MANAGEMENT_ROLES[(index - 1) % len(MANAGEMENT_ROLES)]
        definitions.append(AccountCreate(
            username=f"admin{index:04d}",
            display_name=f"{ROLE_LABELS[role]}{index:02d}",
            password=settings.demo_admin_password,
            role=role,
            department="体育部",
            employee_no=f"T{index:04d}",
        ))
    if len({item.username for item in definitions}) != len(definitions):
        raise ValueError("初始开发人员用户名与预置账号命名冲突")
    return definitions


def provision_account_pool():
    """保留现有账号，仅创建缺少的账号；全部写入在同一事务中完成。"""
    definitions = account_definitions()
    created = []
    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        actor = db.scalar(select(User).where(User.username == definitions[0].username))
        if actor is None or actor.role != Role.DEVELOPER or actor.status != UserStatus.ACTIVE:
            raise ValueError("需要已有且启用的初始开发人员账号")
        for definition in definitions:
            existing = db.scalar(select(User).where(User.username == definition.username))
            if existing is not None:
                if existing.role != definition.role:
                    raise ValueError(f"{definition.username} 的已有角色与预置角色冲突，已取消补齐")
                continue
            validate_account_quota(db, definition.role)
            if definition.employee_no and db.scalar(select(AdministratorProfile.id).where(
                AdministratorProfile.employee_no == definition.employee_no,
            )):
                raise ValueError(f"工号 {definition.employee_no} 已被占用，已取消补齐")
            user = User(
                username=definition.username,
                password_hash=hash_password(definition.password),
                role=definition.role,
                status=UserStatus.ACTIVE,
                display_name=definition.display_name,
                department=definition.department,
                first_login_change_required=False,
                created_by_id=actor.id,
                updated_by_id=actor.id,
            )
            db.add(user)
            db.flush()
            if definition.role in ADMIN_ROLES:
                db.add(AdministratorProfile(
                    user_id=user.id, employee_no=definition.employee_no,
                ))
            audit(db, actor, "CREATE_ACCOUNT", "user", user.id, after={
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
                "status": user.status,
                "department": user.department,
                "employee_no": definition.employee_no,
            })
            db.flush()
            created.append(user.username)
        db.commit()
    return created


def export_account_list(output_path):
    settings = get_settings()
    rows = []
    counts = Counter()
    unmatched = []
    with SessionLocal() as db:
        users = list(db.scalars(select(User).order_by(User.username)))
        for user in users:
            if user.role == Role.STUDENT:
                password = initial_student_password(user.username)
                entrance = "学生"
            elif user.role == Role.DEVELOPER:
                password = settings.initial_developer_password
                entrance = "开发人员"
            else:
                password = settings.demo_admin_password
                entrance = "管理人员"
            if not verify_password(password, user.password_hash):
                password = "已修改，无法直接读取"
                unmatched.append(user.username)
            counts[user.role] += 1
            rows.append((user, entrance, password))
    timestamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 全部账号密码清单", "",
        f"生成时间：{timestamp}（北京时间）", "",
        f"共 {len(rows)} 个账号：开发人员 {counts[Role.DEVELOPER]} 个、"
        f"管理人员 {sum(counts[role] for role in ADMIN_ROLES)} 个、学生 {counts[Role.STUDENT]} 个。", "",
        "密码已与数据库中的密码哈希逐一核对。", "",
        "新增裁判员、计分员及裁判兼计分员的项目权限，需在系统的“项目权限”中按实际职责分配。", "",
        "| 身份 | 姓名 | 登录入口 | 账号 | 密码 | 账号状态 |",
        "|---|---|---|---|---|---|",
    ]
    for user, entrance, password in sorted(rows, key=lambda row: (
        0 if row[0].role == Role.DEVELOPER else 2 if row[0].role == Role.STUDENT else 1,
        row[0].username,
    )):
        name = user.display_name.replace("|", "\\|").replace("\n", " ").replace("\r", " ")
        state = "启用" if user.status == UserStatus.ACTIVE else "冻结"
        lines.append(f"| {ROLE_LABELS[user.role]} | {name} | {entrance} | `{user.username}` | `{password}` | {state} |")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return dict(counts), unmatched


def reset_student_passwords():
    reset = []
    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        actor = db.scalar(select(User).where(User.username == get_settings().initial_developer_username))
        if actor is None or actor.role != Role.DEVELOPER or actor.status != UserStatus.ACTIVE:
            raise ValueError("需要已有且启用的初始开发人员账号")
        for student in db.scalars(select(User).where(User.role == Role.STUDENT)):
            password = initial_student_password(student.username)
            if verify_password(password, student.password_hash):
                continue
            student.password_hash = hash_password(password)
            student.first_login_change_required = False
            student.failed_login_count = 0
            student.locked_until = None
            student.token_version += 1
            student.updated_by_id = actor.id
            audit(db, actor, "RESET_PASSWORD", "user", student.id)
            reset.append(student.username)
        db.commit()
    return reset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset-student-passwords", action="store_true", help="将现有学生密码统一重置为 DF + 完整学号")
    args = parser.parse_args()
    expected_database = PROJECT_ROOT / "data" / "sports_meet.db"
    if sqlite_db_path is None or sqlite_db_path.resolve() != expected_database.resolve():
        raise ValueError("本脚本仅用于项目内的 data/sports_meet.db")
    if not expected_database.is_file():
        raise FileNotFoundError("请先初始化系统数据库")
    timestamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S_%f")
    backup = PROJECT_ROOT / "data" / "backups" / f"sports_meet_{timestamp}_before_fill_account_pool.db"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(expected_database.as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(backup) as target:
            source.backup(target)
    created = provision_account_pool()
    reset = reset_student_passwords() if args.reset_student_passwords else []
    output = PROJECT_ROOT / "data" / "exports" / "全部账号密码清单.md"
    counts, unmatched = export_account_list(output)
    print(json.dumps({
        "created_count": len(created), "student_passwords_reset": len(reset), "counts": counts,
        "backup": str(backup), "account_list": str(output),
        "password_not_known": unmatched,
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
