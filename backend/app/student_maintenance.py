"""仅用于用户确认可重新编号的演示数据，调用方负责备份和事务。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Role, StudentRoster, User
from .security import hash_password, initial_student_password, verify_password
from .student_policy import is_valid_student_number


def demo_student_number_plan(db: Session, grade: str | None = None) -> list[dict]:
    if grade is not None and (len(grade) != 2 or not grade.isascii() or not grade.isdigit()):
        raise ValueError("年级必须为两位数字，例如24表示24级")
    students = list(db.scalars(select(StudentRoster).order_by(StudentRoster.id)))
    users = list(db.scalars(select(User).order_by(User.id)))
    occupied = {row.student_no for row in students} | {user.username for user in users}
    accounts = {user.id: user for user in users}
    linked_users = {row.user_id for row in students if row.user_id is not None}
    plan = []
    for row in [*students, *(user for user in users if user.role == Role.STUDENT and user.id not in linked_users)]:
        old = row.student_no if isinstance(row, StudentRoster) else row.username
        if is_valid_student_number(old) and (grade is None or old.startswith(grade)):
            continue
        user = accounts.get(row.user_id) if isinstance(row, StudentRoster) else row
        if isinstance(row, StudentRoster) and row.user_id is not None and (user is None or user.role != Role.STUDENT or user.username != old):
            raise ValueError(f"学生 {row.id} 的关联账号不一致，请先核查")
        if old.isascii() and old.isdigit() and old.startswith("20") and 8 <= len(old) <= 10:
            inferred_grade, suffix = old[2:4], old[4:]
        elif old.isascii() and old.isdigit() and len(old) >= 2:
            inferred_grade, suffix = old[:2], old[2:]
        elif grade is not None:
            inferred_grade, suffix = grade, ""
        else:
            raise ValueError("无法从旧演示编号识别年级，请使用 --grade 指定两位年级")
        target_grade = grade or inferred_grade
        candidate = target_grade + suffix[-6:].zfill(6)
        if candidate in occupied:
            candidate = next((f"{target_grade}{number:06d}" for number in range(1, 1000000)
                              if f"{target_grade}{number:06d}" not in occupied), None)
        if candidate is None:
            raise ValueError("没有可用的8位演示学号")
        occupied.add(candidate)
        plan.append({"student_id": row.id if isinstance(row, StudentRoster) else None,
                     "user_id": user.id if user else None, "old_student_no": old, "student_no": candidate})
    return plan


def apply_demo_student_number_plan(db: Session, plan: list[dict], grade: str | None = None) -> dict:
    if plan != demo_student_number_plan(db, grade):
        raise ValueError("数据已变化，请重新预览演示学号对应表")
    default_passwords_updated = 0
    for item in plan:
        if item["student_id"] is not None:
            db.get(StudentRoster, item["student_id"]).student_no = item["student_no"]
        if item["user_id"] is not None:
            user = db.get(User, item["user_id"])
            if verify_password(initial_student_password(user.username), user.password_hash):
                user.password_hash = hash_password(initial_student_password(item["student_no"]))
                default_passwords_updated += 1
            user.username = item["student_no"]
            user.token_version += 1
    db.flush()
    return {"students_updated": sum(item["student_id"] is not None for item in plan),
            "accounts_updated": sum(item["user_id"] is not None for item in plan),
            "default_passwords_updated": default_passwords_updated}
