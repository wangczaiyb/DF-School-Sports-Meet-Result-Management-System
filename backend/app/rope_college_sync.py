"""同步跳绳项目与学院总队的报名关联；只补缺失数据，调用方负责事务。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .college_policy import configured_colleges
from .models import CollegeTeam, Event, EventRound, Registration, Role, User
from .rope_rules import ROPE_RULES
from .services import audit, sync_event_rounds


def synchronize_rope_colleges(db: Session, meet_id: int, actor: User | None = None) -> dict:
    events = list(db.scalars(select(Event).where(Event.meet_id == meet_id, Event.code.in_(ROPE_RULES))))
    report = {"created_teams": 0, "created_registrations": 0, "college_count": 0}
    if not events:
        return report
    allowed = configured_colleges(db)
    teams = list(db.scalars(select(CollegeTeam).where(
        CollegeTeam.meet_id == meet_id, CollegeTeam.event_id.is_(None)
    ).order_by(CollegeTeam.id)))
    if allowed is not None:
        teams = [team for team in teams if team.college.strip() in allowed]
        present = {team.college.strip() for team in teams}
        missing = [college for college in allowed if college not in present]
        if missing:
            actor = actor or db.scalar(select(User).where(User.role.in_([Role.DEVELOPER, Role.SPORTS_TEACHER])).order_by(User.id))
            if actor is None:
                raise ValueError("补齐学院总队需要开发人员或体育部老师账号")
            for college in missing:
                team = CollegeTeam(meet_id=meet_id, college=college, team_name=f"{college}代表队", created_by_id=actor.id)
                db.add(team)
                teams.append(team)
            db.flush()
            report["created_teams"] = len(missing)
    report["college_count"] = len({team.college.strip() for team in teams})
    existing = set(db.execute(select(Registration.event_id, Registration.round_id, Registration.college_team_id)
                              .where(Registration.event_id.in_([event.id for event in events]))).all())
    for event in events:
        final = db.scalar(select(EventRound).where(EventRound.event_id == event.id, EventRound.stage == "FINAL"))
        if final is None:
            sync_event_rounds(db, event_id=event.id)
            final = db.scalar(select(EventRound).where(EventRound.event_id == event.id, EventRound.stage == "FINAL"))
        for team in teams:
            if (event.id, final.id, team.id) not in existing:
                db.add(Registration(event_id=event.id, round_id=final.id, college_team_id=team.id, status="REGISTERED"))
                report["created_registrations"] += 1
    db.flush()
    return report


def synchronize_existing_rope_meets(db: Session) -> list[dict]:
    """服务启动时修复已有跳绳项目的遗漏报名，不创建新的比赛项目。"""
    reports = []
    actor = db.scalar(select(User).where(User.role.in_([Role.DEVELOPER, Role.SPORTS_TEACHER])).order_by(User.id))
    for meet_id in db.scalars(select(Event.meet_id).where(Event.code.in_(ROPE_RULES)).distinct()):
        report = synchronize_rope_colleges(db, meet_id, actor)
        if report["created_teams"] or report["created_registrations"]:
            if actor:
                audit(db, actor, "SYNC_ROPE_COLLEGE_REGISTRATIONS", "sports_meet", meet_id, after=report,
                      reason="补齐参赛学院与已有跳绳项目的报名关联")
            reports.append({"meet_id": meet_id, **report})
    return reports
