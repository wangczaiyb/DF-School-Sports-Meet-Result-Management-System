from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any, Callable
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import (
    AuditLog,
    CollegeTeam,
    Event,
    EventAdminPermission,
    EventRound,
    EventSchedule,
    QualificationRecord,
    Registration,
    Result,
    ResultState,
    Role,
    SportsMeet,
    StudentRoster,
    User,
)
from ..services import mask_student_no, participant_for_registration, public_value
from .models import AIToolLog

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    def __init__(self, message: str, code: str = "PERMISSION_DENIED"):
        super().__init__(message)
        self.code = code
        self.message = message


class SportsToolRegistry:
    """Registry of AI Tools with strict RBAC guards and data scope validation."""

    def __init__(self):
        self._tools: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        allowed_roles: set[str] | None = None,
    ):
        def decorator(fn: Callable):
            self._tools[name] = {
                "name": name,
                "description": description,
                "parameters": parameters,
                "allowed_roles": allowed_roles,
                "handler": fn,
            }
            return fn
        return decorator

    def get_tool_definitions(self, user_role: str) -> list[dict[str, Any]]:
        """Return OpenAI-compatible tool definitions available to the given user role."""
        definitions = []
        for name, meta in self._tools.items():
            roles = meta["allowed_roles"]
            if roles is not None and user_role not in roles:
                continue
            definitions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": meta["description"],
                    "parameters": meta["parameters"],
                },
            })
        return definitions

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        user: User,
        db: Session,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a tool with RBAC check, scope guard, and audit logging."""
        start_time = time.perf_counter()
        tool_meta = self._tools.get(tool_name)

        if not tool_meta:
            error_msg = f"未知的系统工具: {tool_name}"
            self._log_tool_call(db, conversation_id, user.id, tool_name, arguments, None, False, error_msg, 0)
            return {"error": error_msg, "code": "TOOL_NOT_FOUND"}

        # 1. RBAC Role Validation
        allowed = tool_meta["allowed_roles"]
        if allowed is not None and user.role not in allowed:
            error_msg = f"权限不足：当前角色 ({user.role}) 无权调用工具 {tool_name}"
            self._log_tool_call(db, conversation_id, user.id, tool_name, arguments, None, False, error_msg, 0)
            return {"error": error_msg, "code": "PERMISSION_DENIED"}

        # 2. Handler execution
        try:
            handler = tool_meta["handler"]
            result = handler(arguments=arguments, user=user, db=db)
            latency = int((time.perf_counter() - start_time) * 1000)
            summary_text = str(result)[:300] if result else "OK"
            self._log_tool_call(db, conversation_id, user.id, tool_name, arguments, summary_text, True, None, latency)
            return result
        except ToolExecutionError as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            self._log_tool_call(db, conversation_id, user.id, tool_name, arguments, None, False, e.message, latency)
            return {"error": e.message, "code": e.code}
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            logger.exception(f"Tool {tool_name} execution failed: {e}")
            self._log_tool_call(db, conversation_id, user.id, tool_name, arguments, None, False, str(e), latency)
            return {"error": f"工具执行异常: {str(e)}", "code": "EXECUTION_ERROR"}

    def _log_tool_call(
        self,
        db: Session,
        conv_id: str | None,
        user_id: int,
        name: str,
        args: dict,
        summary: str | None,
        success: bool,
        error_msg: str | None,
        latency: int,
    ):
        try:
            log = AIToolLog(
                conversation_id=conv_id,
                user_id=user_id,
                tool_name=name,
                arguments=args,
                result_summary=summary,
                success=success,
                error_message=error_msg,
                latency_ms=latency,
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to record AI tool log: {e}")
            db.rollback()


# Global Registry Instance
tool_registry = SportsToolRegistry()

ALL_ROLES = {Role.DEVELOPER, Role.SPORTS_TEACHER, Role.REFEREE, Role.SCORER, Role.REFEREE_SCORER, Role.STUDENT}
STAFF_ROLES = {Role.DEVELOPER, Role.SPORTS_TEACHER, Role.REFEREE, Role.SCORER, Role.REFEREE_SCORER}
ADMIN_TEACHER = {Role.DEVELOPER, Role.SPORTS_TEACHER}


# ------------------------------------------------------------------------------
# 1. get_current_user_profile
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="get_current_user_profile",
    description="获取当前登录用户的基本信息、姓名、所属学院/部门与系统角色",
    parameters={"type": "object", "properties": {}},
    allowed_roles=ALL_ROLES,
)
def _tool_get_current_user(arguments: dict, user: User, db: Session) -> dict:
    data = {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "department": user.department,
        "status": user.status,
    }
    if user.role == Role.STUDENT:
        roster = db.scalar(select(StudentRoster).where(StudentRoster.user_id == user.id))
        if roster:
            data.update({
                "student_no": roster.student_no,
                "name": roster.name,
                "college": roster.college,
                "class_name": roster.class_name,
                "gender": roster.gender,
            })
    return data


# ------------------------------------------------------------------------------
# 2. get_sports_meets
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="get_sports_meets",
    description="查询系统中开设的运动会列表及状态（历史届次、筹备中、进行中、已结束）",
    parameters={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "可选按状态筛选: PREPARING, ONGOING, FINISHED"},
        },
    },
    allowed_roles=ALL_ROLES,
)
def _tool_get_sports_meets(arguments: dict, user: User, db: Session) -> dict:
    stmt = select(SportsMeet)
    status = arguments.get("status")
    if status:
        stmt = stmt.where(SportsMeet.status == status)
    if user.role == Role.STUDENT:
        stmt = stmt.where(SportsMeet.public_visible == True)
    meets = list(db.scalars(stmt.order_by(SportsMeet.start_date.desc())))
    return {
        "meets": [
            {
                "id": m.id,
                "name": m.name,
                "edition": m.edition,
                "status": m.status,
                "start_date": str(m.start_date),
                "end_date": str(m.end_date),
            }
            for m in meets
        ]
    }


# ------------------------------------------------------------------------------
# 3. get_events
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="get_events",
    description="查询某届运动会包含的比赛项目列表（如100米、跳远、跳绳、篮球、排球等）",
    parameters={
        "type": "object",
        "properties": {
            "meet_id": {"type": "integer", "description": "运动会 ID"},
            "gender_group": {"type": "string", "description": "性别组: MALE, FEMALE, MIXED"},
            "keyword": {"type": "string", "description": "项目名称关键字"},
        },
        "required": ["meet_id"],
    },
    allowed_roles=ALL_ROLES,
)
def _tool_get_events(arguments: dict, user: User, db: Session) -> dict:
    meet_id = arguments.get("meet_id")
    stmt = select(Event).where(Event.meet_id == meet_id)
    if arguments.get("gender_group"):
        stmt = stmt.where(Event.gender_group == arguments["gender_group"])
    if arguments.get("keyword"):
        stmt = stmt.where(Event.name.contains(arguments["keyword"]))

    events = list(db.scalars(stmt.order_by(Event.id)))
    return {
        "meet_id": meet_id,
        "events": [
            {
                "id": e.id,
                "code": e.code,
                "name": e.name,
                "gender_group": e.gender_group,
                "event_type": e.event_type,
                "result_unit": e.result_unit,
                "stage": e.stage,
                "scoring_places": e.scoring_places,
            }
            for e in events
        ],
    }


# ------------------------------------------------------------------------------
# 4. get_schedule
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="get_schedule",
    description="查询赛程安排，包括比赛时间、检录时间、比赛地点、组次与状态",
    parameters={
        "type": "object",
        "properties": {
            "meet_id": {"type": "integer", "description": "运动会 ID"},
            "event_id": {"type": "integer", "description": "可选指定项目 ID"},
            "date_str": {"type": "string", "description": "可选指定比赛日期，格式 YYYY-MM-DD"},
        },
    },
    allowed_roles=ALL_ROLES,
)
def _tool_get_schedule(arguments: dict, user: User, db: Session) -> dict:
    stmt = select(EventSchedule).join(Event, EventSchedule.event_id == Event.id)
    if arguments.get("meet_id"):
        stmt = stmt.where(Event.meet_id == arguments["meet_id"])
    if arguments.get("event_id"):
        stmt = stmt.where(EventSchedule.event_id == arguments["event_id"])
    if user.role == Role.STUDENT:
        stmt = stmt.where(EventSchedule.published == True)

    schedules = list(db.scalars(stmt.order_by(EventSchedule.competition_at)))
    items = []
    for s in schedules:
        ev = db.get(Event, s.event_id)
        rd = db.get(EventRound, s.round_id) if s.round_id else None
        items.append({
            "id": s.id,
            "event_id": s.event_id,
            "event_name": ev.name if ev else "",
            "round_name": rd.name if rd else "",
            "competition_at": str(s.competition_at),
            "check_in_at": str(s.check_in_at) if s.check_in_at else None,
            "venue": s.venue,
            "heat": s.heat,
            "status": s.status,
            "notes": s.notes,
        })
    return {"schedules": items}


# ------------------------------------------------------------------------------
# 5. get_student_schedule (Student Own Schedule)
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="get_student_schedule",
    description="查询学生个人的参赛日程、赛程安排、组次与道次（学生仅可查本人，管理人员可指定学号）",
    parameters={
        "type": "object",
        "properties": {
            "student_no": {"type": "string", "description": "学号（学生角色自动绑定本人学号，忽略传入）"},
        },
    },
    allowed_roles=ALL_ROLES,
)
def _tool_get_student_schedule(arguments: dict, user: User, db: Session) -> dict:
    if user.role == Role.STUDENT:
        roster = db.scalar(select(StudentRoster).where(StudentRoster.user_id == user.id))
        if not roster:
            raise ToolExecutionError("未关联学生档案信息")
    else:
        st_no = arguments.get("student_no")
        if not st_no:
            raise ToolExecutionError("管理人员查询学生赛程需提供学号 (student_no)")
        roster = db.scalar(select(StudentRoster).where(StudentRoster.student_no == st_no))
        if not roster:
            raise ToolExecutionError(f"未找到学号为 {st_no} 的学生档案")

    registrations = list(db.scalars(select(Registration).where(Registration.student_id == roster.id)))
    results = []
    for r in registrations:
        ev = db.get(Event, r.event_id)
        rd = db.get(EventRound, r.round_id)
        sched = db.scalar(
            select(EventSchedule).where(
                EventSchedule.event_id == r.event_id,
                EventSchedule.round_id == r.round_id,
                EventSchedule.published == True,
            )
        )
        results.append({
            "event_name": ev.name if ev else "",
            "round_name": rd.name if rd else "",
            "stage": rd.stage if rd else "",
            "bib_no": r.bib_no,
            "heat": r.heat,
            "lane": r.lane,
            "status": r.status,
            "competition_at": str(sched.competition_at) if sched else "待排赛",
            "venue": sched.venue if sched else "待公布",
            "check_in_at": str(sched.check_in_at) if sched and sched.check_in_at else None,
        })
    return {
        "student_name": roster.name,
        "student_no": roster.student_no,
        "college": roster.college,
        "items": results,
    }


# ------------------------------------------------------------------------------
# 6. get_student_results (Student Own Results)
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="get_student_results",
    description="查询学生个人的比赛成绩、最终名次与所获积分（学生仅可查本人已发布成绩）",
    parameters={
        "type": "object",
        "properties": {
            "student_no": {"type": "string", "description": "学号（学生自动查本人）"},
        },
    },
    allowed_roles=ALL_ROLES,
)
def _tool_get_student_results(arguments: dict, user: User, db: Session) -> dict:
    if user.role == Role.STUDENT:
        roster = db.scalar(select(StudentRoster).where(StudentRoster.user_id == user.id))
        if not roster:
            raise ToolExecutionError("未关联学生档案")
    else:
        st_no = arguments.get("student_no")
        if not st_no:
            raise ToolExecutionError("管理人员需提供学号 (student_no)")
        roster = db.scalar(select(StudentRoster).where(StudentRoster.student_no == st_no))
        if not roster:
            raise ToolExecutionError(f"未找到学号 {st_no} 的学生")

    regs = list(db.scalars(select(Registration).where(Registration.student_id == roster.id)))
    reg_ids = [r.id for r in regs]
    if not reg_ids:
        return {"student_name": roster.name, "results": []}

    stmt = select(Result).where(Result.registration_id.in_(reg_ids), Result.published_at.is_not(None))
    result_rows = list(db.scalars(stmt))
    items = []
    for row in result_rows:
        ev = db.get(Event, row.event_id)
        rd = db.get(EventRound, row.round_id) if row.round_id else None
        items.append({
            "event_name": ev.name if ev else "",
            "round_name": rd.name if rd else "",
            "raw_value": str(row.published_raw_value or row.raw_value or ""),
            "unit": ev.result_unit if ev else "",
            "competition_status": row.published_competition_status or row.competition_status,
            "rank": row.published_rank or row.rank,
            "points": float(row.published_points or row.points or 0),
            "published_at": str(row.published_at),
        })
    return {
        "student_name": roster.name,
        "student_no": roster.student_no,
        "college": roster.college,
        "results": items,
    }


# ------------------------------------------------------------------------------
# 7. get_rankings (College Team Rankings)
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="get_rankings",
    description="查询某届运动会各学院团体总积分与排行榜",
    parameters={
        "type": "object",
        "properties": {
            "meet_id": {"type": "integer", "description": "运动会 ID"},
        },
        "required": ["meet_id"],
    },
    allowed_roles=ALL_ROLES,
)
def _tool_get_rankings(arguments: dict, user: User, db: Session) -> dict:
    meet_id = arguments.get("meet_id")
    events = list(db.scalars(select(Event).where(Event.meet_id == meet_id)))
    event_ids = [e.id for e in events]
    if not event_ids:
        return {"meet_id": meet_id, "rankings": []}

    results = list(
        db.scalars(
            select(Result).where(Result.event_id.in_(event_ids), Result.published_at.is_not(None))
        )
    )

    college_scores: dict[str, Decimal] = {}
    for r in results:
        reg = db.get(Registration, r.registration_id)
        p = participant_for_registration(db, reg)
        c = p.get("college")
        if c:
            college_scores[c] = college_scores.get(c, Decimal("0")) + Decimal(r.published_points or r.points or 0)

    sorted_colleges = sorted(college_scores.items(), key=lambda x: x[1], reverse=True)
    rankings = [
        {"rank": idx + 1, "college": name, "points": float(points)}
        for idx, (name, points) in enumerate(sorted_colleges)
    ]
    return {"meet_id": meet_id, "rankings": rankings}


# ------------------------------------------------------------------------------
# 8. get_results (Event Results)
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="get_results",
    description="查询某比赛项目的成绩排名列表（学生仅能看已发布，管理人员按权限查看）",
    parameters={
        "type": "object",
        "properties": {
            "event_id": {"type": "integer", "description": "项目 ID"},
            "round_id": {"type": "integer", "description": "可选轮次 ID"},
        },
        "required": ["event_id"],
    },
    allowed_roles=ALL_ROLES,
)
def _tool_get_results(arguments: dict, user: User, db: Session) -> dict:
    event_id = arguments["event_id"]
    event = db.get(Event, event_id)
    if not event:
        raise ToolExecutionError("比赛项目不存在")

    stmt = select(Result).where(Result.event_id == event_id)
    if arguments.get("round_id"):
        stmt = stmt.where(Result.round_id == arguments["round_id"])

    is_student = user.role == Role.STUDENT
    if is_student:
        stmt = stmt.where(Result.published_at.is_not(None))
    elif user.role in (Role.REFEREE, Role.SCORER):
        # Check event permission
        perm = db.scalar(select(EventAdminPermission).where(EventAdminPermission.user_id == user.id, EventAdminPermission.event_id == event_id))
        if not perm and user.role != Role.DEVELOPER:
            raise ToolExecutionError("您没有该项目的查看与操作权限")

    rows = list(db.scalars(stmt.order_by(Result.rank, Result.id)))
    results = []
    for r in rows:
        reg = db.get(Registration, r.registration_id)
        p = participant_for_registration(db, reg)
        st_no = mask_student_no(p["student_no"]) if (is_student and p["student_no"]) else p["student_no"]
        results.append({
            "id": r.id,
            "name": p["name"],
            "student_no": st_no,
            "college": p["college"],
            "heat": reg.heat if reg else None,
            "lane": reg.lane if reg else None,
            "raw_value": str(public_value(r, "raw_value") if is_student else (r.raw_value or "")),
            "competition_status": r.published_competition_status if is_student else r.competition_status,
            "rank": public_value(r, "rank") if is_student else r.rank,
            "points": float(public_value(r, "points") if is_student else (r.points or 0)),
            "state": r.state,
        })
    return {
        "event_id": event_id,
        "event_name": event.name,
        "result_unit": event.result_unit,
        "items": results,
    }


# ------------------------------------------------------------------------------
# 9. get_pending_reviews (Staff Only: Pending Results to Review)
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="get_pending_reviews",
    description="查询待裁判员审核或待体育老师终审的成绩列表（按权限过滤，仅裁判和管理员可用）",
    parameters={
        "type": "object",
        "properties": {
            "meet_id": {"type": "integer", "description": "可选运动会 ID"},
            "event_id": {"type": "integer", "description": "可选项目 ID"},
        },
    },
    allowed_roles=STAFF_ROLES,
)
def _tool_get_pending_reviews(arguments: dict, user: User, db: Session) -> dict:
    stmt = select(Result).where(Result.state.in_([ResultState.SUBMITTED, ResultState.REVIEWED]))
    if arguments.get("event_id"):
        stmt = stmt.where(Result.event_id == arguments["event_id"])
    elif arguments.get("meet_id"):
        stmt = stmt.join(Event, Result.event_id == Event.id).where(Event.meet_id == arguments["meet_id"])

    # If referee/scorer, only show assigned events
    if user.role in (Role.REFEREE, Role.REFEREE_SCORER):
        allowed_event_ids = list(
            db.scalars(
                select(EventAdminPermission.event_id).where(
                    EventAdminPermission.user_id == user.id,
                    EventAdminPermission.can_review == True,
                )
            )
        )
        stmt = stmt.where(Result.event_id.in_(allowed_event_ids))

    pending_rows = list(db.scalars(stmt.order_by(Result.event_id, Result.id)))
    items = []
    for r in pending_rows:
        ev = db.get(Event, r.event_id)
        reg = db.get(Registration, r.registration_id)
        p = participant_for_registration(db, reg)
        items.append({
            "result_id": r.id,
            "event_id": r.event_id,
            "event_name": ev.name if ev else "",
            "participant": p["name"],
            "college": p["college"],
            "raw_value": str(r.raw_value or ""),
            "state": r.state,
            "notes": r.notes,
        })
    return {"total_pending": len(items), "items": items}


# ------------------------------------------------------------------------------
# 10. get_advancement (Advancement / Qualification List)
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="get_advancement",
    description="查询选手由初赛晋级到晋级赛或决赛的名单记录",
    parameters={
        "type": "object",
        "properties": {
            "event_id": {"type": "integer", "description": "项目 ID"},
        },
        "required": ["event_id"],
    },
    allowed_roles=ALL_ROLES,
)
def _tool_get_advancement(arguments: dict, user: User, db: Session) -> dict:
    event_id = arguments["event_id"]
    event = db.get(Event, event_id)
    if not event:
        raise ToolExecutionError("比赛项目不存在")

    regs = list(db.scalars(select(Registration).where(Registration.event_id == event_id)))
    reg_ids = [r.id for r in regs]
    records = list(db.scalars(select(QualificationRecord).where(QualificationRecord.registration_id.in_(reg_ids))))

    items = []
    for rec in records:
        reg = db.get(Registration, rec.registration_id)
        p = participant_for_registration(db, reg)
        from_round = db.get(EventRound, rec.from_round_id) if rec.from_round_id else None
        next_round = db.get(EventRound, rec.next_round_id) if rec.next_round_id else None
        items.append({
            "participant": p["name"],
            "college": p["college"],
            "from_round": from_round.name if from_round else "",
            "next_round": next_round.name if next_round else "",
            "status": rec.status,
            "adjustment_reason": rec.adjustment_reason,
        })
    return {"event_name": event.name, "advancements": items}


# ------------------------------------------------------------------------------
# 11. get_event_statistics (Meet Overview Statistics)
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="get_event_statistics",
    description="统计运动会各项数据指标：项目总数、参赛人次、成绩总数、已发布数、待审核数",
    parameters={
        "type": "object",
        "properties": {
            "meet_id": {"type": "integer", "description": "运动会 ID"},
        },
        "required": ["meet_id"],
    },
    allowed_roles=ALL_ROLES,
)
def _tool_get_event_statistics(arguments: dict, user: User, db: Session) -> dict:
    meet_id = arguments["meet_id"]
    meet = db.get(SportsMeet, meet_id)
    if not meet:
        raise ToolExecutionError("运动会不存在")

    event_count = db.scalar(select(func.count(Event.id)).where(Event.meet_id == meet_id)) or 0
    events = list(db.scalars(select(Event.id).where(Event.meet_id == meet_id)))

    reg_count = 0
    res_count = 0
    published_count = 0
    pending_count = 0

    if events:
        reg_count = db.scalar(select(func.count(Registration.id)).where(Registration.event_id.in_(events))) or 0
        res_count = db.scalar(select(func.count(Result.id)).where(Result.event_id.in_(events))) or 0
        published_count = db.scalar(select(func.count(Result.id)).where(Result.event_id.in_(events), Result.published_at.is_not(None))) or 0
        pending_count = db.scalar(select(func.count(Result.id)).where(Result.event_id.in_(events), Result.state.in_([ResultState.SUBMITTED, ResultState.REVIEWED]))) or 0

    return {
        "meet_name": meet.name,
        "edition": meet.edition,
        "status": meet.status,
        "total_events": event_count,
        "total_registrations": reg_count,
        "total_results": res_count,
        "published_results": published_count,
        "pending_reviews": pending_count,
    }


# ------------------------------------------------------------------------------
# 12. get_audit_logs (Developer Only)
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="get_audit_logs",
    description="查询系统操作审计日志（仅开发人员/超管权限可用）",
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "返回条数，默认 10 条"},
        },
    },
    allowed_roles={Role.DEVELOPER},
)
def _tool_get_audit_logs(arguments: dict, user: User, db: Session) -> dict:
    limit = min(int(arguments.get("limit", 10)), 50)
    logs = list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)))
    return {
        "logs": [
            {
                "id": l.id,
                "actor": l.actor_username,
                "action": l.action,
                "target_type": l.target_type,
                "target_id": l.target_id,
                "reason": l.reason,
                "created_at": str(l.created_at),
            }
            for l in logs
        ]
    }


# ------------------------------------------------------------------------------
# 13. check_result_anomalies (Staff Only: AI-Assisted Anomaly Scan)
# ------------------------------------------------------------------------------
@tool_registry.register(
    name="check_result_anomalies",
    description="执行成绩异常辅助诊断分析，检测极端异常数值、同项目异常偏离、状态冲突与数据缺失",
    parameters={
        "type": "object",
        "properties": {
            "event_id": {"type": "integer", "description": "指定比赛项目 ID"},
            "meet_id": {"type": "integer", "description": "或指定运动会 ID 进行批量扫描"},
        },
    },
    allowed_roles=STAFF_ROLES,
)
def _tool_check_result_anomalies(arguments: dict, user: User, db: Session) -> dict:
    from .anomaly import detect_result_anomalies
    return detect_result_anomalies(
        db=db,
        event_id=arguments.get("event_id"),
        meet_id=arguments.get("meet_id"),
    )
