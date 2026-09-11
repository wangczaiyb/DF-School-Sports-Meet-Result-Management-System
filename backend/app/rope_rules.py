from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CollegeTeamMember, Event, RopeLineupMember, StudentRoster


ROPE_RULES = {
    "ROPE_SINGLE": {
        "title": "“前单跳”计时计数团体挑战赛",
        "team_size": 22,
        "lineup_size": 10,
        "jumper_count": 10,
        "turner_count": 0,
        "male_jumpers": 5,
        "female_jumpers": 5,
        "duration_seconds": 60,
        "ranking": "10名队员每人1分钟，团体总次数多者名次列前",
    },
    "ROPE_SYNC": {
        "title": "集体单摇跳",
        "team_size": 22,
        "lineup_size": 12,
        "jumper_count": 10,
        "turner_count": 2,
        "male_jumpers": 5,
        "female_jumpers": 5,
        "duration_seconds": 300,
        "target_count": 30,
        "ranking": "5分钟内完成30次者按用时升序；未完成者按有效次数降序并排在完赛队之后",
    },
    "ROPE_FIG8": {
        "title": "“8”字环绕跳",
        "team_size": 22,
        "lineup_size": 22,
        "jumper_count": 20,
        "turner_count": 2,
        "male_jumpers": 10,
        "female_jumpers": 10,
        "duration_seconds": 300,
        "ranking": "5分钟内按固定先后顺序进行，全队有效完成次数多者名次列前",
    },
}


def rope_rule_for_event(event: Event | None) -> dict | None:
    if not event:
        return None
    return ROPE_RULES.get(event.code)


def rope_lineup_status(db: Session, event: Event, college_team_id: int, lineup: list[RopeLineupMember] | None = None) -> dict:
    rule = rope_rule_for_event(event)
    if not rule:
        return {"valid": False, "errors": ["该项目不是标准跳绳项目"]}

    team_members = list(db.scalars(select(CollegeTeamMember).where(CollegeTeamMember.team_id == college_team_id)))
    student_by_id = {
        row.student_id: db.get(StudentRoster, row.student_id)
        for row in team_members
    }
    rows = lineup if lineup is not None else list(
        db.scalars(
            select(RopeLineupMember)
            .where(RopeLineupMember.event_id == event.id, RopeLineupMember.college_team_id == college_team_id)
            .order_by(RopeLineupMember.role, RopeLineupMember.sequence, RopeLineupMember.id)
        )
    )
    jumpers = [row for row in rows if row.role == "JUMPER"]
    turners = [row for row in rows if row.role == "TURNER"]
    jumper_students = [student_by_id.get(row.student_id) for row in jumpers]
    male_jumpers = sum(1 for student in jumper_students if student and student.gender == "男")
    female_jumpers = sum(1 for student in jumper_students if student and student.gender == "女")
    selected_ids = [row.student_id for row in rows]

    errors: list[str] = []
    if len(team_members) != rule["team_size"]:
        errors.append(f"学院跳绳队必须登记 {rule['team_size']} 人，当前 {len(team_members)} 人")
    if len(rows) != rule["lineup_size"]:
        errors.append(f"本项目阵容必须选择 {rule['lineup_size']} 人，当前 {len(rows)} 人")
    if len(jumpers) != rule["jumper_count"]:
        errors.append(f"跳绳者必须为 {rule['jumper_count']} 人，当前 {len(jumpers)} 人")
    if len(turners) != rule["turner_count"]:
        errors.append(f"摇绳者必须为 {rule['turner_count']} 人，当前 {len(turners)} 人")
    if male_jumpers != rule["male_jumpers"] or female_jumpers != rule["female_jumpers"]:
        errors.append(f"跳绳者须男 {rule['male_jumpers']} 人、女 {rule['female_jumpers']} 人，当前男 {male_jumpers} 人、女 {female_jumpers} 人")
    if len(selected_ids) != len(set(selected_ids)):
        errors.append("同一运动员不能在同一项目阵容中重复")
    missing = [student_id for student_id in selected_ids if student_id not in student_by_id]
    if missing:
        errors.append("阵容中包含不属于该学院代表队的运动员")

    return {
        "valid": not errors,
        "errors": errors,
        "team_member_count": len(team_members),
        "lineup_count": len(rows),
        "jumper_count": len(jumpers),
        "turner_count": len(turners),
        "male_jumpers": male_jumpers,
        "female_jumpers": female_jumpers,
    }


def rope_detail_payload(detail, public: bool = False, published: bool = False) -> dict | None:
    if not detail:
        return None
    if public and published and detail.published_detail is not None:
        return detail.published_detail
    return {
        "individual_counts": detail.individual_counts or [],
        "completed_target": detail.completed_target,
        "elapsed_seconds": detail.elapsed_seconds,
        "completed_count": detail.completed_count,
    }
