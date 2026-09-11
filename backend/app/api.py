from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from openpyxl import Workbook, load_workbook
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import sys
from .config import PROJECT_ROOT, get_settings
from .database import get_db
from .dependencies import business_admin, developer_only, get_current_user, manager_only, student_only
from .models import (
    AdministratorProfile,
    AuditLog,
    CollegeTeam,
    CollegeTeamMember,
    Event,
    EventAdminPermission,
    EventRound,
    EventSchedule,
    QualificationRecord,
    Registration,
    Result,
    ResultReview,
    ResultState,
    Role,
    RopeLineupMember,
    RopeResultDetail,
    ScoringModel,
    ScoringModelBinding,
    ScoringModelItem,
    SportsMeet,
    StudentRoster,
    SystemSetting,
    TournamentMatch,
    User,
    UserStatus,
    utcnow,
)
from .schemas import (
    AccountCreate,
    AccountUpdate,
    ChangePasswordRequest,
    CollegeTeamCreate,
    CollegeTeamGenerate,
    CollegeTeamMemberBatchCreate,
    CollegeTeamMemberCreate,
    CollegeTeamMemberUpdate,
    EventCreate,
    LoginRequest,
    MeetCreate,
    ModelBindRequest,
    PermissionUpsert,
    ReasonRequest,
    RegistrationBatchCreate,
    RegistrationAdvanceRequest,
    RegistrationSeedRequest,
    RegistrationUpdate,
    ResetPasswordRequest,
    ResultAction,
    ResultEntry,
    RopeInitializeRequest,
    RopeLineupUpsert,
    RopeResultEntry,
    ScheduleUpsert,
    ScoringModelCreate,
    SettingsUpdate,
    StudentRosterCreate,
    StudentRegisterRequest,
)
from .security import create_access_token, hash_password, verify_password
from .services import (
    ADMIN_ROLES,
    add_review,
    audit,
    calculate_rankings,
    create_score_workbook,
    ensure_last_developer_safe,
    has_event_permission,
    mask_student_no,
    participant_for_registration,
    require_event_permission,
    result_dict,
    snapshot_user,
    sync_event_rounds,
    utc_iso,
    validate_account_quota,
)
from .rope_rules import ROPE_RULES, rope_detail_payload, rope_lineup_status, rope_rule_for_event


router = APIRouter()
settings = get_settings()


def _account_dict(db: Session, user: User) -> dict:
    data = snapshot_user(user)
    profile = db.scalar(select(AdministratorProfile).where(AdministratorProfile.user_id == user.id))
    data.update({
        "employee_no": profile.employee_no if profile else None,
        "phone": profile.phone if profile else None,
    })
    return data


def _login(db: Session, data: LoginRequest, allowed_roles: set[str]) -> dict:
    user = db.scalar(select(User).where(User.username == data.username))
    now = utcnow()
    if user and user.locked_until and user.locked_until > now:
        minutes = max(1, int((user.locked_until - now).total_seconds() / 60) + 1)
        raise HTTPException(423, f"账号已锁定，请在 {minutes} 分钟后重试")
    if not user or not verify_password(data.password, user.password_hash):
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                user.locked_until = now + timedelta(minutes=15)
                user.failed_login_count = 0
            db.commit()
        raise HTTPException(401, "用户名或密码错误")
    if user.role not in allowed_roles:
        raise HTTPException(403, "账号身份选择不正确")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(403, f"账号已冻结：{user.frozen_reason or '请联系开发人员'}")
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    return {
        "access_token": create_access_token(user.id, user.role, user.token_version),
        "token_type": "bearer",
        "user": snapshot_user(user),
        "first_login_change_required": user.first_login_change_required if user.role != Role.STUDENT else False,
    }


@router.get("/public/settings")
def public_settings(db: Session = Depends(get_db)):
    return {row.key: row.value for row in db.scalars(select(SystemSetting))}


@router.post("/auth/developer-login")
def developer_login(data: LoginRequest, db: Session = Depends(get_db)):
    return _login(db, data, {Role.DEVELOPER})


@router.post("/auth/admin-login")
def admin_login(data: LoginRequest, db: Session = Depends(get_db)):
    return _login(db, data, set(ADMIN_ROLES))


@router.post("/auth/student-login")
def student_login(data: LoginRequest, db: Session = Depends(get_db)):
    return _login(db, data, {Role.STUDENT})


@router.post("/auth/student-register")
def student_register(data: StudentRegisterRequest, db: Session = Depends(get_db)):
    roster = db.scalar(
        select(StudentRoster).where(StudentRoster.student_no == data.student_no, StudentRoster.name == data.name)
    )
    if not roster:
        raise HTTPException(404, "学号和姓名与参赛名单不匹配")
    if len(data.student_no) < 6:
        raise HTTPException(422, "学号不足 6 位，请联系管理员")
    if roster.activated or roster.user_id:
        raise HTTPException(409, "该学号已经注册")
    validate_account_quota(db, Role.STUDENT)
    initial_password = f"DF{data.student_no[-6:]}"
    user = User(
        username=data.student_no,
        password_hash=hash_password(initial_password),
        role=Role.STUDENT,
        display_name=roster.name,
        department=roster.college,
        first_login_change_required=False,
    )
    db.add(user)
    db.flush()
    roster.user_id = user.id
    roster.activated = True
    db.commit()
    return {"message": "账号激活成功", "initial_password_hint": "DF + 学号后6位"}


@router.post("/auth/change-password")
def change_password(data: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "当前密码不正确")
    user.password_hash = hash_password(data.new_password)
    user.first_login_change_required = False
    user.token_version += 1
    audit(db, user, "CHANGE_PASSWORD", "user", user.id)
    db.commit()
    return {"message": "密码修改成功，请重新登录"}


@router.get("/auth/me")
def auth_me(user: User = Depends(get_current_user)):
    return {**snapshot_user(user), "first_login_change_required": user.first_login_change_required if user.role != Role.STUDENT else False}


@router.get("/dashboard/summary")
def dashboard_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == Role.STUDENT:
        roster = db.scalar(select(StudentRoster).where(StudentRoster.user_id == user.id))
        registration_ids = list(db.scalars(select(Registration.id).where(Registration.student_id == roster.id))) if roster else []
        qualified_count = 0
        if roster:
            qualified_count = db.scalar(
                select(func.count(Registration.id))
                .join(EventRound, Registration.round_id == EventRound.id)
                .where(Registration.student_id == roster.id, EventRound.stage.in_(["SEMIFINAL", "FINAL"]))
            ) or 0
        return {
            "registrations": len(registration_ids),
            "published_results": db.scalar(select(func.count(Result.id)).where(Result.registration_id.in_(registration_ids), Result.published_at.is_not(None))) if registration_ids else 0,
            "qualified": qualified_count,
        }
    event_ids = None
    if user.role not in {Role.DEVELOPER, Role.SPORTS_TEACHER}:
        event_ids = list(db.scalars(select(EventAdminPermission.event_id).where(EventAdminPermission.user_id == user.id)))
    event_count_stmt = select(func.count(Event.id))
    if event_ids is not None:
        event_count_stmt = event_count_stmt.where(Event.id.in_(event_ids))
    return {
        "meets": db.scalar(select(func.count(SportsMeet.id))) or 0,
        "events": db.scalar(event_count_stmt) or 0,
        "pending_review": db.scalar(select(func.count(Result.id)).where(Result.state.in_([ResultState.SUBMITTED, ResultState.REVIEWED]))) or 0,
        "published": db.scalar(select(func.count(Result.id)).where(Result.state == ResultState.PUBLISHED)) or 0,
    }


@router.get("/developer/accounts")
def list_accounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: str | None = None,
    keyword: str | None = None,
    _actor: User = Depends(developer_only),
    db: Session = Depends(get_db),
):
    stmt = select(User)
    count_stmt = select(func.count(User.id))
    if role:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)
    if keyword:
        condition = or_(User.username.contains(keyword), User.display_name.contains(keyword))
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    rows = list(db.scalars(stmt.order_by(User.id).offset((page - 1) * page_size).limit(page_size)))
    quotas = {
        "developers": db.scalar(select(func.count(User.id)).where(User.role == Role.DEVELOPER)) or 0,
        "sports_teachers": db.scalar(select(func.count(User.id)).where(User.role == Role.SPORTS_TEACHER)) or 0,
        "administrators": db.scalar(select(func.count(User.id)).where(User.role.in_(list(ADMIN_ROLES)))) or 0,
        "students": db.scalar(select(func.count(User.id)).where(User.role == Role.STUDENT)) or 0,
    }
    return {"items": [_account_dict(db, row) for row in rows], "total": db.scalar(count_stmt) or 0, "quotas": quotas}


@router.post("/developer/accounts")
def create_account(data: AccountCreate, actor: User = Depends(developer_only), db: Session = Depends(get_db)):
    validate_account_quota(db, data.role)
    if db.scalar(select(User.id).where(User.username == data.username)):
        raise HTTPException(409, "用户名已存在")
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
        display_name=data.display_name,
        department=data.department,
        status=UserStatus.ACTIVE if data.enabled else UserStatus.FROZEN,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.add(user)
    db.flush()
    if data.role in ADMIN_ROLES:
        employee_no = data.employee_no or f"AUTO{user.id:05d}"
        if db.scalar(select(AdministratorProfile.id).where(AdministratorProfile.employee_no == employee_no)):
            raise HTTPException(409, "工号已存在")
        db.add(AdministratorProfile(user_id=user.id, employee_no=employee_no, phone=data.phone))
    db.flush()
    audit(db, actor, "CREATE_ACCOUNT", "user", user.id, after=_account_dict(db, user))
    db.commit()
    return _account_dict(db, user)


@router.put("/developer/accounts/{user_id}")
def update_account(user_id: int, data: AccountUpdate, actor: User = Depends(developer_only), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "账号不存在")
    before = _account_dict(db, target)
    values = data.model_dump(exclude_unset=True)
    if data.username and data.username != target.username and db.scalar(select(User.id).where(User.username == data.username)):
        raise HTTPException(409, "用户名已存在")
    if data.role and data.role != target.role:
        ensure_last_developer_safe(db, actor, target, next_role=data.role)
        validate_account_quota(db, data.role, exclude_user_id=target.id)
    for field in ["username", "display_name", "role", "department"]:
        if field in values and values[field] is not None:
            setattr(target, field, values[field])
    next_role = data.role or target.role
    profile = db.scalar(select(AdministratorProfile).where(AdministratorProfile.user_id == target.id))
    if next_role in ADMIN_ROLES:
        employee_no = (data.employee_no or "").strip() if "employee_no" in values else (profile.employee_no if profile else "")
        employee_no = employee_no or f"AUTO{target.id:05d}"
        duplicate_employee = db.scalar(
            select(AdministratorProfile.id).where(
                AdministratorProfile.employee_no == employee_no,
                AdministratorProfile.user_id != target.id,
            )
        )
        if duplicate_employee:
            raise HTTPException(409, "工号已存在")
        if not profile:
            profile = AdministratorProfile(user_id=target.id, employee_no=employee_no)
            db.add(profile)
        else:
            profile.employee_no = employee_no
        if "phone" in values:
            profile.phone = (data.phone or "").strip() or None
    elif profile:
        db.delete(profile)
    if data.password:
        target.password_hash = hash_password(data.password)
        target.token_version += 1
    target.updated_by_id = actor.id
    db.flush()
    audit(db, actor, "UPDATE_ACCOUNT", "user", target.id, before=before, after=_account_dict(db, target))
    db.commit()
    return _account_dict(db, target)


@router.post("/developer/accounts/{user_id}/freeze")
def freeze_account(user_id: int, data: ReasonRequest, actor: User = Depends(developer_only), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "账号不存在")
    ensure_last_developer_safe(db, actor, target, freezing=True)
    before = snapshot_user(target)
    target.status = UserStatus.FROZEN
    target.frozen_reason = data.reason
    target.token_version += 1
    audit(db, actor, "FREEZE_ACCOUNT", "user", target.id, before, snapshot_user(target), data.reason)
    db.commit()
    return {"message": "账号已冻结"}


@router.post("/developer/accounts/{user_id}/unfreeze")
def unfreeze_account(user_id: int, actor: User = Depends(developer_only), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "账号不存在")
    target.status = UserStatus.ACTIVE
    target.frozen_reason = None
    audit(db, actor, "UNFREEZE_ACCOUNT", "user", target.id, after=snapshot_user(target))
    db.commit()
    return {"message": "账号已解冻"}


@router.post("/developer/accounts/{user_id}/reset-password")
def reset_password(user_id: int, data: ResetPasswordRequest, actor: User = Depends(developer_only), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "账号不存在")
    if target.role == Role.STUDENT:
        password = data.password or f"DF{target.username[-6:]}"
        target.first_login_change_required = False
    else:
        if not data.password:
            raise HTTPException(422, "管理人员重置密码时必须输入新密码")
        password = data.password
    target.password_hash = hash_password(password)
    target.token_version += 1
    audit(db, actor, "RESET_PASSWORD", "user", target.id)
    db.commit()
    return {"message": "密码已重置"}


@router.post("/developer/accounts/{user_id}/force-logout")
def force_logout(user_id: int, actor: User = Depends(developer_only), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "账号不存在")
    target.token_version += 1
    audit(db, actor, "FORCE_LOGOUT", "user", target.id)
    db.commit()
    return {"message": "已强制退出该账号"}


@router.get("/developer/settings")
def get_settings_data(_actor: User = Depends(developer_only), db: Session = Depends(get_db)):
    return {row.key: row.value for row in db.scalars(select(SystemSetting))}


@router.put("/developer/settings")
def update_settings(data: SettingsUpdate, actor: User = Depends(developer_only), db: Session = Depends(get_db)):
    for key, value in data.values.items():
        row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        before = {"value": row.value} if row else None
        if row:
            row.value = value
            row.updated_by_id = actor.id
        else:
            row = SystemSetting(key=key, value=value, updated_by_id=actor.id)
            db.add(row)
        audit(db, actor, "UPDATE_SETTING", "setting", key, before, {"value": value})
    db.commit()
    return {"message": "系统配置已保存"}


@router.get("/developer/audit-logs")
def audit_logs(page: int = 1, page_size: int = 50, _actor: User = Depends(developer_only), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)))
    return {"items": [{"id": r.id, "actor": r.actor_username, "action": r.action, "target_type": r.target_type, "target_id": r.target_id, "reason": r.reason, "created_at": utc_iso(r.created_at)} for r in rows]}


@router.get("/sports-teacher/meets")
def list_meets(_actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(SportsMeet).order_by(SportsMeet.start_date.desc())))


@router.post("/sports-teacher/meets")
def create_meet(data: MeetCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    if data.end_date < data.start_date:
        raise HTTPException(422, "结束日期不能早于开始日期")
    duplicate = db.scalar(select(SportsMeet.id).where(SportsMeet.name == data.name, SportsMeet.edition == data.edition))
    if duplicate:
        raise HTTPException(409, "同名同届运动会已存在")
    meet = SportsMeet(**data.model_dump(), created_by_id=actor.id)
    try:
        db.add(meet)
        db.flush()
        audit(db, actor, "CREATE_MEET", "sports_meet", meet.id, after=data.model_dump(mode="json"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "同名同届运动会已存在") from exc
    return meet


@router.put("/sports-teacher/meets/{meet_id}")
def update_meet(meet_id: int, data: MeetCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    meet = db.get(SportsMeet, meet_id)
    if not meet:
        raise HTTPException(404, "运动会不存在")
    if data.end_date < data.start_date:
        raise HTTPException(422, "结束日期不能早于开始日期")
    duplicate = db.scalar(select(SportsMeet.id).where(SportsMeet.name == data.name, SportsMeet.edition == data.edition, SportsMeet.id != meet.id))
    if duplicate:
        raise HTTPException(409, "同名同届运动会已存在")
    before = {field: getattr(meet, field) for field in type(data).model_fields}
    for field, value in data.model_dump().items():
        setattr(meet, field, value)
    audit(db, actor, "UPDATE_MEET", "sports_meet", meet.id, before=before, after=data.model_dump(mode="json"))
    db.commit()
    return meet


@router.delete("/sports-teacher/meets/{meet_id}")
def delete_meet(meet_id: int, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    meet = db.get(SportsMeet, meet_id)
    if not meet:
        raise HTTPException(404, "运动会不存在")
    dependencies = {
        "比赛项目": db.scalar(select(func.count(Event.id)).where(Event.meet_id == meet.id)) or 0,
        "学院代表队": db.scalar(select(func.count(CollegeTeam.id)).where(CollegeTeam.meet_id == meet.id)) or 0,
        "计分绑定": db.scalar(select(func.count(ScoringModelBinding.id)).where(ScoringModelBinding.meet_id == meet.id)) or 0,
    }
    if any(dependencies.values()):
        detail = "、".join(f"{name}{count}项" for name, count in dependencies.items() if count)
        raise HTTPException(409, f"该运动会仍有{detail}，请先处理关联数据")
    before = {"name": meet.name, "edition": meet.edition}
    db.delete(meet)
    audit(db, actor, "DELETE_MEET", "sports_meet", meet_id, before=before)
    db.commit()
    return {"message": "运动会已删除"}


def _student_roster_dict(row: StudentRoster) -> dict:
    return {
        "id": row.id,
        "student_no": row.student_no,
        "name": row.name,
        "gender": row.gender,
        "college": row.college,
        "major": row.major,
        "class_name": row.class_name,
        "activated": row.activated,
        "created_at": row.created_at,
    }


@router.get("/sports-teacher/students")
def list_student_roster(
    keyword: str | None = None,
    college: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    _actor: User = Depends(business_admin),
    db: Session = Depends(get_db),
):
    filters = []
    if keyword and keyword.strip():
        term = f"%{keyword.strip()}%"
        filters.append(or_(StudentRoster.student_no.like(term), StudentRoster.name.like(term)))
    if college and college.strip():
        filters.append(StudentRoster.college == college.strip())
    stmt = select(StudentRoster)
    count_stmt = select(func.count(StudentRoster.id))
    for condition in filters:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    rows = list(db.scalars(stmt.order_by(StudentRoster.college, StudentRoster.class_name, StudentRoster.student_no).offset((page - 1) * page_size).limit(page_size)))
    return {"items": [_student_roster_dict(row) for row in rows], "total": db.scalar(count_stmt) or 0}


@router.post("/sports-teacher/students")
def create_student_roster(data: StudentRosterCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    values = {key: value.strip() for key, value in data.model_dump().items()}
    if values["gender"] not in {"男", "女"}:
        raise HTTPException(422, "性别必须选择男或女")
    if db.scalar(select(StudentRoster.id).where(StudentRoster.student_no == values["student_no"])):
        raise HTTPException(409, "该学号已存在于学生名单")
    row = StudentRoster(**values, activated=False)
    db.add(row)
    db.flush()
    audit(db, actor, "CREATE_STUDENT_ROSTER", "student_roster", row.id, after=_student_roster_dict(row))
    db.commit()
    return _student_roster_dict(row)


@router.put("/sports-teacher/students/{student_id}")
def update_student_roster(student_id: int, data: StudentRosterCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    row = db.get(StudentRoster, student_id)
    if not row:
        raise HTTPException(404, "学生资料不存在")
    values = {key: value.strip() for key, value in data.model_dump().items()}
    if values["gender"] not in {"男", "女"}:
        raise HTTPException(422, "性别必须选择男或女")
    duplicate = db.scalar(select(StudentRoster.id).where(StudentRoster.student_no == values["student_no"], StudentRoster.id != row.id))
    if duplicate:
        raise HTTPException(409, "该学号已存在于学生资料库")
    if row.user_id:
        user = db.get(User, row.user_id)
        if user and values["student_no"] != row.student_no:
            if db.scalar(select(User.id).where(User.username == values["student_no"], User.id != user.id)):
                raise HTTPException(409, "新学号已被其他账号使用")
            user.username = values["student_no"]
        if user:
            user.display_name = values["name"]
            user.department = values["college"]
    before = _student_roster_dict(row)
    for field, value in values.items():
        setattr(row, field, value)
    audit(db, actor, "UPDATE_STUDENT_ROSTER", "student_roster", row.id, before=before, after=_student_roster_dict(row))
    db.commit()
    return _student_roster_dict(row)


@router.delete("/sports-teacher/students/{student_id}")
def delete_student_roster(student_id: int, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    row = db.get(StudentRoster, student_id)
    if not row:
        raise HTTPException(404, "学生资料不存在")
    if row.user_id or row.activated:
        raise HTTPException(409, "该学生账号已激活，不能删除资料；可在账号管理中冻结账号")
    dependencies = {
        "参赛记录": db.scalar(select(func.count(Registration.id)).where(Registration.student_id == row.id)) or 0,
        "代表队成员记录": db.scalar(select(func.count(CollegeTeamMember.id)).where(CollegeTeamMember.student_id == row.id)) or 0,
        "跳绳阵容": db.scalar(select(func.count(RopeLineupMember.id)).where(RopeLineupMember.student_id == row.id)) or 0,
        "淘汰赛记录": db.scalar(
            select(func.count(TournamentMatch.id)).where(
                or_(
                    TournamentMatch.home_student_id == row.id,
                    TournamentMatch.away_student_id == row.id,
                    TournamentMatch.winner_student_id == row.id,
                    TournamentMatch.loser_student_id == row.id,
                )
            )
        ) or 0,
    }
    if any(dependencies.values()):
        detail = "、".join(f"{name}{count}项" for name, count in dependencies.items() if count)
        raise HTTPException(409, f"该学生仍有{detail}，请先处理关联数据")
    before = _student_roster_dict(row)
    db.delete(row)
    audit(db, actor, "DELETE_STUDENT_ROSTER", "student_roster", student_id, before=before)
    db.commit()
    return {"message": "学生资料已删除"}


@router.get("/sports-teacher/students/template")
def download_student_roster_template(_actor: User = Depends(business_admin)):
    candidates = [
        PROJECT_ROOT / "outputs" / "sports-meet" / "学生参赛名单导入模板.xlsx",
        Path(__file__).resolve().parents[2] / "outputs" / "sports-meet" / "学生参赛名单导入模板.xlsx",
    ]
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "outputs" / "sports-meet" / "学生参赛名单导入模板.xlsx")
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "outputs" / "sports-meet" / "学生参赛名单导入模板.xlsx")
        candidates.append(exe_dir / "_internal" / "outputs" / "sports-meet" / "学生参赛名单导入模板.xlsx")

    for candidate in candidates:
        if candidate.exists():
            return FileResponse(
                candidate,
                filename=candidate.name,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # 动态生成标准模板作为托底保障
    import io
    from fastapi.responses import Response

    wb = Workbook()
    ws = wb.active
    ws.title = "学生名单"
    ws.append(["学号*", "姓名*", "性别*", "学院*", "专业*", "班级*"])
    ws.append(["2026001001", "张三", "男", "计算机与信息工程学院", "软件工程", "2601"])
    ws.append(["2026001002", "李四", "女", "经济与管理学院", "国际贸易", "2602"])
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''%E5%AD%A6%E7%94%9F%E5%8F%82%E8%B5%9B%E5%90%8D%E5%8D%95%E5%AF%BC%E5%85%A5%E6%A8%A1%E6%9D%BF.xlsx"
        },
    )


@router.post("/sports-teacher/students/import")
def import_student_roster(file: UploadFile = File(...), actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(422, "请上传 .xlsx 格式的学生名单")
    try:
        workbook = load_workbook(file.file, read_only=True, data_only=True)
        sheet = workbook["学生名单"] if "学生名单" in workbook.sheetnames else workbook.active
        header_row = None
        expected = ["学号", "姓名", "性别", "学院", "专业", "班级"]
        for row_index, row in enumerate(sheet.iter_rows(min_row=1, max_row=10, max_col=6, values_only=True), 1):
            values = [str(value or "").replace("*", "").strip() for value in row]
            if values == expected:
                header_row = row_index
                break
        if not header_row:
            raise HTTPException(422, "未找到标准表头，请使用系统提供的导入模板")
        created = 0
        skipped = 0
        errors: list[str] = []
        seen: set[str] = set()
        for row_index, row in enumerate(sheet.iter_rows(min_row=header_row + 1, max_col=6, values_only=True), header_row + 1):
            values = [str(value).strip() if value is not None else "" for value in row]
            if not any(values):
                continue
            student_no, name, gender, college, major, class_name = values
            if not all(values):
                errors.append(f"第 {row_index} 行存在空白必填字段")
                continue
            if len(student_no) < 6 or gender not in {"男", "女"}:
                errors.append(f"第 {row_index} 行学号或性别格式不正确")
                continue
            if student_no in seen or db.scalar(select(StudentRoster.id).where(StudentRoster.student_no == student_no)):
                skipped += 1
                continue
            seen.add(student_no)
            db.add(StudentRoster(student_no=student_no, name=name, gender=gender, college=college, major=major, class_name=class_name, activated=False))
            created += 1
        if errors:
            db.rollback()
            raise HTTPException(422, {"message": "名单校验失败，未导入任何数据", "errors": errors[:30]})
        audit(db, actor, "IMPORT_STUDENT_ROSTER", "student_roster", file.filename, after={"created": created, "skipped": skipped})
        db.commit()
        return {"message": "学生名单导入完成", "created": created, "skipped": skipped}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(422, "Excel 文件无法读取或内容格式损坏，请使用系统模板重新填写") from exc
    finally:
        file.file.close()

def _college_team_dict(db: Session, row: CollegeTeam) -> dict:
    meet = db.get(SportsMeet, row.meet_id)
    event = db.get(Event, row.event_id) if row.event_id else None
    members = list(db.scalars(select(CollegeTeamMember).where(CollegeTeamMember.team_id == row.id)))
    male_count = 0
    female_count = 0
    for m in members:
        s = db.get(StudentRoster, m.student_id)
        if s:
            if s.gender == "男":
                male_count += 1
            elif s.gender == "女":
                female_count += 1
    return {
        "id": row.id,
        "meet_id": row.meet_id,
        "meet_name": f"{meet.name} {meet.edition}" if meet else "",
        "event_id": row.event_id,
        "event_name": event.name if event else "全能/通用代表队",
        "event_type": event.event_type if event else None,
        "college": row.college,
        "team_name": row.team_name,
        "leader_name": row.leader_name,
        "leader_phone": row.leader_phone,
        "notes": row.notes,
        "created_at": row.created_at,
        "total_members": len(members),
        "male_count": male_count,
        "female_count": female_count,
    }


@router.get("/sports-teacher/college-teams")
def list_college_teams(meet_id: int | None = None, event_id: int | None = None, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    stmt = select(CollegeTeam)
    if meet_id:
        stmt = stmt.where(CollegeTeam.meet_id == meet_id)
    if event_id:
        stmt = stmt.where(or_(CollegeTeam.event_id == event_id, CollegeTeam.event_id.is_(None)))
    rows = list(db.scalars(stmt.order_by(CollegeTeam.meet_id.desc(), CollegeTeam.event_id, CollegeTeam.college)))
    return [_college_team_dict(db, row) for row in rows]


@router.post("/sports-teacher/college-teams")
def create_college_team(data: CollegeTeamCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    meet = db.get(SportsMeet, data.meet_id)
    if not meet:
        raise HTTPException(404, "运动会不存在")
    college = data.college.strip()
    event_id = data.event_id if data.event_id else None
    event = db.get(Event, event_id) if event_id else None
    if event_id and (not event or event.meet_id != data.meet_id):
        raise HTTPException(422, "专项比赛项目不属于所选运动会")
    default_suffix = f"{event.name}代表队" if event else "代表队"
    team_name = (data.team_name or "").strip() or f"{college}{default_suffix}"

    duplicate = db.scalar(select(CollegeTeam.id).where(
        CollegeTeam.meet_id == data.meet_id,
        CollegeTeam.college == college,
        CollegeTeam.team_name == team_name,
    ))
    if duplicate:
        raise HTTPException(409, f"本届运动会中该学院已存在代表队【{team_name}】")

    row = CollegeTeam(
        meet_id=data.meet_id,
        event_id=event_id,
        college=college,
        team_name=team_name,
        leader_name=(data.leader_name or "").strip() or None,
        leader_phone=(data.leader_phone or "").strip() or None,
        notes=(data.notes or "").strip() or None,
        created_by_id=actor.id,
    )
    db.add(row)
    db.flush()
    audit(db, actor, "CREATE_COLLEGE_TEAM", "college_team", row.id, after=_college_team_dict(db, row))
    db.commit()
    return _college_team_dict(db, row)


@router.put("/sports-teacher/college-teams/{team_id}")
def update_college_team(team_id: int, data: CollegeTeamCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    row = db.get(CollegeTeam, team_id)
    if not row:
        raise HTTPException(404, "学院代表队不存在")
    if not db.get(SportsMeet, data.meet_id):
        raise HTTPException(404, "运动会不存在")
    college = data.college.strip()
    event_id = data.event_id if data.event_id else None
    event = db.get(Event, event_id) if event_id else None
    if event_id and (not event or event.meet_id != data.meet_id):
        raise HTTPException(422, "专项比赛项目不属于所选运动会")
    default_suffix = f"{event.name}代表队" if event else "代表队"
    team_name = (data.team_name or "").strip() or f"{college}{default_suffix}"

    duplicate = db.scalar(select(CollegeTeam.id).where(
        CollegeTeam.meet_id == data.meet_id,
        CollegeTeam.college == college,
        CollegeTeam.team_name == team_name,
        CollegeTeam.id != row.id,
    ))
    if duplicate:
        raise HTTPException(409, f"本届运动会中该学院已存在代表队【{team_name}】")
    if data.meet_id != row.meet_id and db.scalar(select(Registration.id).where(Registration.college_team_id == row.id).limit(1)):
        raise HTTPException(409, "该代表队已有参赛记录，不能更换所属运动会")

    before = _college_team_dict(db, row)
    row.meet_id = data.meet_id
    row.event_id = event_id
    row.college = college
    row.team_name = team_name
    row.leader_name = (data.leader_name or "").strip() or None
    row.leader_phone = (data.leader_phone or "").strip() or None
    row.notes = (data.notes or "").strip() or None
    audit(db, actor, "UPDATE_COLLEGE_TEAM", "college_team", row.id, before=before, after=_college_team_dict(db, row))
    db.commit()
    return _college_team_dict(db, row)


@router.delete("/sports-teacher/college-teams/{team_id}")
def delete_college_team(team_id: int, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    row = db.get(CollegeTeam, team_id)
    if not row:
        raise HTTPException(404, "学院代表队不存在")
    dependencies = {
        "参赛记录": db.scalar(select(func.count(Registration.id)).where(Registration.college_team_id == row.id)) or 0,
        "队员": db.scalar(select(func.count(CollegeTeamMember.id)).where(CollegeTeamMember.team_id == row.id)) or 0,
        "跳绳阵容": db.scalar(select(func.count(RopeLineupMember.id)).where(RopeLineupMember.college_team_id == row.id)) or 0,
        "淘汰赛记录": db.scalar(
            select(func.count(TournamentMatch.id)).where(
                or_(
                    TournamentMatch.home_team_id == row.id,
                    TournamentMatch.away_team_id == row.id,
                    TournamentMatch.winner_team_id == row.id,
                    TournamentMatch.loser_team_id == row.id,
                    TournamentMatch.forfeit_team_id == row.id,
                )
            )
        ) or 0,
    }
    if any(dependencies.values()):
        detail = "、".join(f"{name}{count}项" for name, count in dependencies.items() if count)
        raise HTTPException(409, f"该代表队仍有{detail}，请先处理关联数据")
    before = _college_team_dict(db, row)
    db.delete(row)
    audit(db, actor, "DELETE_COLLEGE_TEAM", "college_team", team_id, before=before)
    db.commit()
    return {"message": "学院代表队已删除"}


@router.post("/sports-teacher/college-teams/generate")
def generate_college_teams(data: CollegeTeamGenerate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    if not db.get(SportsMeet, data.meet_id):
        raise HTTPException(404, "运动会不存在")
    event_id = data.event_id if data.event_id else None
    event = db.get(Event, event_id) if event_id else None
    if event_id and (not event or event.meet_id != data.meet_id):
        raise HTTPException(422, "专项比赛项目不属于所选运动会")
    suffix = f"{event.name}代表队" if event else "代表队"
    colleges = [str(value).strip() for value in db.scalars(select(StudentRoster.college).distinct().order_by(StudentRoster.college)) if str(value).strip()]
    existing = set(db.scalars(select(CollegeTeam.team_name).where(CollegeTeam.meet_id == data.meet_id, CollegeTeam.event_id == event_id)))
    created = 0
    for college in colleges:
        name = f"{college}{suffix}"
        if name in existing:
            continue
        db.add(CollegeTeam(meet_id=data.meet_id, event_id=event_id, college=college, team_name=name, created_by_id=actor.id))
        created += 1
    db.flush()
    audit(db, actor, "GENERATE_COLLEGE_TEAMS", "college_team", str(data.meet_id), after={"created": created, "event_id": event_id})
    db.commit()
    return {"message": f"成功为【{event.name if event else '本届运动会'}】批量生成 {created} 支学院代表队！", "created": created}


# ------------------------------------------------------------------------------
# 👥 学院代表队队员阵容管理 (Team Squad & Gender Constraints)
# ------------------------------------------------------------------------------

def _team_member_dict(db: Session, row: CollegeTeamMember) -> dict:
    student = db.get(StudentRoster, row.student_id)
    return {
        "id": row.id,
        "team_id": row.team_id,
        "student_id": row.student_id,
        "student_no": student.student_no if student else "",
        "name": student.name if student else "",
        "gender": student.gender if student else "",
        "college": student.college if student else "",
        "major": student.major if student else "",
        "class_name": student.class_name if student else "",
        "role_title": row.role_title or "队员",
        "is_starter": row.is_starter,
        "created_at": row.created_at,
    }


@router.get("/sports-teacher/college-teams/{team_id}/members")
def list_college_team_members(team_id: int, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    team = db.get(CollegeTeam, team_id)
    if not team:
        raise HTTPException(404, "学院代表队不存在")
    rows = list(db.scalars(select(CollegeTeamMember).where(CollegeTeamMember.team_id == team_id).order_by(CollegeTeamMember.id)))
    members = [_team_member_dict(db, r) for r in rows]
    male_count = sum(1 for m in members if m["gender"] == "男")
    female_count = sum(1 for m in members if m["gender"] == "女")
    return {
        "team": _college_team_dict(db, team),
        "members": members,
        "total_members": len(members),
        "male_count": male_count,
        "female_count": female_count,
        "female_rule_passed": female_count >= 2,
        "female_rule_tip": "女生人数已达标（不低于两人）" if female_count >= 2 else f"当前女生 {female_count} 人，依据竞赛规程要求女生不能低于两人！",
    }


@router.post("/sports-teacher/college-teams/{team_id}/members")
def add_college_team_member(team_id: int, data: CollegeTeamMemberCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    team = db.get(CollegeTeam, team_id)
    if not team:
        raise HTTPException(404, "学院代表队不存在")
    student = db.get(StudentRoster, data.student_id)
    if not student:
        raise HTTPException(404, "学生不存在")
    if student.college != team.college:
        raise HTTPException(400, f"该学生所属学院（{student.college}）与代表队学院（{team.college}）不一致")
    if db.scalar(select(CollegeTeamMember.id).where(CollegeTeamMember.team_id == team_id, CollegeTeamMember.student_id == data.student_id)):
        raise HTTPException(409, "该队员已在代表队名单中")

    member = CollegeTeamMember(
        team_id=team_id,
        student_id=data.student_id,
        role_title=(data.role_title or "队员").strip(),
        is_starter=data.is_starter,
    )
    db.add(member)
    db.flush()
    audit(db, actor, "ADD_TEAM_MEMBER", "college_team_member", member.id, after=_team_member_dict(db, member))
    db.commit()
    return _team_member_dict(db, member)


@router.post("/sports-teacher/college-teams/{team_id}/members/batch")
def add_college_team_members_batch(team_id: int, data: CollegeTeamMemberBatchCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    team = db.get(CollegeTeam, team_id)
    if not team:
        raise HTTPException(404, "学院代表队不存在")
    added = 0
    for sid in data.student_ids:
        student = db.get(StudentRoster, sid)
        if not student or student.college != team.college:
            continue
        if db.scalar(select(CollegeTeamMember.id).where(CollegeTeamMember.team_id == team_id, CollegeTeamMember.student_id == sid)):
            continue
        db.add(CollegeTeamMember(team_id=team_id, student_id=sid, role_title=(data.role_title or "队员").strip()))
        added += 1
    db.flush()
    audit(db, actor, "BATCH_ADD_TEAM_MEMBERS", "college_team", str(team_id), after={"added": added})
    db.commit()
    return {"message": f"成功为【{team.team_name}】添加 {added} 名队员！", "added": added}


@router.delete("/sports-teacher/college-teams/{team_id}/members/{member_id}")
def delete_college_team_member(team_id: int, member_id: int, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    member = db.get(CollegeTeamMember, member_id)
    if not member or member.team_id != team_id:
        raise HTTPException(404, "队员记录不存在")
    before = _team_member_dict(db, member)
    db.delete(member)
    audit(db, actor, "DELETE_TEAM_MEMBER", "college_team_member", member_id, before=before)
    db.commit()
    return {"message": "队员已从代表队名单中移除"}


@router.put("/sports-teacher/college-teams/{team_id}/members/{member_id}")
def update_college_team_member(team_id: int, member_id: int, data: CollegeTeamMemberUpdate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    member = db.get(CollegeTeamMember, member_id)
    if not member or member.team_id != team_id:
        raise HTTPException(404, "队员记录不存在")
    before = _team_member_dict(db, member)
    if data.role_title is not None:
        member.role_title = data.role_title.strip()
    if data.is_starter is not None:
        member.is_starter = data.is_starter
    audit(db, actor, "UPDATE_TEAM_MEMBER", "college_team_member", member_id, before=before, after=_team_member_dict(db, member))
    db.commit()
    return _team_member_dict(db, member)


@router.get("/sports-teacher/college-teams/{team_id}/available-candidates")
def list_available_team_candidates(team_id: int, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    team = db.get(CollegeTeam, team_id)
    if not team:
        raise HTTPException(404, "学院代表队不存在")
    existing_sids = set(db.scalars(select(CollegeTeamMember.student_id).where(CollegeTeamMember.team_id == team_id)))
    candidates = list(
        db.scalars(
            select(StudentRoster)
            .where(StudentRoster.college == team.college)
            .order_by(StudentRoster.gender.desc(), StudentRoster.student_no)
        )
    )
    return [
        {
            "id": s.id,
            "student_no": s.student_no,
            "name": s.name,
            "gender": s.gender,
            "college": s.college,
            "major": s.major,
            "class_name": s.class_name,
            "activated": s.activated,
        }
        for s in candidates
        if s.id not in existing_sids
    ]


@router.get("/sports-teacher/events")
def teacher_events(meet_id: int | None = None, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    stmt = select(Event)
    if meet_id:
        stmt = stmt.where(Event.meet_id == meet_id)
    return list(db.scalars(stmt.order_by(Event.id)))


@router.post("/sports-teacher/events")
def create_event(data: EventCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    if not db.get(SportsMeet, data.meet_id):
        raise HTTPException(404, "运动会不存在")
    duplicate = db.scalar(select(Event.id).where(Event.meet_id == data.meet_id, Event.code == data.code))
    if duplicate:
        raise HTTPException(409, "该运动会中项目编号已存在")
    event = Event(**data.model_dump())
    try:
        db.add(event)
        db.flush()
        sync_event_rounds(db, event_id=event.id)
        audit(db, actor, "CREATE_EVENT", "event", event.id, after=data.model_dump(mode="json"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "该运动会中项目编号已存在") from exc
    return event


@router.put("/sports-teacher/events/{event_id}")
def update_event(event_id: int, data: EventCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    if not db.get(SportsMeet, data.meet_id):
        raise HTTPException(404, "运动会不存在")
    duplicate = db.scalar(select(Event.id).where(Event.meet_id == data.meet_id, Event.code == data.code, Event.id != event.id))
    if duplicate:
        raise HTTPException(409, "该运动会中项目编号已存在")
    result_count = db.scalar(select(func.count(Result.id)).where(Result.event_id == event.id)) or 0
    protected_fields = ["meet_id", "event_type", "result_unit", "sort_direction", "gender_group"]
    changed_protected = [field for field in protected_fields if getattr(event, field) != getattr(data, field)]
    if result_count and changed_protected:
        raise HTTPException(409, f"项目已有成绩，不能修改：{'、'.join(changed_protected)}")
    if data.meet_id != event.meet_id and db.scalar(select(Registration.id).where(Registration.event_id == event.id).limit(1)):
        raise HTTPException(409, "项目已有参赛名单，不能更换所属运动会")
    before = {field: getattr(event, field) for field in data.model_dump()}
    for field, value in data.model_dump().items():
        setattr(event, field, value)
    sync_event_rounds(db, event_id=event.id)
    audit(db, actor, "UPDATE_EVENT", "event", event.id, before=before, after=data.model_dump(mode="json"))
    db.commit()
    return event


@router.delete("/sports-teacher/events/{event_id}")
def delete_event(event_id: int, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    dependencies = {
        "参赛记录": db.scalar(select(func.count(Registration.id)).where(Registration.event_id == event.id)) or 0,
        "成绩": db.scalar(select(func.count(Result.id)).where(Result.event_id == event.id)) or 0,
        "赛程": db.scalar(select(func.count(EventSchedule.id)).where(EventSchedule.event_id == event.id)) or 0,
        "权限": db.scalar(select(func.count(EventAdminPermission.id)).where(EventAdminPermission.event_id == event.id)) or 0,
        "计分绑定": db.scalar(select(func.count(ScoringModelBinding.id)).where(ScoringModelBinding.event_id == event.id)) or 0,
        "跳绳阵容": db.scalar(select(func.count(RopeLineupMember.id)).where(RopeLineupMember.event_id == event.id)) or 0,
        "专项代表队": db.scalar(select(func.count(CollegeTeam.id)).where(CollegeTeam.event_id == event.id)) or 0,
        "赛制比赛记录": db.scalar(select(func.count(TournamentMatch.id)).where(TournamentMatch.event_id == event.id)) or 0,
    }
    if any(dependencies.values()):
        detail = "、".join(f"{name}{count}项" for name, count in dependencies.items() if count)
        raise HTTPException(409, f"该项目仍有{detail}，请先处理关联数据")
    for round_row in db.scalars(select(EventRound).where(EventRound.event_id == event.id)):
        db.delete(round_row)
    # EventRound 没有配置 ORM relationship；先显式落盘子表删除，避免同一次
    # flush 中 SQLite 先删除 events 而触发外键约束。
    db.flush()
    before = {"code": event.code, "name": event.name}
    db.delete(event)
    audit(db, actor, "DELETE_EVENT", "event", event_id, before=before)
    db.commit()
    return {"message": "比赛项目已删除"}


def _event_registration_dict(db: Session, row: Registration) -> dict:
    participant = participant_for_registration(db, row)
    round_row = db.get(EventRound, row.round_id)
    return {
        "id": row.id,
        "event_id": row.event_id,
        "round_id": row.round_id,
        "round_name": round_row.name if round_row else "",
        "round_stage": round_row.stage if round_row else "",
        "bib_no": row.bib_no,
        "heat": row.heat,
        "lane": row.lane,
        "status": row.status,
        "participant": participant,
        "result_count": db.scalar(select(func.count(Result.id)).where(Result.registration_id == row.id)) or 0,
    }


@router.get("/sports-teacher/event-registrations")
def list_event_registrations(event_id: int, round_id: int | None = None, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    """Return the actual entry list for one event and eligible unregistered candidates."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    if sync_event_rounds(db, event_id=event.id):
        db.commit()
    rounds = list(db.scalars(select(EventRound).where(EventRound.event_id == event.id).order_by(EventRound.sequence)))
    if not rounds:
        round_row = EventRound(event_id=event.id, name="决赛", stage=event.stage or "FINAL", sequence=1, qualification_count=0)
        db.add(round_row)
        db.commit()
        rounds = [round_row]
    selected_round_id = round_id or (rounds[0].id if rounds else None)
    if not selected_round_id or not any(row.id == selected_round_id for row in rounds):
        selected_round_id = rounds[0].id
    team_event = event.event_type in {"TEAM", "RELAY"}
    registrations = list(db.scalars(select(Registration).where(Registration.event_id == event.id, Registration.round_id == selected_round_id).order_by(Registration.heat, Registration.lane, Registration.id)))
    if team_event:
        registered_ids = {row.college_team_id for row in registrations if row.college_team_id is not None}
        candidates = [
            {
                "id": row.id,
                "participant_type": "TEAM",
                "name": row.team_name,
                "college": row.college,
                "detail": row.leader_name or "未填写领队",
            }
            for row in db.scalars(
                select(CollegeTeam)
                .where(CollegeTeam.meet_id == event.meet_id, or_(CollegeTeam.event_id == event.id, CollegeTeam.event_id.is_(None)))
                .order_by(CollegeTeam.college)
            )
            if row.id not in registered_ids
        ]
    else:
        registered_ids = {row.student_id for row in registrations if row.student_id is not None}
        student_stmt = select(StudentRoster)
        if event.gender_group == "MALE":
            student_stmt = student_stmt.where(StudentRoster.gender == "男")
        elif event.gender_group == "FEMALE":
            student_stmt = student_stmt.where(StudentRoster.gender == "女")
        candidates = [
            {
                "id": row.id,
                "participant_type": "STUDENT",
                "student_no": row.student_no,
                "name": row.name,
                "gender": row.gender,
                "college": row.college,
                "detail": f"{row.major} · {row.class_name}",
                "activated": row.activated,
            }
            for row in db.scalars(student_stmt.order_by(StudentRoster.college, StudentRoster.class_name, StudentRoster.student_no))
            if row.id not in registered_ids
        ]
    meet = db.get(SportsMeet, event.meet_id)
    return {
        "event": {
            "id": event.id,
            "name": event.name,
            "code": event.code,
            "meet_id": event.meet_id,
            "meet_name": f"{meet.name} {meet.edition}" if meet else "",
            "event_type": event.event_type,
            "gender_group": event.gender_group,
        },
        "rounds": rounds,
        "selected_round_id": selected_round_id,
        "items": [_event_registration_dict(db, row) for row in registrations],
        "candidates": candidates,
        "inactive_students_allowed": True,
    }


@router.post("/sports-teacher/event-registrations/batch")
def add_event_registrations(data: RegistrationBatchCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    event = db.get(Event, data.event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    participant_ids = list(dict.fromkeys(data.participant_ids))
    if not participant_ids:
        raise HTTPException(422, "请至少选择一名参赛者")
    team_event = event.event_type in {"TEAM", "RELAY"}
    round_row = db.get(EventRound, data.round_id)
    if not round_row or round_row.event_id != event.id:
        raise HTTPException(422, "比赛轮次不属于该项目")
    if team_event:
        participants = list(db.scalars(select(CollegeTeam).where(CollegeTeam.id.in_(participant_ids))))
        if len(participants) != len(participant_ids):
            raise HTTPException(422, "部分学院代表队不存在")
        if any(row.meet_id != event.meet_id for row in participants):
            raise HTTPException(422, "学院代表队不属于该项目所在运动会")
        if any(row.event_id not in {None, event.id} for row in participants):
            raise HTTPException(422, "专项学院代表队不属于当前比赛项目")
        existing = set(db.scalars(select(Registration.college_team_id).where(Registration.event_id == event.id, Registration.round_id == round_row.id, Registration.college_team_id.in_(participant_ids))))
    else:
        participants = list(db.scalars(select(StudentRoster).where(StudentRoster.id.in_(participant_ids))))
        if len(participants) != len(participant_ids):
            raise HTTPException(422, "部分学生不存在")
        expected_gender = {"MALE": "男", "FEMALE": "女"}.get(event.gender_group)
        mismatched = [row.name for row in participants if expected_gender and row.gender != expected_gender]
        if mismatched:
            raise HTTPException(422, f"以下学生与项目组别不符：{'、'.join(mismatched[:8])}")
        existing = set(db.scalars(select(Registration.student_id).where(Registration.event_id == event.id, Registration.round_id == round_row.id, Registration.student_id.in_(participant_ids))))
    created = 0
    skipped = 0
    for participant in participants:
        if participant.id in existing:
            skipped += 1
            continue
        values = {
            "event_id": event.id,
            "round_id": round_row.id,
            "heat": (data.heat or "").strip() or None,
            "status": data.status,
        }
        if team_event:
            values.update(college_team_id=participant.id, bib_no=f"T{event.id:03d}{participant.id:03d}")
        else:
            values.update(student_id=participant.id, bib_no=f"P{event.id:03d}{participant.id:04d}")
        db.add(Registration(**values))
        created += 1
    audit(db, actor, "BATCH_CREATE_EVENT_REGISTRATIONS", "event", event.id, after={"round_id": round_row.id, "round_name": round_row.name, "created": created, "skipped": skipped, "participant_ids": participant_ids})
    db.commit()
    return {"message": "项目参赛名单已更新", "created": created, "skipped": skipped}


@router.put("/sports-teacher/event-registrations/{registration_id}")
def update_event_registration(registration_id: int, data: RegistrationUpdate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    row = db.get(Registration, registration_id)
    if not row:
        raise HTTPException(404, "参赛记录不存在")
    before = _event_registration_dict(db, row)
    for field, value in data.model_dump().items():
        setattr(row, field, value.strip() or None if isinstance(value, str) and field != "status" else value)
    audit(db, actor, "UPDATE_EVENT_REGISTRATION", "registration", row.id, before=before, after=_event_registration_dict(db, row))
    db.commit()
    return _event_registration_dict(db, row)


@router.delete("/sports-teacher/event-registrations/{registration_id}")
def delete_event_registration(registration_id: int, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    row = db.get(Registration, registration_id)
    if not row:
        raise HTTPException(404, "参赛记录不存在")
    if db.scalar(select(Result.id).where(Result.registration_id == row.id).limit(1)):
        raise HTTPException(409, "该参赛者已有成绩，不能从项目名单中移除")
    before = _event_registration_dict(db, row)
    event_id = row.event_id
    db.delete(row)
    audit(db, actor, "DELETE_EVENT_REGISTRATION", "registration", registration_id, before=before)
    db.commit()
    return {"message": "已从项目参赛名单移除", "event_id": event_id}


@router.post("/sports-teacher/event-registrations/seed")
def seed_event_registrations(data: RegistrationSeedRequest, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    event = db.get(Event, data.event_id)
    round_row = db.get(EventRound, data.round_id)
    if not event or not round_row or round_row.event_id != data.event_id:
        raise HTTPException(422, "比赛项目或轮次不匹配")
    rows = list(db.scalars(
        select(Registration)
        .where(
            Registration.event_id == data.event_id,
            Registration.round_id == data.round_id,
            Registration.status.notin_(["WITHDRAWN", "ABSENT"]),
        )
        .order_by(Registration.id)
    ))
    if not rows:
        raise HTTPException(422, "当前轮次没有可分组的参赛名单")

    # 道次从中间向两侧展开，符合径赛常见排道习惯；超过 8 道时继续顺序补齐。
    center_left = (data.lanes_per_heat + 1) // 2
    preferred_lanes: list[int] = []
    for offset in range(data.lanes_per_heat):
        candidate = center_left + ((offset + 1) // 2 if offset % 2 else -(offset // 2))
        if 1 <= candidate <= data.lanes_per_heat and candidate not in preferred_lanes:
            preferred_lanes.append(candidate)
    preferred_lanes.extend(lane for lane in range(1, data.lanes_per_heat + 1) if lane not in preferred_lanes)
    for index, row in enumerate(rows):
        row.heat = f"第{index // data.lanes_per_heat + 1}组"
        row.lane = str(preferred_lanes[index % data.lanes_per_heat])
        if row.status == "ALTERNATE":
            row.lane = None
    audit(db, actor, "AUTO_SEED_REGISTRATIONS", "event_round", round_row.id, after={"event_id": event.id, "round_name": round_row.name, "participants": len(rows), "lanes_per_heat": data.lanes_per_heat})
    db.commit()
    return {"message": f"已为{len(rows)}名参赛者自动分组排道", "participants": len(rows)}


@router.post("/sports-teacher/event-registrations/advance")
def advance_event_registrations(data: RegistrationAdvanceRequest, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    event = db.get(Event, data.event_id)
    from_round = db.get(EventRound, data.from_round_id)
    to_round = db.get(EventRound, data.to_round_id)
    if not event or not from_round or not to_round or from_round.event_id != event.id or to_round.event_id != event.id:
        raise HTTPException(422, "比赛项目或轮次不匹配")
    if to_round.sequence <= from_round.sequence:
        raise HTTPException(422, "目标轮次必须晚于当前轮次")
    ranked = list(db.scalars(
        select(Result)
        .where(
            Result.event_id == event.id,
            Result.round_id == from_round.id,
            Result.published_at.is_not(None),
            Result.published_rank.is_not(None),
            Result.published_competition_status == "NORMAL",
        )
        .order_by(Result.published_rank, Result.id)
    ))
    if len(ranked) < data.count:
        raise HTTPException(422, f"当前仅有{len(ranked)}条已发布有效成绩，不足以生成{data.count}个晋级名额")
    selected = ranked[: data.count + data.alternates]
    created = 0
    skipped = 0
    for index, result in enumerate(selected):
        source = db.get(Registration, result.registration_id)
        participant_filter = Registration.college_team_id == source.college_team_id if source.college_team_id is not None else Registration.student_id == source.student_id
        existing = db.scalar(select(Registration).where(Registration.event_id == event.id, Registration.round_id == to_round.id, participant_filter))
        if existing:
            skipped += 1
            continue
        target = Registration(
            event_id=event.id,
            round_id=to_round.id,
            student_id=source.student_id,
            college_team_id=source.college_team_id,
            bib_no=source.bib_no,
            status="REGISTERED" if index < data.count else "ALTERNATE",
        )
        db.add(target)
        qualification = db.scalar(select(QualificationRecord).where(QualificationRecord.registration_id == source.id, QualificationRecord.from_round_id == from_round.id))
        if not qualification:
            qualification = QualificationRecord(registration_id=source.id, from_round_id=from_round.id)
            db.add(qualification)
        qualification.next_round_id = to_round.id
        qualification.status = "QUALIFIED" if index < data.count else "ALTERNATE"
        qualification.decided_by_id = actor.id
        qualification.decided_at = utcnow()
        created += 1
    audit(db, actor, "GENERATE_NEXT_ROUND_ROSTER", "event_round", to_round.id, after={"from_round": from_round.name, "to_round": to_round.name, "qualified": data.count, "alternates": data.alternates, "created": created, "skipped": skipped})
    db.commit()
    return {"message": f"已生成{to_round.name}名单", "created": created, "skipped": skipped}


@router.get("/sports-teacher/event-registrations/export")
def export_event_registrations(event_id: int, round_id: int, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    round_row = db.get(EventRound, round_id)
    if not event or not round_row or round_row.event_id != event.id:
        raise HTTPException(404, "比赛项目或轮次不存在")
    rows = list(db.scalars(select(Registration).where(Registration.event_id == event.id, Registration.round_id == round_row.id).order_by(Registration.heat, Registration.lane, Registration.id)))
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "分组表"
    sheet.append(["项目", "轮次", "组次", "道次", "号码", "学号", "姓名/集体", "学院", "班级", "参赛状态"])
    status_text = {"REGISTERED": "已报名", "CHECKED_IN": "已检录", "ALTERNATE": "候补", "ABSENT": "缺席", "WITHDRAWN": "退赛"}
    for row in rows:
        participant = participant_for_registration(db, row)
        sheet.append([event.name, round_row.name, row.heat or "", row.lane or "", row.bib_no or "", participant.get("student_no", ""), participant.get("name", ""), participant.get("college", ""), participant.get("class_name", ""), status_text.get(row.status, row.status)])
    for column, width in {"A": 20, "B": 10, "C": 10, "D": 8, "E": 14, "F": 16, "G": 22, "H": 22, "I": 18, "J": 12}.items():
        sheet.column_dimensions[column].width = width
    export_dir = Path(settings.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    file_path = export_dir / f"{event.code}_{round_row.stage}_分组表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    workbook.save(file_path)
    audit(db, actor, "EXPORT_EVENT_ROSTER", "event_round", round_row.id, after={"event_id": event.id, "count": len(rows), "file": file_path.name})
    db.commit()
    return FileResponse(file_path, filename=file_path.name)


@router.get("/sports-teacher/permissions")
def list_permissions(_actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(EventAdminPermission).order_by(EventAdminPermission.event_id)))
    return [{"id": row.id, "user_id": row.user_id, "event_id": row.event_id, "can_schedule": row.can_schedule, "can_score": row.can_score, "can_review": row.can_review, "can_export": row.can_export} for row in rows]


@router.get("/sports-teacher/managers")
def list_event_managers(_actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(User).where(User.role.in_([Role.REFEREE, Role.SCORER, Role.REFEREE_SCORER])).order_by(User.id)))
    return [snapshot_user(row) for row in rows]


@router.put("/sports-teacher/permissions")
def upsert_permission(data: PermissionUpsert, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    target = db.get(User, data.user_id)
    if not target or target.role not in {Role.REFEREE, Role.SCORER, Role.REFEREE_SCORER}:
        raise HTTPException(422, "只能给裁判员或计分员分配项目权限")
    if not db.get(Event, data.event_id):
        raise HTTPException(404, "比赛项目不存在")
    row = db.scalar(select(EventAdminPermission).where(EventAdminPermission.user_id == data.user_id, EventAdminPermission.event_id == data.event_id))
    before = None
    if row:
        before = {field: getattr(row, field) for field in ["can_schedule", "can_score", "can_review", "can_export"]}
        for field, value in data.model_dump().items():
            setattr(row, field, value)
        row.assigned_by_id = actor.id
    else:
        row = EventAdminPermission(**data.model_dump(), assigned_by_id=actor.id)
        db.add(row)
    audit(db, actor, "UPSERT_EVENT_PERMISSION", "event_permission", f"{data.user_id}:{data.event_id}", before, data.model_dump())
    db.commit()
    return {"message": "项目权限已保存"}


@router.delete("/sports-teacher/permissions/{permission_id}")
def delete_permission(permission_id: int, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    row = db.get(EventAdminPermission, permission_id)
    if not row:
        raise HTTPException(404, "项目权限不存在")
    before = {"user_id": row.user_id, "event_id": row.event_id, "can_schedule": row.can_schedule, "can_score": row.can_score, "can_review": row.can_review, "can_export": row.can_export}
    db.delete(row)
    audit(db, actor, "DELETE_EVENT_PERMISSION", "event_permission", permission_id, before=before)
    db.commit()
    return {"message": "项目权限已删除"}


def _model_dict(db: Session, row: ScoringModel) -> dict:
    items = list(db.scalars(select(ScoringModelItem).where(ScoringModelItem.model_id == row.id).order_by(ScoringModelItem.place)))
    in_use = (db.scalar(select(func.count(ScoringModelBinding.id)).where(ScoringModelBinding.model_id == row.id)) or 0) + (db.scalar(select(func.count(Event.id)).where(Event.scoring_model_id == row.id)) or 0)
    return {"id": row.id, "name": row.name, "description": row.description, "status": row.status, "places": row.places, "points": [item.points for item in items], "individual_multiplier": row.individual_multiplier, "relay_multiplier": row.relay_multiplier, "team_multiplier": row.team_multiplier, "version": row.version, "locked": row.locked_by_published_results, "in_use": in_use > 0}


@router.get("/sports-teacher/scoring-models")
@router.get("/developer/scoring-models")
def list_scoring_models(_actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    return [_model_dict(db, row) for row in db.scalars(select(ScoringModel).order_by(ScoringModel.id))]


@router.post("/sports-teacher/scoring-models")
def create_scoring_model(data: ScoringModelCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    if len(data.points) != data.places:
        raise HTTPException(422, "积分数量必须与录取名次数量一致")
    row = ScoringModel(
        name=data.name, description=data.description, status=data.status, places=data.places,
        individual_multiplier=data.individual_multiplier, relay_multiplier=data.relay_multiplier,
        team_multiplier=data.team_multiplier, tie_rule="AVERAGE_OCCUPIED",
        non_finish_points={"DNS": 0, "DNF": 0, "DQ": 0, "NM": 0}, tiebreak_rules=["gold", "silver", "bronze"],
        created_by_id=actor.id, updated_by_id=actor.id,
    )
    db.add(row)
    db.flush()
    for place, points in enumerate(data.points, 1):
        db.add(ScoringModelItem(model_id=row.id, place=place, points=points))
    audit(db, actor, "CREATE_SCORING_MODEL", "scoring_model", row.id, after=data.model_dump(mode="json"))
    db.commit()
    return _model_dict(db, row)


@router.put("/sports-teacher/scoring-models/{model_id}")
def update_scoring_model(model_id: int, data: ScoringModelCreate, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    row = db.get(ScoringModel, model_id)
    if not row:
        raise HTTPException(404, "计分模型不存在")
    if row.locked_by_published_results:
        raise HTTPException(409, "模型已被已发布成绩锁定，请复制新版本后修改")
    if db.scalar(select(ScoringModelBinding.id).where(ScoringModelBinding.model_id == row.id).limit(1)) or db.scalar(select(Event.id).where(Event.scoring_model_id == row.id).limit(1)):
        raise HTTPException(409, "模型已绑定比赛项目，请复制新版本后修改")
    if len(data.points) != data.places:
        raise HTTPException(422, "积分数量必须与录取名次数量一致")
    before = _model_dict(db, row)
    row.name = data.name
    row.description = data.description
    row.status = data.status
    row.places = data.places
    row.individual_multiplier = data.individual_multiplier
    row.relay_multiplier = data.relay_multiplier
    row.team_multiplier = data.team_multiplier
    row.updated_by_id = actor.id
    row.version += 1
    for item in db.scalars(select(ScoringModelItem).where(ScoringModelItem.model_id == row.id)):
        db.delete(item)
    db.flush()
    for place, points in enumerate(data.points, 1):
        db.add(ScoringModelItem(model_id=row.id, place=place, points=points))
    db.flush()
    audit(db, actor, "UPDATE_SCORING_MODEL", "scoring_model", row.id, before=before, after=_model_dict(db, row))
    db.commit()
    return _model_dict(db, row)


@router.delete("/sports-teacher/scoring-models/{model_id}")
def delete_scoring_model(model_id: int, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    row = db.get(ScoringModel, model_id)
    if not row:
        raise HTTPException(404, "计分模型不存在")
    if row.locked_by_published_results:
        raise HTTPException(409, "模型已被已发布成绩锁定，不能删除")
    if db.scalar(select(ScoringModelBinding.id).where(ScoringModelBinding.model_id == row.id).limit(1)) or db.scalar(select(Event.id).where(Event.scoring_model_id == row.id).limit(1)):
        raise HTTPException(409, "模型正在被比赛项目使用，不能删除")
    if db.scalar(select(ScoringModel.id).where(ScoringModel.parent_id == row.id).limit(1)):
        raise HTTPException(409, "该模型已有复制版本，不能删除源版本")
    before = _model_dict(db, row)
    for item in db.scalars(select(ScoringModelItem).where(ScoringModelItem.model_id == row.id)):
        db.delete(item)
    db.flush()
    db.delete(row)
    audit(db, actor, "DELETE_SCORING_MODEL", "scoring_model", model_id, before=before)
    db.commit()
    return {"message": "计分模型已删除"}


@router.post("/sports-teacher/scoring-models/{model_id}/copy")
def copy_scoring_model(model_id: int, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    source = db.get(ScoringModel, model_id)
    if not source:
        raise HTTPException(404, "计分模型不存在")
    copy = ScoringModel(name=f"{source.name}（副本）", description=source.description, status="DRAFT", places=source.places, individual_multiplier=source.individual_multiplier, relay_multiplier=source.relay_multiplier, team_multiplier=source.team_multiplier, tie_rule=source.tie_rule, non_finish_points=source.non_finish_points, tiebreak_rules=source.tiebreak_rules, version=source.version + 1, parent_id=source.id, created_by_id=actor.id, updated_by_id=actor.id)
    db.add(copy)
    db.flush()
    for item in db.scalars(select(ScoringModelItem).where(ScoringModelItem.model_id == source.id)):
        db.add(ScoringModelItem(model_id=copy.id, place=item.place, points=item.points))
    audit(db, actor, "COPY_SCORING_MODEL", "scoring_model", copy.id, before={"source_id": source.id})
    db.commit()
    return _model_dict(db, copy)


@router.post("/sports-teacher/scoring-models/{model_id}/enable")
def enable_scoring_model(model_id: int, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    row = db.get(ScoringModel, model_id)
    if not row:
        raise HTTPException(404, "计分模型不存在")
    row.status = "ENABLED" if row.status != "ENABLED" else "DISABLED"
    audit(db, actor, "TOGGLE_SCORING_MODEL", "scoring_model", row.id, after={"status": row.status})
    db.commit()
    return {"status": row.status}


@router.post("/sports-teacher/scoring-models/{model_id}/bind")
def bind_scoring_model(model_id: int, data: ModelBindRequest, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    row = db.get(ScoringModel, model_id)
    if not row or row.status != "ENABLED":
        raise HTTPException(422, "只能绑定启用中的计分模型")
    snapshot = jsonable_encoder(_model_dict(db, row))
    binding = ScoringModelBinding(meet_id=data.meet_id, event_id=data.event_id, model_id=row.id, model_version=row.version, snapshot=snapshot, bound_by_id=actor.id)
    db.add(binding)
    if data.event_id:
        event = db.get(Event, data.event_id)
        if not event or event.meet_id != data.meet_id:
            raise HTTPException(422, "项目不属于该运动会")
        event.scoring_model_id = row.id
    audit(db, actor, "BIND_SCORING_MODEL", "scoring_model_binding", model_id, after=data.model_dump())
    db.commit()
    return {"message": "计分模型已绑定"}


@router.get("/admin/my-events")
def my_events(user: User = Depends(manager_only), db: Session = Depends(get_db)):
    if user.role in {Role.DEVELOPER, Role.SPORTS_TEACHER}:
        rows = list(db.scalars(select(Event).order_by(Event.id)))
        return [{"event": row, "permissions": {"can_schedule": True, "can_score": True, "can_review": True, "can_export": True}} for row in rows]
    permissions = list(db.scalars(select(EventAdminPermission).where(EventAdminPermission.user_id == user.id)))
    return [{"event": db.get(Event, row.event_id), "permissions": {"can_schedule": row.can_schedule, "can_score": row.can_score, "can_review": row.can_review, "can_export": row.can_export}} for row in permissions]


@router.get("/admin/schedules")
def admin_schedules(event_id: int | None = None, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    stmt = select(EventSchedule)
    if event_id:
        if user.role not in {Role.DEVELOPER, Role.SPORTS_TEACHER} and not has_event_permission(db, user, event_id, "can_schedule"):
            raise HTTPException(403, "没有该项目的赛程权限")
        stmt = stmt.where(EventSchedule.event_id == event_id)
    elif user.role not in {Role.DEVELOPER, Role.SPORTS_TEACHER}:
        ids = list(db.scalars(select(EventAdminPermission.event_id).where(EventAdminPermission.user_id == user.id)))
        stmt = stmt.where(EventSchedule.event_id.in_(ids))
    rows = list(db.scalars(stmt.order_by(EventSchedule.competition_at)))
    return [{
        "id": row.id,
        "event_id": row.event_id,
        "round_id": row.round_id,
        "round_name": db.get(EventRound, row.round_id).name if row.round_id and db.get(EventRound, row.round_id) else "全部轮次",
        "competition_at": row.competition_at,
        "check_in_at": row.check_in_at,
        "venue": row.venue,
        "heat": row.heat,
        "notes": row.notes,
        "status": row.status,
        "published": row.published,
    } for row in rows]


@router.post("/admin/schedules")
def save_schedule(data: ScheduleUpsert, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    if not db.get(Event, data.event_id):
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, data.event_id, "can_schedule")
    if data.check_in_at and data.check_in_at > data.competition_at:
        raise HTTPException(422, "检录时间不能晚于比赛时间")
    if data.round_id:
        round_row = db.get(EventRound, data.round_id)
        if not round_row or round_row.event_id != data.event_id:
            raise HTTPException(422, "比赛轮次不属于该项目")
    schedule = EventSchedule(**data.model_dump(), operator_id=user.id)
    db.add(schedule)
    db.flush()
    audit(db, user, "CREATE_SCHEDULE", "event_schedule", schedule.id, after=data.model_dump(mode="json"))
    db.commit()
    return schedule


@router.put("/admin/schedules/{schedule_id}")
def update_schedule(schedule_id: int, data: ScheduleUpsert, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    schedule = db.get(EventSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "赛程不存在")
    require_event_permission(db, user, schedule.event_id, "can_schedule")
    if not db.get(Event, data.event_id):
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, data.event_id, "can_schedule")
    if data.check_in_at and data.check_in_at > data.competition_at:
        raise HTTPException(422, "检录时间不能晚于比赛时间")
    if data.round_id:
        round_row = db.get(EventRound, data.round_id)
        if not round_row or round_row.event_id != data.event_id:
            raise HTTPException(422, "比赛轮次不属于该项目")
    before = {field: getattr(schedule, field) for field in data.model_dump().keys()}
    for field, value in data.model_dump().items():
        setattr(schedule, field, value)
    schedule.operator_id = user.id
    audit(db, user, "UPDATE_SCHEDULE", "event_schedule", schedule.id, before=jsonable_encoder(before), after=data.model_dump(mode="json"))
    db.commit()
    return schedule


@router.delete("/admin/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    schedule = db.get(EventSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "赛程不存在")
    require_event_permission(db, user, schedule.event_id, "can_schedule")
    before = {"event_id": schedule.event_id, "round_id": schedule.round_id, "competition_at": schedule.competition_at, "venue": schedule.venue, "published": schedule.published}
    db.delete(schedule)
    audit(db, user, "DELETE_SCHEDULE", "event_schedule", schedule_id, before=jsonable_encoder(before))
    db.commit()
    return {"message": "赛程已删除"}


@router.get("/admin/results")
def admin_results(event_id: int, round_id: int | None = None, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    if user.role not in {Role.DEVELOPER, Role.SPORTS_TEACHER} and not (
        has_event_permission(db, user, event_id, "can_schedule") or has_event_permission(db, user, event_id, "can_score") or has_event_permission(db, user, event_id, "can_review") or has_event_permission(db, user, event_id, "can_export")
    ):
        raise HTTPException(403, "没有该项目的查看权限")
    stmt = select(Result).where(Result.event_id == event_id)
    if round_id:
        stmt = stmt.where(Result.round_id == round_id)
    return [result_dict(db, row) for row in db.scalars(stmt.order_by(Result.rank, Result.id))]


@router.get("/admin/registrations")
def admin_registrations(event_id: int, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    if user.role not in {Role.DEVELOPER, Role.SPORTS_TEACHER} and not (
        has_event_permission(db, user, event_id, "can_score") or has_event_permission(db, user, event_id, "can_review") or has_event_permission(db, user, event_id, "can_export")
    ):
        raise HTTPException(403, "没有该项目的查看权限")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    repaired = sync_event_rounds(db, event_id=event_id)
    if repaired:
        db.commit()
    rounds = list(db.scalars(select(EventRound).where(EventRound.event_id == event_id).order_by(EventRound.sequence)))
    registrations = list(db.scalars(select(Registration).where(Registration.event_id == event_id).order_by(Registration.heat, Registration.lane)))
    return {"rounds": rounds, "items": [{"id": row.id, "round_id": row.round_id, "heat": row.heat, "lane": row.lane, "status": row.status, "student": participant_for_registration(db, row)} for row in registrations]}


@router.put("/admin/results")
def save_result(data: ResultEntry, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    require_event_permission(db, user, data.event_id, "can_score")
    registration = db.get(Registration, data.registration_id)
    if not registration or registration.event_id != data.event_id or registration.round_id != data.round_id:
        raise HTTPException(422, "参赛记录与项目或比赛轮次不匹配")
    row = db.scalar(select(Result).where(Result.round_id == data.round_id, Result.registration_id == data.registration_id))
    if row and row.state not in {ResultState.DRAFT, ResultState.RETURNED, ResultState.PUBLISHED}:
        raise HTTPException(409, "该成绩已提交，当前不能修改")
    before = result_dict(db, row) if row else None
    if row and row.published_at and not data.modification_reason:
        raise HTTPException(422, "修改已发布成绩必须填写修改原因")
    if not row:
        row = Result(event_id=data.event_id, round_id=data.round_id, registration_id=data.registration_id)
        db.add(row)
    else:
        row.version += 1
    row.raw_value = data.raw_value
    row.competition_status = data.competition_status
    row.notes = data.notes
    row.modification_reason = data.modification_reason
    row.state = ResultState.DRAFT
    row.entered_by_id = user.id
    row.entered_at = utcnow()
    row.reviewed_by_id = None
    row.reviewed_at = None
    row.finalized_by_id = None
    row.finalized_at = None
    db.flush()
    calculate_rankings(db, data.event_id, data.round_id)
    audit(db, user, "SAVE_RESULT", "result", row.id, before=before, after=result_dict(db, row), reason=data.modification_reason)
    db.commit()
    return result_dict(db, row)


@router.delete("/admin/results/{result_id}")
def delete_result(result_id: int, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    row = db.get(Result, result_id)
    if not row:
        raise HTTPException(404, "成绩不存在")
    require_event_permission(db, user, row.event_id, "can_score")
    if row.state not in {ResultState.DRAFT, ResultState.RETURNED} or row.published_at:
        raise HTTPException(409, "只有未发布的草稿或退回成绩可以删除")
    before = result_dict(db, row)
    event_id, round_id = row.event_id, row.round_id
    rope_detail = db.scalar(select(RopeResultDetail).where(RopeResultDetail.result_id == row.id))
    if rope_detail:
        db.delete(rope_detail)
    for review in db.scalars(select(ResultReview).where(ResultReview.result_id == row.id)):
        db.delete(review)
    db.delete(row)
    db.flush()
    calculate_rankings(db, event_id, round_id)
    audit(db, user, "DELETE_RESULT", "result", result_id, before=before)
    db.commit()
    return {"message": "成绩草稿已删除"}


@router.post("/admin/results/submit")
def submit_results(data: ResultAction, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    rows = [db.get(Result, result_id) for result_id in data.result_ids]
    if any(not row for row in rows):
        raise HTTPException(404, "部分成绩不存在")
    for row in rows:
        require_event_permission(db, user, row.event_id, "can_score")
        if row.state not in {ResultState.DRAFT, ResultState.RETURNED}:
            raise HTTPException(409, "只有草稿或退回成绩可以提交")
        add_review(db, row, user, "ENTER", ResultState.SUBMITTED, data.comment)
        audit(db, user, "SUBMIT_RESULT", "result", row.id, after={"state": ResultState.SUBMITTED}, reason=data.comment)
    db.commit()
    return {"message": "成绩已提交审核"}


@router.post("/admin/results/review")
def review_results(data: ResultAction, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    rows = [db.get(Result, result_id) for result_id in data.result_ids]
    if any(not row for row in rows):
        raise HTTPException(404, "部分成绩不存在")
    for row in rows:
        require_event_permission(db, user, row.event_id, "can_review")
        if row.state != ResultState.SUBMITTED:
            raise HTTPException(409, "只有已提交审核的成绩可以裁判审核")
        next_state = ResultState.REVIEWED if data.approve else ResultState.RETURNED
        add_review(db, row, user, "REVIEW" if data.approve else "RETURN", next_state, data.comment)
        row.reviewed_by_id = user.id if data.approve else None
        row.reviewed_at = utcnow() if data.approve else None
        row.finalized_by_id = None
        row.finalized_at = None
        audit(
            db,
            user,
            "REVIEW_RESULT" if data.approve else "RETURN_RESULT",
            "result",
            row.id,
            after={"state": next_state},
            reason=data.comment,
        )
    db.commit()
    return {"message": "裁判审核已完成"}


@router.post("/sports-teacher/results/final-review")
def final_review(data: ResultAction, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    rows = [db.get(Result, result_id) for result_id in data.result_ids]
    if any(not row for row in rows):
        raise HTTPException(404, "部分成绩不存在")
    for row in rows:
        if row.state != ResultState.REVIEWED or not row.reviewed_by_id or not row.reviewed_at:
            raise HTTPException(409, "成绩必须先通过裁判审核才能进入终审")
        if data.approve:
            add_review(db, row, actor, "FINAL_REVIEW", ResultState.REVIEWED, data.comment)
            row.finalized_by_id = actor.id
            row.finalized_at = utcnow()
        else:
            add_review(db, row, actor, "FINAL_RETURN", ResultState.RETURNED, data.comment)
            row.finalized_by_id = None
            row.finalized_at = None
        audit(
            db,
            actor,
            "FINAL_REVIEW_RESULT" if data.approve else "FINAL_RETURN_RESULT",
            "result",
            row.id,
            after={"state": row.state},
            reason=data.comment,
        )
    db.commit()
    return {"message": "终审操作已完成"}


@router.post("/sports-teacher/results/publish")
def publish_results(data: ResultAction, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    rows = [db.get(Result, result_id) for result_id in data.result_ids]
    if any(not row for row in rows):
        raise HTTPException(404, "部分成绩不存在")
    now = utcnow()
    for row in rows:
        if row.state != ResultState.REVIEWED or not row.finalized_by_id or not row.finalized_at:
            raise HTTPException(409, "只有终审通过的成绩可以发布")
        add_review(db, row, actor, "PUBLISH", ResultState.PUBLISHED, data.comment)
        row.publisher_id = actor.id
        row.published_at = now
        row.published_version = row.version
        row.published_raw_value = row.raw_value
        row.published_competition_status = row.competition_status
        row.published_notes = row.notes
        row.published_rank = row.rank
        row.published_points = row.points
        rope_detail = db.scalar(select(RopeResultDetail).where(RopeResultDetail.result_id == row.id))
        if rope_detail:
            rope_detail.published_detail = jsonable_encoder(rope_detail_payload(rope_detail))
        event = db.get(Event, row.event_id)
        model_id = event.scoring_model_id if event else None
        if model_id:
            model = db.get(ScoringModel, model_id)
            model.locked_by_published_results = True
        if event and event.qualification_count > 0:
            next_round = db.scalar(
                select(EventRound)
                .where(EventRound.event_id == event.id, EventRound.sequence > db.get(EventRound, row.round_id).sequence)
                .order_by(EventRound.sequence)
            )
            qualification = db.scalar(
                select(QualificationRecord).where(
                    QualificationRecord.registration_id == row.registration_id,
                    QualificationRecord.from_round_id == row.round_id,
                )
            )
            if not qualification:
                qualification = QualificationRecord(registration_id=row.registration_id, from_round_id=row.round_id)
                db.add(qualification)
            qualification.next_round_id = next_round.id if next_round else None
            qualification.status = "QUALIFIED" if row.rank and row.rank <= event.qualification_count else "NOT_QUALIFIED"
            qualification.decided_by_id = actor.id
            qualification.decided_at = now
        audit(db, actor, "PUBLISH_RESULT", "result", row.id, after={"state": ResultState.PUBLISHED, "published_version": row.version}, reason=data.comment)
    db.commit()
    return {"message": "最终成绩已发布", "published_at": utc_iso(now)}


@router.post("/sports-teacher/results/unpublish")
def unpublish_results(data: ResultAction, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    rows = [db.get(Result, result_id) for result_id in data.result_ids]
    if any(not row for row in rows):
        raise HTTPException(404, "部分成绩不存在")
    for row in rows:
        if row.state != ResultState.PUBLISHED and not row.published_at:
            raise HTTPException(409, "只有已发布的成绩可以下架/撤回发布")
        add_review(db, row, actor, "UNPUBLISH", ResultState.REVIEWED, data.comment or "管理员下架/撤回发布成绩")
        row.state = ResultState.REVIEWED
        row.published_at = None
        row.published_version = None
        row.published_raw_value = None
        row.published_competition_status = None
        row.published_notes = None
        row.published_rank = None
        row.published_points = None
        row.publisher_id = None
        rope_detail = db.scalar(select(RopeResultDetail).where(RopeResultDetail.result_id == row.id))
        if rope_detail:
            rope_detail.published_detail = None
    audit(db, actor, "UNPUBLISH_RESULTS", "result", rows[0].id if rows else None, after={"count": len(rows)})
    db.commit()
    return {"message": "已成功从实时成绩大屏下架/撤回发布"}


@router.get("/admin/results/export")
def export_results(event_id: int, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    require_event_permission(db, user, event_id, "can_export")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    results = list(db.scalars(select(Result).where(Result.event_id == event_id).order_by(Result.rank, Result.id)))
    file_path = create_score_workbook(db, event, results, user)
    audit(db, user, "EXPORT_RESULTS", "event", event.id, after={"file": file_path.name})
    db.commit()
    return FileResponse(file_path, filename=file_path.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/public/meets")
def public_meets(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SportsMeet)
        .where(SportsMeet.public_visible.is_(True))
        .order_by(SportsMeet.start_date.desc(), SportsMeet.id.desc())
    )
    return [{"id": row.id, "name": row.name, "edition": row.edition, "start_date": row.start_date, "end_date": row.end_date, "status": row.status} for row in rows]


@router.get("/public/latest-results")
def latest_results(limit: int = Query(6, ge=1, le=20), meet_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(Result).join(Event, Result.event_id == Event.id).where(Result.published_at.is_not(None))
    if meet_id:
        stmt = stmt.where(Event.meet_id == meet_id)
    rows = list(db.scalars(stmt.order_by(Result.published_at.desc()).limit(limit * 8)))
    grouped: dict[tuple[int, int | None], list[Result]] = {}
    for row in rows:
        grouped.setdefault((row.event_id, row.round_id), []).append(row)
    cards = []
    for (event_id, round_id), event_rows in list(grouped.items())[:limit]:
        event = db.get(Event, event_id)
        meet = db.get(SportsMeet, event.meet_id)
        round_row = db.get(EventRound, round_id) if round_id else None
        top = sorted(event_rows, key=lambda item: item.published_rank or 999)[:3]
        cards.append({"event_id": event_id, "meet_id": event.meet_id, "round_id": round_id, "event_name": event.name, "gender_group": event.gender_group, "stage": round_row.stage if round_row else event.stage, "round_name": round_row.name if round_row else "", "unit": event.result_unit, "meet_name": meet.name, "published_at": utc_iso(max(row.published_at for row in event_rows)), "top_three": [result_dict(db, row, public=True) for row in top]})
    return cards


@router.get("/public/results")
def public_results(event_id: int | None = None, meet_id: int | None = None, gender: str | None = None, stage: str | None = None, college: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Result).join(Event, Result.event_id == Event.id).join(EventRound, Result.round_id == EventRound.id).where(Result.published_at.is_not(None))
    if event_id:
        stmt = stmt.where(Result.event_id == event_id)
    if meet_id:
        stmt = stmt.where(Event.meet_id == meet_id)
    if gender:
        stmt = stmt.where(Event.gender_group == gender)
    if stage:
        stmt = stmt.where(EventRound.stage == stage)
    rows = list(db.scalars(stmt.order_by(Result.event_id, Result.published_rank)))
    items = [result_dict(db, row, public=True) for row in rows]
    if college:
        items = [item for item in items if item["college"] == college]
    return items


@router.get("/public/schedules")
def public_schedules(meet_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(EventSchedule).join(Event, EventSchedule.event_id == Event.id).where(EventSchedule.published.is_(True))
    if meet_id:
        stmt = stmt.where(Event.meet_id == meet_id)
    rows = list(db.scalars(stmt.order_by(EventSchedule.competition_at)))
    return [{"id": row.id, "meet_id": db.get(Event, row.event_id).meet_id, "event_id": row.event_id, "event_name": db.get(Event, row.event_id).name, "round_id": row.round_id, "round_name": db.get(EventRound, row.round_id).name if row.round_id and db.get(EventRound, row.round_id) else "全部轮次", "competition_at": row.competition_at, "check_in_at": row.check_in_at, "venue": row.venue, "heat": row.heat, "status": row.status, "notes": row.notes} for row in rows]


@router.get("/public/college-rankings")
def college_rankings(meet_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(Result).join(Event, Result.event_id == Event.id).where(Result.published_at.is_not(None))
    if meet_id:
        stmt = stmt.where(Event.meet_id == meet_id)
    rows = list(db.scalars(stmt))
    totals: dict[str, Decimal] = {}
    medals: dict[str, list[int]] = {}
    for row in rows:
        registration = db.get(Registration, row.registration_id)
        participant = participant_for_registration(db, registration)
        points = row.published_points
        rank = row.published_rank
        college = participant["college"]
        if not college:
            continue
        totals[college] = totals.get(college, Decimal("0")) + Decimal(points or 0)
        medals.setdefault(college, [0, 0, 0])
        if rank in {1, 2, 3}:
            medals[college][rank - 1] += 1
    ordered = sorted(totals, key=lambda college: (totals[college], *medals[college]), reverse=True)
    return [{"rank": index + 1, "college": college, "points": totals[college], "gold": medals[college][0], "silver": medals[college][1], "bronze": medals[college][2]} for index, college in enumerate(ordered)]


def _student_roster(db: Session, user: User) -> StudentRoster:
    row = db.scalar(select(StudentRoster).where(StudentRoster.user_id == user.id))
    if not row:
        raise HTTPException(404, "学生档案不存在")
    return row


@router.get("/student/me")
def student_me(user: User = Depends(student_only), db: Session = Depends(get_db)):
    row = _student_roster(db, user)
    return {"student_no": mask_student_no(row.student_no), "name": row.name, "gender": row.gender, "college": row.college, "major": row.major, "class_name": row.class_name}


@router.get("/student/my-events")
def student_events(user: User = Depends(student_only), db: Session = Depends(get_db)):
    student = _student_roster(db, user)
    registrations = list(db.scalars(select(Registration).where(Registration.student_id == student.id)))
    items = []
    for registration in registrations:
        event = db.get(Event, registration.event_id)
        round_row = db.get(EventRound, registration.round_id)
        schedule = db.scalar(select(EventSchedule).where(EventSchedule.event_id == event.id, or_(EventSchedule.round_id == registration.round_id, EventSchedule.round_id.is_(None)), EventSchedule.published.is_(True)).order_by(EventSchedule.round_id.desc(), EventSchedule.competition_at))
        items.append({"registration_id": registration.id, "event_id": event.id, "event_name": event.name, "round_id": registration.round_id, "round_name": round_row.name if round_row else "", "stage": round_row.stage if round_row else event.stage, "status": registration.status, "heat": registration.heat, "lane": registration.lane, "schedule": schedule})
    return items


@router.get("/student/my-results")
def student_results(user: User = Depends(student_only), db: Session = Depends(get_db)):
    student = _student_roster(db, user)
    registration_ids = list(db.scalars(select(Registration.id).where(Registration.student_id == student.id)))
    rows = list(db.scalars(select(Result).where(Result.registration_id.in_(registration_ids)))) if registration_ids else []
    items = []
    for row in rows:
        if row.published_at:
            items.append(result_dict(db, row, public=True))
        else:
            event = db.get(Event, row.event_id)
            round_row = db.get(EventRound, row.round_id)
            items.append({"event_id": row.event_id, "event_name": event.name, "stage": round_row.stage if round_row else event.stage, "round_name": round_row.name if round_row else "", "state": "审核中", "raw_value": None, "rank": None, "points": None, "published_at": None})
    return items


@router.get("/student/my-qualifications")
def student_qualifications(user: User = Depends(student_only), db: Session = Depends(get_db)):
    student = _student_roster(db, user)
    rows = list(db.scalars(select(Registration).where(Registration.student_id == student.id).order_by(Registration.event_id, Registration.round_id)))
    items = []
    for registration in rows:
        round_row = db.get(EventRound, registration.round_id)
        if not round_row or round_row.stage not in {"SEMIFINAL", "FINAL"}:
            continue
        event = db.get(Event, registration.event_id)
        items.append({"registration_id": registration.id, "event_id": event.id, "event_name": event.name, "status": "QUALIFIED", "round_id": round_row.id, "round_name": round_row.name, "stage": round_row.stage, "decided_at": None})
    return items


# ==============================================================================
# 🪢 跳绳团体赛模块 (Rope Skipping Team Engine)
# ==============================================================================

ROPE_EVENT_CONFIG = {
    "ROPE_SINGLE": {"name": "跳绳 - “前单跳”团体挑战赛", "unit": "次", "sort": "DESC"},
    "ROPE_SYNC": {"name": "跳绳 - 集体单摇跳", "unit": "秒", "sort": "ASC"},
    "ROPE_FIG8": {"name": "跳绳 - “8”字环绕跳", "unit": "次", "sort": "DESC"},
}


def _rope_lineup_member_dict(db: Session, row: RopeLineupMember) -> dict:
    student = db.get(StudentRoster, row.student_id)
    return {
        "id": row.id,
        "student_id": row.student_id,
        "student_no": student.student_no if student else "",
        "name": student.name if student else "",
        "gender": student.gender if student else "",
        "role": row.role,
        "sequence": row.sequence,
    }


@router.post("/sports-teacher/rope/initialize")
def initialize_rope_events(data: RopeInitializeRequest, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    meet = db.get(SportsMeet, data.meet_id)
    if not meet:
        raise HTTPException(404, "运动会不存在")
    created_events = 0
    created_registrations = 0
    events: list[Event] = []
    for code, config in ROPE_EVENT_CONFIG.items():
        event = db.scalar(select(Event).where(Event.meet_id == meet.id, Event.code == code))
        if not event:
            event = Event(
                meet_id=meet.id,
                code=code,
                name=config["name"],
                gender_group="MIXED",
                participant_group="STUDENT",
                event_type="TEAM",
                result_unit=config["unit"],
                sort_direction=config["sort"],
                stage="FINAL",
                qualification_count=0,
                scoring_places=8,
                points_multiplier=1,
            )
            db.add(event)
            db.flush()
            created_events += 1
        else:
            event.name = config["name"]
            event.gender_group = "MIXED"
            event.event_type = "TEAM"
            event.result_unit = config["unit"]
            event.sort_direction = config["sort"]
            event.stage = "FINAL"
            event.points_multiplier = 1
        sync_event_rounds(db, event_id=event.id)
        events.append(event)

    teams = list(
        db.scalars(
            select(CollegeTeam)
            .where(CollegeTeam.meet_id == meet.id, CollegeTeam.event_id.is_(None))
            .order_by(CollegeTeam.college, CollegeTeam.id)
        )
    )
    for event in events:
        round_row = db.scalar(select(EventRound).where(EventRound.event_id == event.id, EventRound.stage == "FINAL"))
        for team in teams:
            registration = db.scalar(
                select(Registration.id).where(
                    Registration.event_id == event.id,
                    Registration.round_id == round_row.id,
                    Registration.college_team_id == team.id,
                )
            )
            if not registration:
                db.add(Registration(event_id=event.id, round_id=round_row.id, college_team_id=team.id, status="REGISTERED"))
                created_registrations += 1
    audit(
        db,
        actor,
        "INITIALIZE_ROPE_EVENTS",
        "sports_meet",
        meet.id,
        after={"created_events": created_events, "created_registrations": created_registrations},
    )
    db.commit()

    # 自动为跳绳赛制创建并绑定默认计分模型（前8名积分：9-7-6-5-4-3-2-1）
    created_model = False
    rope_model_name = f"跳绳赛制计分模型（{meet.name} {meet.edition}）"
    existing_model = db.scalar(
        select(ScoringModel).where(ScoringModel.name == rope_model_name)
    )
    if not existing_model:
        model = ScoringModel(
            name=rope_model_name,
            description="跳绳团体赛自动生成计分模型。前8名积分：9-7-6-5-4-3-2-1。并列时平均所占名次积分。",
            status="ENABLED",
            places=8,
            individual_multiplier=1,
            relay_multiplier=1,
            team_multiplier=1,
            tie_rule="AVERAGE_OCCUPIED",
            non_finish_points={},
            tiebreak_rules=[],
            version=1,
            created_by_id=actor.id,
            updated_by_id=actor.id,
        )
        db.add(model)
        db.flush()
        for place, pts in enumerate([9, 7, 6, 5, 4, 3, 2, 1], 1):
            db.add(ScoringModelItem(model_id=model.id, place=place, points=pts))
        existing_model = model
        created_model = True
    elif existing_model.status != "ENABLED":
        existing_model.status = "ENABLED"

    # 为每个跳绳项目绑定计分模型（若尚未绑定）
    for event in events:
        if event.scoring_model_id != existing_model.id:
            event.scoring_model_id = existing_model.id
            existing_binding = db.scalar(
                select(ScoringModelBinding).where(
                    ScoringModelBinding.meet_id == meet.id,
                    ScoringModelBinding.event_id == event.id,
                )
            )
            if not existing_binding:
                db.add(ScoringModelBinding(
                    meet_id=meet.id,
                    event_id=event.id,
                    model_id=existing_model.id,
                    model_version=existing_model.version,
                    snapshot={
                        "id": existing_model.id,
                        "name": existing_model.name,
                        "places": existing_model.places,
                        "tie_rule": existing_model.tie_rule,
                        "team_multiplier": float(existing_model.team_multiplier),
                    },
                    bound_by_id=actor.id,
                ))

    db.commit()
    model_tip = f"，并{'新建' if created_model else '复用'}了默认计分模型（前8名 9-7-6-5-4-3-2-1 分）"
    return {
        "message": f"跳绳赛制已就绪：新增 {created_events} 个项目、{created_registrations} 条学院报名记录{model_tip}",
        "event_ids": [event.id for event in events],
    }



@router.get("/sports-teacher/rope/status")
def rope_status(meet_id: int, _actor: User = Depends(manager_only), db: Session = Depends(get_db)):
    meet = db.get(SportsMeet, meet_id)
    if not meet:
        raise HTTPException(404, "运动会不存在")
    event_rows = list(db.scalars(select(Event).where(Event.meet_id == meet_id, Event.code.in_(list(ROPE_RULES)))))
    by_code = {event.code: event for event in event_rows}
    items = []
    for code in ROPE_RULES:
        event = by_code.get(code)
        if not event:
            continue
        round_row = db.scalar(select(EventRound).where(EventRound.event_id == event.id, EventRound.stage == "FINAL"))
        registrations = list(
            db.scalars(
                select(Registration)
                .where(
                    Registration.event_id == event.id,
                    Registration.round_id == round_row.id,
                    Registration.college_team_id.is_not(None),
                )
                .order_by(Registration.id)
            )
        )
        teams = []
        for registration in registrations:
            team = db.get(CollegeTeam, registration.college_team_id)
            if not team:
                continue
            member_rows = list(db.scalars(select(CollegeTeamMember).where(CollegeTeamMember.team_id == team.id).order_by(CollegeTeamMember.id)))
            members = []
            for member in member_rows:
                student = db.get(StudentRoster, member.student_id)
                if student:
                    members.append({
                        "student_id": student.id,
                        "student_no": student.student_no,
                        "name": student.name,
                        "gender": student.gender,
                    })
            lineup_rows = list(
                db.scalars(
                    select(RopeLineupMember)
                    .where(RopeLineupMember.event_id == event.id, RopeLineupMember.college_team_id == team.id)
                    .order_by(RopeLineupMember.role, RopeLineupMember.sequence, RopeLineupMember.id)
                )
            )
            result = db.scalar(
                select(Result).where(Result.round_id == registration.round_id, Result.registration_id == registration.id)
            )
            teams.append({
                "registration_id": registration.id,
                "team_id": team.id,
                "college": team.college,
                "team_name": team.team_name,
                "members": members,
                "lineup": [_rope_lineup_member_dict(db, row) for row in lineup_rows],
                "lineup_status": rope_lineup_status(db, event, team.id, lineup_rows),
                "result": result_dict(db, result) if result else None,
            })
        items.append({
            "id": event.id,
            "code": event.code,
            "name": event.name,
            "round_id": round_row.id if round_row else None,
            "rule": ROPE_RULES[code],
            "teams": teams,
        })
    return {"meet": {"id": meet.id, "name": meet.name, "edition": meet.edition}, "events": items}


@router.put("/sports-teacher/rope/lineups")
def save_rope_lineup(data: RopeLineupUpsert, actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    event = db.get(Event, data.event_id)
    team = db.get(CollegeTeam, data.college_team_id)
    if not event or not rope_rule_for_event(event):
        raise HTTPException(404, "标准跳绳项目不存在")
    if not team or team.meet_id != event.meet_id:
        raise HTTPException(422, "学院代表队不属于该运动会")
    if not db.scalar(select(Registration.id).where(Registration.event_id == event.id, Registration.college_team_id == team.id)):
        raise HTTPException(422, "该学院代表队尚未报名本项目")
    roles = [member.role.strip().upper() for member in data.members]
    if any(role not in {"JUMPER", "TURNER"} for role in roles):
        raise HTTPException(422, "阵容角色只能是跳绳者或摇绳者")
    proposed = [
        RopeLineupMember(
            event_id=event.id,
            college_team_id=team.id,
            student_id=member.student_id,
            role=role,
            sequence=member.sequence,
        )
        for member, role in zip(data.members, roles)
    ]
    status = rope_lineup_status(db, event, team.id, proposed)
    if not status["valid"]:
        raise HTTPException(422, "；".join(status["errors"]))
    old_rows = list(
        db.scalars(
            select(RopeLineupMember).where(
                RopeLineupMember.event_id == event.id,
                RopeLineupMember.college_team_id == team.id,
            )
        )
    )
    for row in old_rows:
        db.delete(row)
    db.flush()
    db.add_all(proposed)
    db.flush()
    audit(
        db,
        actor,
        "SAVE_ROPE_LINEUP",
        "college_team",
        team.id,
        before={"event_id": event.id, "member_ids": [row.student_id for row in old_rows]},
        after={"event_id": event.id, "members": data.model_dump(mode="json")["members"]},
    )
    db.commit()
    return {"message": "跳绳项目阵容已保存并通过人数、角色及男女比例校验", "status": status}


@router.put("/admin/rope/results")
def save_rope_result(data: RopeResultEntry, user: User = Depends(manager_only), db: Session = Depends(get_db)):
    require_event_permission(db, user, data.event_id, "can_score")
    event = db.get(Event, data.event_id)
    rule = rope_rule_for_event(event)
    if not event or not rule:
        raise HTTPException(404, "标准跳绳项目不存在")
    registration = db.get(Registration, data.registration_id)
    if not registration or registration.event_id != event.id or registration.round_id != data.round_id or not registration.college_team_id:
        raise HTTPException(422, "参赛队伍与跳绳项目或比赛轮次不匹配")
    lineup = rope_lineup_status(db, event, registration.college_team_id)
    if not lineup["valid"]:
        raise HTTPException(422, "阵容校验未通过：" + "；".join(lineup["errors"]))

    individual_counts = None
    completed_target = None
    elapsed_seconds = None
    completed_count = None
    if event.code == "ROPE_SINGLE":
        individual_counts = list(data.individual_counts or [])
        if len(individual_counts) != 10 or any(value < 0 or value > 500 for value in individual_counts):
            raise HTTPException(422, "前单跳必须录入10名队员各自1分钟次数，单人成绩范围为0—500次")
        raw_value = Decimal(sum(individual_counts))
        completed_count = int(raw_value)
        completed_target = True
        generated_notes = f"男女各5人每人1分钟，10人团体总次数 {completed_count} 次；个人明细：{individual_counts}"
    elif event.code == "ROPE_SYNC":
        if data.completed_target is None:
            raise HTTPException(422, "请选择是否在5分钟内完成30次有效跳动")
        completed_target = data.completed_target
        if completed_target:
            elapsed_seconds = Decimal(data.elapsed_seconds or 0)
            if elapsed_seconds <= 0 or elapsed_seconds > 300:
                raise HTTPException(422, "完成30次的用时必须大于0秒且不超过300秒")
            completed_count = 30
            raw_value = elapsed_seconds
            generated_notes = f"5分钟内完成30次有效跳动，用时 {elapsed_seconds} 秒"
        else:
            completed_count = int(data.completed_count if data.completed_count is not None else -1)
            if completed_count < 0 or completed_count >= 30:
                raise HTTPException(422, "未完成队伍的有效跳动次数必须在0—29次之间")
            elapsed_seconds = Decimal("300")
            raw_value = Decimal(1000 + (30 - completed_count))
            generated_notes = f"5分钟未完成30次任务，实际完成 {completed_count} 次"
    else:
        completed_count = int(data.completed_count if data.completed_count is not None else -1)
        if completed_count < 0 or completed_count > 10000:
            raise HTTPException(422, "8字环绕跳有效次数必须在0—10000次之间")
        elapsed_seconds = Decimal("300")
        raw_value = Decimal(completed_count)
        generated_notes = f"22人8字环绕跳，5分钟全队有效完成 {completed_count} 次"

    row = db.scalar(select(Result).where(Result.round_id == data.round_id, Result.registration_id == data.registration_id))
    if row and row.state not in {ResultState.DRAFT, ResultState.RETURNED, ResultState.PUBLISHED}:
        raise HTTPException(409, "该成绩已提交，当前不能修改")
    before = result_dict(db, row) if row else None
    if row and row.published_at and not data.modification_reason:
        raise HTTPException(422, "修改已发布成绩必须填写修改原因")
    if not row:
        row = Result(event_id=event.id, round_id=data.round_id, registration_id=data.registration_id)
        db.add(row)
    else:
        row.version += 1
    row.raw_value = raw_value
    row.competition_status = "NORMAL"
    row.notes = "；".join(part for part in [generated_notes, data.notes] if part)
    row.modification_reason = data.modification_reason
    row.state = ResultState.DRAFT
    row.entered_by_id = user.id
    row.entered_at = utcnow()
    row.reviewed_by_id = None
    row.reviewed_at = None
    row.finalized_by_id = None
    row.finalized_at = None
    db.flush()
    detail = db.scalar(select(RopeResultDetail).where(RopeResultDetail.result_id == row.id))
    if not detail:
        detail = RopeResultDetail(result_id=row.id)
        db.add(detail)
    detail.individual_counts = individual_counts
    detail.completed_target = completed_target
    detail.elapsed_seconds = elapsed_seconds
    detail.completed_count = completed_count
    db.flush()
    calculate_rankings(db, event.id, data.round_id)
    audit(db, user, "SAVE_ROPE_RESULT", "result", row.id, before=before, after=result_dict(db, row), reason=data.modification_reason)
    db.commit()
    return result_dict(db, row)


# ==============================================================================
# 🏀 篮球赛事模块 (Basketball Tournament Multi-stage Engine)
# ==============================================================================

@router.get("/sports-teacher/basketball/teams")
def basketball_teams(event_id: int | None = None, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    stmt = select(CollegeTeam)
    if event_id:
        event = db.get(Event, event_id)
        if event:
            stmt = stmt.where(CollegeTeam.meet_id == event.meet_id, or_(CollegeTeam.event_id == event_id, CollegeTeam.event_id.is_(None)))
    all_teams = list(db.scalars(stmt.order_by(CollegeTeam.college, CollegeTeam.team_name)))
    registered_teams = []
    registered_team_ids = []
    if event_id:
        regs = list(db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id.is_not(None))))
        registered_team_ids = [r.college_team_id for r in regs]
        for r in regs:
            t = db.get(CollegeTeam, r.college_team_id)
            if t:
                registered_teams.append({
                    "registration_id": r.id,
                    "team_id": t.id,
                    "college": t.college,
                    "team_name": t.team_name,
                    "group_tag": r.group_tag or "未分组",
                    "status": r.status,
                })
    return {
        "registered_teams": registered_teams,
        "registered_team_ids": registered_team_ids,
        "all_available_teams": [{"id": t.id, "college": t.college, "team_name": t.team_name} for t in all_teams],
    }


@router.post("/sports-teacher/basketball/quick-create-event")
def basketball_quick_create_event(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    meet_id = data.get("meet_id")
    if not meet_id:
        meet = db.scalar(select(SportsMeet).order_by(SportsMeet.id.desc()))
        if not meet:
            raise HTTPException(400, "请先在【赛事与项目】中创建运动会赛事")
        meet_id = meet.id

    name = data.get("name", "男子篮球赛")
    code = data.get("code", f"BB_{int(datetime.now().timestamp()) % 10000}")
    gender = data.get("gender_group", "MALE")

    # 检查是否已存在同名或同 code
    existing = db.scalar(select(Event).where(Event.meet_id == meet_id, Event.code == code))
    if existing:
        code = f"{code}_{int(datetime.now().timestamp()) % 100}"

    # 绑定篮球计分模型
    bb_model = db.scalar(select(ScoringModel).where(ScoringModel.name.contains("篮球")))
    model_id = bb_model.id if bb_model else None

    event = Event(
        meet_id=meet_id,
        code=code,
        name=name,
        gender_group=gender,
        participant_group="STUDENT",
        event_type="TEAM",
        result_unit="分",
        sort_direction="DESC",
        stage="FINAL",
        qualification_count=0,
        scoring_places=4,
        points_multiplier=Decimal("2.0"),
        scoring_model_id=model_id,
    )
    db.add(event)
    db.flush()

    round_row = EventRound(event_id=event.id, name="决赛", stage="FINAL", sequence=1, qualification_count=0)
    db.add(round_row)

    # 自动赋予当前管理员权限
    perm = EventAdminPermission(
        user_id=user.id,
        event_id=event.id,
        can_schedule=True,
        can_score=True,
        can_review=True,
        can_export=True,
        assigned_by_id=user.id,
    )
    db.add(perm)
    db.commit()

    return {"message": f"成功创建【{name}】赛事，已自动生成赛程轮次与权限！", "event": {"id": event.id, "name": event.name, "event_type": event.event_type}}


@router.post("/sports-teacher/basketball/add-teams")
def basketball_add_teams(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    event_id = data.get("event_id")
    team_ids = data.get("team_ids", [])
    if not event_id:
        raise HTTPException(400, "请指定比赛项目 ID")
    if not team_ids:
        raise HTTPException(400, "请至少勾选一支学院代表队")

    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    rounds = list(db.scalars(select(EventRound).where(EventRound.event_id == event_id).order_by(EventRound.sequence)))
    if not rounds:
        round_row = EventRound(event_id=event.id, name="决赛", stage="FINAL", sequence=1, qualification_count=0)
        db.add(round_row)
        db.flush()
        target_round_id = round_row.id
    else:
        target_round_id = rounds[0].id

    added_count = 0
    for tid in team_ids:
        existing = db.scalar(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id == tid))
        if not existing:
            reg = Registration(
                event_id=event_id,
                round_id=target_round_id,
                college_team_id=tid,
                status="REGISTERED",
            )
            db.add(reg)
            added_count += 1

    db.commit()
    return {"message": f"成功为【{event.name}】添加 {added_count} 支学院参赛代表队！", "added_count": added_count}


def _match_dict(db: Session, match: TournamentMatch) -> dict:
    home_team = db.get(CollegeTeam, match.home_team_id) if match.home_team_id else None
    away_team = db.get(CollegeTeam, match.away_team_id) if match.away_team_id else None
    winner = db.get(CollegeTeam, match.winner_team_id) if match.winner_team_id else None
    forfeit_team = db.get(CollegeTeam, match.forfeit_team_id) if match.forfeit_team_id else None
    home_student = db.get(StudentRoster, match.home_student_id) if match.home_student_id else None
    away_student = db.get(StudentRoster, match.away_student_id) if match.away_student_id else None
    winner_student = db.get(StudentRoster, match.winner_student_id) if match.winner_student_id else None
    return {
        "id": match.id,
        "event_id": match.event_id,
        "round_id": match.round_id,
        "stage_type": match.stage_type,
        "match_code": match.match_code,
        "match_name": match.match_name,
        "home_team_id": match.home_team_id,
        "home_team_name": home_team.team_name if home_team else ("待定队伍" if not home_student else None),
        "home_college": home_team.college if home_team else (home_student.college if home_student else "待定"),
        "away_team_id": match.away_team_id,
        "away_team_name": away_team.team_name if away_team else ("待定队伍" if not away_student else None),
        "away_college": away_team.college if away_team else (away_student.college if away_student else "待定"),
        "home_student_id": match.home_student_id,
        "home_student_name": home_student.name if home_student else None,
        "home_student_no": home_student.student_no if home_student else None,
        "away_student_id": match.away_student_id,
        "away_student_name": away_student.name if away_student else None,
        "away_student_no": away_student.student_no if away_student else None,
        "home_score": match.home_score,
        "away_score": match.away_score,
        "winner_team_id": match.winner_team_id,
        "winner_team_name": winner.team_name if winner else None,
        "loser_team_id": match.loser_team_id,
        "winner_student_id": match.winner_student_id,
        "winner_student_name": winner_student.name if winner_student else None,
        "loser_student_id": match.loser_student_id,
        "best_of": match.best_of or 3,
        "status": match.status,
        "court_venue": match.court_venue,
        "match_time": match.match_time,
        "sets_detail": match.sets_detail or [],
        "team_rubber_detail": match.team_rubber_detail or [],
        "forfeit_team_id": match.forfeit_team_id,
        "forfeit_team_name": forfeit_team.team_name if forfeit_team else None,
        "notes": match.notes,
    }


@router.post("/sports-teacher/basketball/groups/auto-generate")
def basketball_generate_groups(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    registrations = list(db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id.is_not(None))))
    if len(registrations) < 4:
        raise HTTPException(400, "篮球赛分组至少需要 4 支学院代表队")

    a_team_ids = data.get("a_team_ids")
    b_team_ids = data.get("b_team_ids")

    if not a_team_ids or not b_team_ids:
        all_team_ids = [r.college_team_id for r in registrations]
        half = (len(all_team_ids) + 1) // 2
        a_team_ids = all_team_ids[:half]
        b_team_ids = all_team_ids[half:]

    # 更新注册记录的组别
    for reg in registrations:
        if reg.college_team_id in a_team_ids:
            reg.group_tag = "A"
            reg.heat = "A组"
        elif reg.college_team_id in b_team_ids:
            reg.group_tag = "B"
            reg.heat = "B组"

    # 清空此前的循环赛对阵
    old_matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type.in_(["GROUP_A", "GROUP_B"]))))
    for m in old_matches:
        db.delete(m)
    db.flush()

    # 自动生成 A 组单循环对阵
    created_matches = 0
    for i in range(len(a_team_ids)):
        for j in range(i + 1, len(a_team_ids)):
            t1, t2 = a_team_ids[i], a_team_ids[j]
            m = TournamentMatch(
                event_id=event_id,
                stage_type="GROUP_A",
                match_code=f"A_{i+1}-{j+1}",
                match_name=f"A组单循环第{created_matches+1}场",
                home_team_id=t1,
                away_team_id=t2,
                status="NOT_STARTED",
                court_venue="篮球馆1号场",
            )
            db.add(m)
            created_matches += 1

    # 自动生成 B 组单循环对阵
    b_count = 0
    for i in range(len(b_team_ids)):
        for j in range(i + 1, len(b_team_ids)):
            t1, t2 = b_team_ids[i], b_team_ids[j]
            m = TournamentMatch(
                event_id=event_id,
                stage_type="GROUP_B",
                match_code=f"B_{i+1}-{j+1}",
                match_name=f"B组单循环第{b_count+1}场",
                home_team_id=t1,
                away_team_id=t2,
                status="NOT_STARTED",
                court_venue="篮球馆2号场",
            )
            db.add(m)
            b_count += 1
            created_matches += 1

    db.commit()
    return {"message": f"成功完成 A/B 组抽签并生成 {created_matches} 场单循环赛程", "a_count": len(a_team_ids), "b_count": len(b_team_ids)}


@router.get("/sports-teacher/basketball/matches")
def basketball_matches(event_id: int, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id).order_by(TournamentMatch.id)))
    return [_match_dict(db, m) for m in matches]


@router.put("/sports-teacher/basketball/matches/{match_id}")
def basketball_update_match(match_id: int, data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    match = db.get(TournamentMatch, match_id)
    if not match:
        raise HTTPException(404, "对阵比赛不存在")
    require_event_permission(db, user, match.event_id, "can_score")

    home_score = data.get("home_score")
    away_score = data.get("away_score")
    if home_score is not None and away_score is not None:
        home_score = int(home_score)
        away_score = int(away_score)
        if home_score == away_score:
            raise HTTPException(400, "依据《篮球竞赛规则》，篮球比赛必须决出胜负，不能平局")
        match.home_score = home_score
        match.away_score = away_score
        if home_score > away_score:
            match.winner_team_id = match.home_team_id
            match.loser_team_id = match.away_team_id
        else:
            match.winner_team_id = match.away_team_id
            match.loser_team_id = match.home_team_id
        match.status = "FINISHED"

    if "court_venue" in data:
        match.court_venue = data["court_venue"]
    if "match_time" in data and data["match_time"]:
        match.match_time = datetime.fromisoformat(data["match_time"].replace("Z", ""))
    if "notes" in data:
        match.notes = data["notes"]

    db.commit()
    return {"message": "比分已录入并更新胜负结果", "match": _match_dict(db, match)}


@router.get("/sports-teacher/basketball/standings")
def basketball_standings(event_id: int, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type.in_(["GROUP_A", "GROUP_B"]))))
    registrations = list(db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id.is_not(None))))

    def calculate_group(group_letter: str):
        group_regs = [r for r in registrations if r.group_tag == group_letter]
        group_team_ids = [r.college_team_id for r in group_regs]
        group_matches = [m for m in matches if m.stage_type == f"GROUP_{group_letter}"]

        stats = {
            tid: {
                "team_id": tid,
                "team_name": db.get(CollegeTeam, tid).team_name if db.get(CollegeTeam, tid) else "队伍",
                "college": db.get(CollegeTeam, tid).college if db.get(CollegeTeam, tid) else "学院",
                "played": 0,
                "won": 0,
                "lost": 0,
                "points": 0,      # 胜2分，负1分，弃权0分
                "points_for": 0,  # 总得分
                "points_against": 0, # 总失分
                "points_diff": 0,    # 净胜分
            }
            for tid in group_team_ids
        }

        for m in group_matches:
            if m.status == "FINISHED" and m.home_team_id in stats and m.away_team_id in stats:
                h = stats[m.home_team_id]
                a = stats[m.away_team_id]
                h["played"] += 1
                a["played"] += 1
                h["points_for"] += (m.home_score or 0)
                h["points_against"] += (m.away_score or 0)
                a["points_for"] += (m.away_score or 0)
                a["points_against"] += (m.home_score or 0)

                if m.winner_team_id == m.home_team_id:
                    h["won"] += 1
                    h["points"] += 2
                    a["lost"] += 1
                    a["points"] += 1
                else:
                    a["won"] += 1
                    a["points"] += 2
                    h["lost"] += 1
                    h["points"] += 1

        for s in stats.values():
            s["points_diff"] = s["points_for"] - s["points_against"]

        # 排序：总积分从高到低 -> 净胜分 -> 总得分
        sorted_list = sorted(stats.values(), key=lambda item: (item["points"], item["points_diff"], item["points_for"]), reverse=True)
        for idx, item in enumerate(sorted_list):
            item["rank"] = idx + 1
        return sorted_list

    return {
        "group_a": calculate_group("A"),
        "group_b": calculate_group("B"),
    }


@router.post("/sports-teacher/basketball/advance-to-finals")
def basketball_advance_to_finals(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    standings = basketball_standings(event_id, db=db)
    group_a = standings["group_a"]
    group_b = standings["group_b"]

    if len(group_a) < 2 or len(group_b) < 2:
        raise HTTPException(400, "A组和B组各自至少需有2支队伍决出前两名")

    a1 = group_a[0]["team_id"]
    a2 = group_a[1]["team_id"]
    b1 = group_b[0]["team_id"]
    b2 = group_b[1]["team_id"]

    # 清空旧的淘汰赛对阵
    old_playoffs = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type.in_(["SEMIFINAL", "THIRD_PLACE", "FINAL"]))))
    for m in old_playoffs:
        db.delete(m)
    db.flush()

    # 创建 半决赛1: A1 vs B2
    sf1 = TournamentMatch(
        event_id=event_id,
        stage_type="SEMIFINAL",
        match_code="SF1",
        match_name="半决赛第1场 (A组第1 vs B组第2)",
        home_team_id=a1,
        away_team_id=b2,
        status="NOT_STARTED",
        court_venue="篮球主馆",
    )
    # 创建 半决赛2: B1 vs A2
    sf2 = TournamentMatch(
        event_id=event_id,
        stage_type="SEMIFINAL",
        match_code="SF2",
        match_name="半决赛第2场 (B组第1 vs A组第2)",
        home_team_id=b1,
        away_team_id=a2,
        status="NOT_STARTED",
        court_venue="篮球主馆",
    )
    db.add(sf1)
    db.add(sf2)
    db.commit()

    return {"message": "已依据小组积分榜（胜2分负1分）提取 A1, A2, B1, B2 生成第二阶段半决赛", "sf1_teams": [a1, b2], "sf2_teams": [b1, a2]}


@router.post("/sports-teacher/basketball/generate-finals")
def basketball_generate_finals(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    sf_matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type == "SEMIFINAL")))
    if len(sf_matches) < 2 or any(m.status != "FINISHED" for m in sf_matches):
        raise HTTPException(400, "请先录入两场半决赛的比分并完赛，才能生成决赛与三四名赛")

    sf1 = next(m for m in sf_matches if m.match_code == "SF1")
    sf2 = next(m for m in sf_matches if m.match_code == "SF2")

    # 清空旧决赛
    old_finals = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type.in_(["THIRD_PLACE", "FINAL"]))))
    for m in old_finals:
        db.delete(m)
    db.flush()

    # 三四名季军赛：半决赛负者
    third_place = TournamentMatch(
        event_id=event_id,
        stage_type="THIRD_PLACE",
        match_code="3RD",
        match_name="季军争夺赛 (第3、4名决赛)",
        home_team_id=sf1.loser_team_id,
        away_team_id=sf2.loser_team_id,
        status="NOT_STARTED",
        court_venue="篮球主馆",
    )
    # 冠亚军总决赛：半决赛胜者
    championship = TournamentMatch(
        event_id=event_id,
        stage_type="FINAL",
        match_code="FINAL",
        match_name="冠亚军总决赛 (争夺全国第1、2名)",
        home_team_id=sf1.winner_team_id,
        away_team_id=sf2.winner_team_id,
        status="NOT_STARTED",
        court_venue="篮球主馆",
    )
    db.add(third_place)
    db.add(championship)
    db.commit()

    return {"message": "已生成冠亚军总决赛及三四名季军赛对阵"}


@router.post("/sports-teacher/basketball/finalize-results")
def basketball_finalize_results(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_score")

    final_match = db.scalar(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type == "FINAL"))
    third_match = db.scalar(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type == "THIRD_PLACE"))

    if not final_match or final_match.status != "FINISHED" or not third_match or third_match.status != "FINISHED":
        raise HTTPException(400, "冠亚军总决赛和三四名决赛均已完赛后方可定稿前四名成绩")

    # 1st ~ 4th
    rankings = [
        (1, final_match.winner_team_id, final_match.home_score if final_match.winner_team_id == final_match.home_team_id else final_match.away_score),
        (2, final_match.loser_team_id, final_match.away_score if final_match.winner_team_id == final_match.home_team_id else final_match.home_score),
        (3, third_match.winner_team_id, third_match.home_score if third_match.winner_team_id == third_match.home_team_id else third_match.away_score),
        (4, third_match.loser_team_id, third_match.away_score if third_match.winner_team_id == third_match.home_team_id else third_match.home_score),
    ]

    rounds = list(db.scalars(select(EventRound).where(EventRound.event_id == event_id).order_by(EventRound.sequence.desc())))
    target_round = rounds[0] if rounds else None

    # 获取或计算计分模型
    scoring_model = db.get(ScoringModel, event.scoring_model_id) if event.scoring_model_id else None
    multiplier = event.points_multiplier or Decimal("2.0")

    # 默认名次基础分（第1名9, 第2名7, 第3名6, 第4名5）
    default_base_points = {1: Decimal("9"), 2: Decimal("7"), 3: Decimal("6"), 4: Decimal("5")}

    for rank, team_id, score_val in rankings:
        reg = db.scalar(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id == team_id))
        if not reg:
            continue
        res = db.scalar(select(Result).where(Result.event_id == event_id, Result.registration_id == reg.id))
        if not res:
            res = Result(event_id=event_id, round_id=target_round.id if target_round else reg.round_id, registration_id=reg.id)
            db.add(res)
        res.rank = rank
        res.raw_value = Decimal(score_val or 0)
        res.competition_status = "NORMAL"
        res.state = ResultState.REVIEWED  # 自动进入终审就绪状态
        base_p = default_base_points.get(rank, Decimal("0"))
        res.points = base_p * multiplier
        res.finalized_by_id = user.id
        res.finalized_at = utcnow()

    db.commit()
    return {"message": "已成功将前四名排名与团体积分归档至成绩公布台，可一键终审发布大屏！"}


@router.get("/public/basketball")
def public_basketball(event_id: int | None = None, meet_id: int | None = None, db: Session = Depends(get_db)):
    # 若未指定，查询第一个篮球或团体球类赛
    if not event_id:
        stmt = select(Event).where(Event.event_type.in_(["TEAM", "BALL"]), or_(Event.name.contains("篮球"), Event.name.contains("球")))
        if meet_id:
            stmt = stmt.where(Event.meet_id == meet_id)
        b_event = db.scalar(stmt)
        if not b_event:
            fallback = select(Event).where(Event.event_type == "TEAM")
            if meet_id:
                fallback = fallback.where(Event.meet_id == meet_id)
            b_event = db.scalar(fallback)
        if not b_event:
            return {"has_tournament": False}
        event_id = b_event.id

    event = db.get(Event, event_id)
    matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id).order_by(TournamentMatch.id)))
    standings = basketball_standings(event_id, db=db)
    return {
        "has_tournament": True,
        "event_id": event.id,
        "event_name": event.name,
        "standings": standings,
        "matches": [_match_dict(db, m) for m in matches],
    }


# ==============================================================================
# 🏐 排球赛事模块 (Volleyball Tournament Multi-stage & Scoring Engine)
# ==============================================================================

@router.get("/sports-teacher/volleyball/teams")
def volleyball_teams(event_id: int | None = None, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    stmt = select(CollegeTeam)
    if event_id:
        event = db.get(Event, event_id)
        if event:
            stmt = stmt.where(CollegeTeam.meet_id == event.meet_id, or_(CollegeTeam.event_id == event_id, CollegeTeam.event_id.is_(None)))
    all_teams = list(db.scalars(stmt.order_by(CollegeTeam.college, CollegeTeam.team_name)))
    registered_teams = []
    registered_team_ids = []
    if event_id:
        regs = list(db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id.is_not(None))))
        registered_team_ids = [r.college_team_id for r in regs]
        for r in regs:
            t = db.get(CollegeTeam, r.college_team_id)
            if t:
                members = list(db.scalars(select(CollegeTeamMember).where(CollegeTeamMember.team_id == t.id)))
                male_c = 0
                female_c = 0
                for m in members:
                    s = db.get(StudentRoster, m.student_id)
                    if s and s.gender == "女":
                        female_c += 1
                    elif s and s.gender == "男":
                        male_c += 1
                registered_teams.append({
                    "registration_id": r.id,
                    "team_id": t.id,
                    "college": t.college,
                    "team_name": t.team_name,
                    "group_tag": r.group_tag or "未分组",
                    "status": r.status,
                    "member_count": len(members),
                    "male_count": male_c,
                    "female_count": female_c,
                    "female_rule_passed": female_c >= 2,
                    "female_rule_tip": "女生已达标（≥2人）" if female_c >= 2 else f"女生不足2人（当前{female_c}人）",
                })
    return {
        "registered_teams": registered_teams,
        "registered_team_ids": registered_team_ids,
        "all_available_teams": [{"id": t.id, "college": t.college, "team_name": t.team_name} for t in all_teams],
    }


@router.post("/sports-teacher/volleyball/quick-create-event")
def volleyball_quick_create_event(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    meet_id = data.get("meet_id")
    if not meet_id:
        meet = db.scalar(select(SportsMeet).order_by(SportsMeet.id.desc()))
        if not meet:
            raise HTTPException(400, "请先在【赛事与项目】中创建运动会赛事")
        meet_id = meet.id

    name = data.get("name", "男女混合排球赛")
    code = data.get("code", f"VB_{int(datetime.now().timestamp()) % 10000}")
    gender = data.get("gender_group", "MIXED")

    existing = db.scalar(select(Event).where(Event.meet_id == meet_id, Event.code == code))
    if existing:
        code = f"{code}_{int(datetime.now().timestamp()) % 100}"

    vb_model = db.scalar(select(ScoringModel).where(ScoringModel.name.contains("排球")))
    model_id = vb_model.id if vb_model else None

    event = Event(
        meet_id=meet_id,
        code=code,
        name=name,
        gender_group=gender,
        participant_group="STUDENT",
        event_type="TEAM",
        result_unit="分",
        sort_direction="DESC",
        stage="FINAL",
        qualification_count=0,
        scoring_places=4,
        points_multiplier=Decimal("2.0"),
        scoring_model_id=model_id,
    )
    db.add(event)
    db.flush()

    round_row = EventRound(event_id=event.id, name="决赛", stage="FINAL", sequence=1, qualification_count=0)
    db.add(round_row)

    perm = EventAdminPermission(
        user_id=user.id,
        event_id=event.id,
        can_schedule=True,
        can_score=True,
        can_review=True,
        can_export=True,
        assigned_by_id=user.id,
    )
    db.add(perm)
    db.commit()

    return {"message": f"成功创建【{name}】赛事，已自动配置排球三局两胜规程及计分模型！", "event": {"id": event.id, "name": event.name, "event_type": event.event_type}}


@router.post("/sports-teacher/volleyball/add-teams")
def volleyball_add_teams(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    event_id = data.get("event_id")
    team_ids = data.get("team_ids", [])
    if not event_id:
        raise HTTPException(400, "请指定排球比赛项目 ID")
    if not team_ids:
        raise HTTPException(400, "请至少勾选一支学院代表队")

    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    rounds = list(db.scalars(select(EventRound).where(EventRound.event_id == event_id).order_by(EventRound.sequence)))
    target_round_id = rounds[0].id if rounds else None
    if not target_round_id:
        round_row = EventRound(event_id=event.id, name="决赛", stage="FINAL", sequence=1, qualification_count=0)
        db.add(round_row)
        db.flush()
        target_round_id = round_row.id

    added_count = 0
    for tid in team_ids:
        existing = db.scalar(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id == tid))
        if not existing:
            reg = Registration(
                event_id=event_id,
                round_id=target_round_id,
                college_team_id=tid,
                status="REGISTERED",
            )
            db.add(reg)
            added_count += 1

    db.commit()
    return {"message": f"成功为【{event.name}】添加 {added_count} 支排球参赛代表队！", "added_count": added_count}


@router.post("/sports-teacher/volleyball/groups/auto-generate")
def volleyball_generate_groups(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    registrations = list(db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id.is_not(None))))
    if len(registrations) < 4:
        raise HTTPException(400, "排球分组单循环赛至少需要 4 支学院代表队")

    female_violations = []
    for reg in registrations:
        team = db.get(CollegeTeam, reg.college_team_id)
        if not team:
            continue
        members = list(db.scalars(select(CollegeTeamMember).where(CollegeTeamMember.team_id == team.id)))
        female_count = 0
        for m in members:
            s = db.get(StudentRoster, m.student_id)
            if s and s.gender == "女":
                female_count += 1
        if female_count < 2:
            female_violations.append(f"{team.team_name}(当前女生{female_count}人)")

    if female_violations and not data.get("ignore_gender_warning", False):
        tip = "、".join(female_violations)
        raise HTTPException(400, f"依据《排球竞赛规则》，比赛上场队员要求女生不能低于两人。以下队伍未达标：{tip}。请先在【名单录入】中为代表队添加女生队员！")

    a_team_ids = data.get("a_team_ids")
    b_team_ids = data.get("b_team_ids")

    if not a_team_ids or not b_team_ids:
        all_team_ids = [r.college_team_id for r in registrations]
        half = (len(all_team_ids) + 1) // 2
        a_team_ids = all_team_ids[:half]
        b_team_ids = all_team_ids[half:]

    for reg in registrations:
        if reg.college_team_id in a_team_ids:
            reg.group_tag = "A"
            reg.heat = "A组"
        elif reg.college_team_id in b_team_ids:
            reg.group_tag = "B"
            reg.heat = "B组"

    old_matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type.in_(["GROUP_A", "GROUP_B"]))))
    for m in old_matches:
        db.delete(m)
    db.flush()

    created_matches = 0
    for i in range(len(a_team_ids)):
        for j in range(i + 1, len(a_team_ids)):
            t1, t2 = a_team_ids[i], a_team_ids[j]
            m = TournamentMatch(
                event_id=event_id,
                stage_type="GROUP_A",
                match_code=f"VB_A_{i+1}-{j+1}",
                match_name=f"A组排球循环赛第{created_matches+1}场",
                home_team_id=t1,
                away_team_id=t2,
                status="NOT_STARTED",
                court_venue="排球馆1号场",
            )
            db.add(m)
            created_matches += 1

    b_count = 0
    for i in range(len(b_team_ids)):
        for j in range(i + 1, len(b_team_ids)):
            t1, t2 = b_team_ids[i], b_team_ids[j]
            m = TournamentMatch(
                event_id=event_id,
                stage_type="GROUP_B",
                match_code=f"VB_B_{i+1}-{j+1}",
                match_name=f"B组排球循环赛第{b_count+1}场",
                home_team_id=t1,
                away_team_id=t2,
                status="NOT_STARTED",
                court_venue="排球馆2号场",
            )
            db.add(m)
            b_count += 1
            created_matches += 1

    db.commit()
    return {"message": f"排球 A/B 组抽签成功，生成 {created_matches} 场三局两胜单循环赛程！", "a_count": len(a_team_ids), "b_count": len(b_team_ids)}


@router.get("/sports-teacher/volleyball/matches")
def volleyball_matches(event_id: int, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id).order_by(TournamentMatch.id)))
    return [_match_dict(db, m) for m in matches]


@router.put("/sports-teacher/volleyball/matches/{match_id}")
def volleyball_update_match(match_id: int, data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    match = db.get(TournamentMatch, match_id)
    if not match:
        raise HTTPException(404, "排球对阵比赛不存在")
    require_event_permission(db, user, match.event_id, "can_score")

    is_forfeit = data.get("is_forfeit", False)
    forfeit_team_id = data.get("forfeit_team_id")

    if is_forfeit or forfeit_team_id:
        f_tid = forfeit_team_id or match.away_team_id
        if f_tid not in {match.home_team_id, match.away_team_id}:
            f_tid = match.away_team_id
        winner_id = match.away_team_id if f_tid == match.home_team_id else match.home_team_id
        match.forfeit_team_id = f_tid
        match.winner_team_id = winner_id
        match.loser_team_id = f_tid
        match.home_score = 2 if winner_id == match.home_team_id else 0
        match.away_score = 0 if winner_id == match.home_team_id else 2
        match.sets_detail = [
            {"set": 1, "home": 25 if winner_id == match.home_team_id else 0, "away": 0 if winner_id == match.home_team_id else 25},
            {"set": 2, "home": 25 if winner_id == match.home_team_id else 0, "away": 0 if winner_id == match.home_team_id else 25},
        ]
        match.status = "FINISHED"
        w_team = db.get(CollegeTeam, winner_id)
        match.notes = data.get("notes") or f"（因一方迟到超过15分钟判弃权，{w_team.team_name if w_team else '获胜方'} 2:0 获胜）"
    else:
        sets_detail = data.get("sets_detail")
        home_score = data.get("home_score")
        away_score = data.get("away_score")

        if sets_detail and isinstance(sets_detail, list):
            home_sets_won = 0
            away_sets_won = 0
            formatted_sets = []
            for idx, s in enumerate(sets_detail, 1):
                h_pts = int(s.get("home", 0))
                a_pts = int(s.get("away", 0))
                if h_pts > a_pts:
                    home_sets_won += 1
                elif a_pts > h_pts:
                    away_sets_won += 1
                formatted_sets.append({"set": idx, "home": h_pts, "away": a_pts})
            
            if home_sets_won == away_sets_won:
                raise HTTPException(400, "三局两胜制必须决出胜负局，不能平局")
            if home_sets_won < 2 and away_sets_won < 2:
                raise HTTPException(400, "三局两胜制获胜方必须赢得 2 局（总比分应为 2:0 或 2:1）")
            
            match.sets_detail = formatted_sets
            match.home_score = home_sets_won
            match.away_score = away_sets_won
            match.winner_team_id = match.home_team_id if home_sets_won > away_sets_won else match.away_team_id
            match.loser_team_id = match.away_team_id if home_sets_won > away_sets_won else match.home_team_id
            match.forfeit_team_id = None
            match.status = "FINISHED"
        elif home_score is not None and away_score is not None:
            home_score = int(home_score)
            away_score = int(away_score)
            if (home_score, away_score) not in {(2, 0), (2, 1), (1, 2), (0, 2)}:
                raise HTTPException(400, "排球采取三局两胜制，局大比分只能为 2:0, 2:1, 1:2, 0:2")
            match.home_score = home_score
            match.away_score = away_score
            match.winner_team_id = match.home_team_id if home_score > away_score else match.away_team_id
            match.loser_team_id = match.away_team_id if home_score > away_score else match.home_team_id
            match.forfeit_team_id = None
            match.status = "FINISHED"

    if "court_venue" in data:
        match.court_venue = data["court_venue"]
    if "match_time" in data and data["match_time"]:
        match.match_time = datetime.fromisoformat(data["match_time"].replace("Z", ""))
    if "notes" in data and data["notes"]:
        match.notes = data["notes"]

    db.commit()
    return {"message": "排球比分已录入并更新胜负与积分！", "match": _match_dict(db, match)}


@router.get("/sports-teacher/volleyball/standings")
def volleyball_standings(event_id: int, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type.in_(["GROUP_A", "GROUP_B"]))))
    registrations = list(db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id.is_not(None))))

    def calculate_group(group_letter: str):
        group_regs = [r for r in registrations if r.group_tag == group_letter]
        group_team_ids = [r.college_team_id for r in group_regs]
        group_matches = [m for m in matches if m.stage_type == f"GROUP_{group_letter}"]

        stats = {
            tid: {
                "team_id": tid,
                "team_name": db.get(CollegeTeam, tid).team_name if db.get(CollegeTeam, tid) else "队伍",
                "college": db.get(CollegeTeam, tid).college if db.get(CollegeTeam, tid) else "学院",
                "played": 0,
                "won": 0,
                "lost": 0,
                "won_2_0": 0,
                "won_2_1": 0,
                "lost_1_2": 0,
                "lost_0_2": 0,
                "forfeited": 0,
                "points": 0,          # 胜4分，负(1:2)2分，负(0:2)1分，弃权0分
                "sets_won": 0,        # 胜局数
                "sets_lost": 0,       # 负局数
                "set_diff": 0,        # 净胜局
                "set_ratio": 0.0,     # C值 (胜局 / 负局)
                "points_for": 0,      # 总得分数
                "points_against": 0,  # 总失分数
                "point_diff": 0,      # 净胜得分
                "point_ratio": 0.0,   # Z值 (总得分 / 总失分)
            }
            for tid in group_team_ids
        }

        for m in group_matches:
            if m.status == "FINISHED" and m.home_team_id in stats and m.away_team_id in stats:
                h = stats[m.home_team_id]
                a = stats[m.away_team_id]
                h["played"] += 1
                a["played"] += 1

                h_sets = m.home_score if m.home_score is not None else 0
                a_sets = m.away_score if m.away_score is not None else 0
                h["sets_won"] += h_sets
                h["sets_lost"] += a_sets
                a["sets_won"] += a_sets
                a["sets_lost"] += h_sets

                if m.sets_detail:
                    for s in m.sets_detail:
                        hp = s.get("home", 0)
                        ap = s.get("away", 0)
                        h["points_for"] += hp
                        h["points_against"] += ap
                        a["points_for"] += ap
                        a["points_against"] += hp
                else:
                    h["points_for"] += h_sets * 25
                    h["points_against"] += a_sets * 25
                    a["points_for"] += a_sets * 25
                    a["points_against"] += h_sets * 25

                if m.forfeit_team_id:
                    if m.forfeit_team_id == m.home_team_id:
                        h["forfeited"] += 1
                        h["lost"] += 1
                        a["won"] += 1
                        a["won_2_0"] += 1
                        a["points"] += 4
                    else:
                        a["forfeited"] += 1
                        a["lost"] += 1
                        h["won"] += 1
                        h["won_2_0"] += 1
                        h["points"] += 4
                elif m.winner_team_id == m.home_team_id:
                    h["won"] += 1
                    h["points"] += 4
                    a["lost"] += 1
                    if a_sets == 1:
                        h["won_2_1"] += 1
                        a["lost_1_2"] += 1
                        a["points"] += 2
                    else:
                        h["won_2_0"] += 1
                        a["lost_0_2"] += 1
                        a["points"] += 1
                else:
                    a["won"] += 1
                    a["points"] += 4
                    h["lost"] += 1
                    if h_sets == 1:
                        a["won_2_1"] += 1
                        h["lost_1_2"] += 1
                        h["points"] += 2
                    else:
                        a["won_2_0"] += 1
                        h["lost_0_2"] += 1
                        h["points"] += 1

        for s in stats.values():
            s["set_diff"] = s["sets_won"] - s["sets_lost"]
            s["point_diff"] = s["points_for"] - s["points_against"]
            s["set_ratio"] = round(s["sets_won"] / s["sets_lost"], 4) if s["sets_lost"] > 0 else (s["sets_won"] * 100.0)
            s["point_ratio"] = round(s["points_for"] / s["points_against"], 4) if s["points_against"] > 0 else (s["points_for"] * 100.0)

        sorted_list = sorted(stats.values(), key=lambda item: (item["points"], item["set_ratio"], item["point_ratio"], item["point_diff"]), reverse=True)
        for idx, item in enumerate(sorted_list):
            item["rank"] = idx + 1
        return sorted_list

    return {
        "group_a": calculate_group("A"),
        "group_b": calculate_group("B"),
    }


@router.post("/sports-teacher/volleyball/advance-to-finals")
def volleyball_advance_to_finals(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    standings = volleyball_standings(event_id, db=db)
    group_a = standings["group_a"]
    group_b = standings["group_b"]

    if len(group_a) < 2 or len(group_b) < 2:
        raise HTTPException(400, "A组和B组各自至少需有2支队伍决出前两名")

    a1 = group_a[0]["team_id"]
    a2 = group_a[1]["team_id"]
    b1 = group_b[0]["team_id"]
    b2 = group_b[1]["team_id"]

    old_playoffs = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type.in_(["SEMIFINAL", "THIRD_PLACE", "FINAL"]))))
    for m in old_playoffs:
        db.delete(m)
    db.flush()

    sf1 = TournamentMatch(
        event_id=event_id,
        stage_type="SEMIFINAL",
        match_code="VB_SF1",
        match_name="排球半决赛第1场 (A组第1 vs B组第2)",
        home_team_id=a1,
        away_team_id=b2,
        status="NOT_STARTED",
        court_venue="排球主馆",
    )
    sf2 = TournamentMatch(
        event_id=event_id,
        stage_type="SEMIFINAL",
        match_code="VB_SF2",
        match_name="排球半决赛第2场 (B组第1 vs A组第2)",
        home_team_id=b1,
        away_team_id=a2,
        status="NOT_STARTED",
        court_venue="排球主馆",
    )
    db.add(sf1)
    db.add(sf2)
    db.commit()

    return {"message": "已依据排球小组积分榜（胜4分，1:2负2分，0:2负1分）提取 A1, A2, B1, B2 生成第二阶段交叉半决赛！", "sf1_teams": [a1, b2], "sf2_teams": [b1, a2]}


@router.post("/sports-teacher/volleyball/generate-finals")
def volleyball_generate_finals(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    sf_matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type == "SEMIFINAL")))
    if len(sf_matches) < 2 or any(m.status != "FINISHED" for m in sf_matches):
        raise HTTPException(400, "请先录入两场排球半决赛的比分并完赛，才能生成决赛与季军赛")

    sf1 = next(m for m in sf_matches if m.match_code in ["VB_SF1", "SF1"])
    sf2 = next(m for m in sf_matches if m.match_code in ["VB_SF2", "SF2"])

    old_finals = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type.in_(["THIRD_PLACE", "FINAL"]))))
    for m in old_finals:
        db.delete(m)
    db.flush()

    third_place = TournamentMatch(
        event_id=event_id,
        stage_type="THIRD_PLACE",
        match_code="VB_3RD",
        match_name="排球季军争夺赛 (第3、4名决赛)",
        home_team_id=sf1.loser_team_id,
        away_team_id=sf2.loser_team_id,
        status="NOT_STARTED",
        court_venue="排球主馆",
    )
    championship = TournamentMatch(
        event_id=event_id,
        stage_type="FINAL",
        match_code="VB_FINAL",
        match_name="排球冠亚军总决赛 (争夺全国第1、2名)",
        home_team_id=sf1.winner_team_id,
        away_team_id=sf2.winner_team_id,
        status="NOT_STARTED",
        court_venue="排球主馆",
    )
    db.add(third_place)
    db.add(championship)
    db.commit()

    return {"message": "已生成排球冠亚军总决赛及三四名季军赛对阵！"}


@router.post("/sports-teacher/volleyball/finalize-results")
def volleyball_finalize_results(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_score")

    final_match = db.scalar(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type == "FINAL"))
    third_match = db.scalar(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type == "THIRD_PLACE"))

    if not final_match or final_match.status != "FINISHED" or not third_match or third_match.status != "FINISHED":
        raise HTTPException(400, "排球冠亚军总决赛和三四名决赛均已完赛后方可定稿前四名成绩")

    rankings = [
        (1, final_match.winner_team_id, final_match.home_score if final_match.winner_team_id == final_match.home_team_id else final_match.away_score),
        (2, final_match.loser_team_id, final_match.away_score if final_match.winner_team_id == final_match.home_team_id else final_match.home_score),
        (3, third_match.winner_team_id, third_match.home_score if third_match.winner_team_id == third_match.home_team_id else third_match.away_score),
        (4, third_match.loser_team_id, third_match.away_score if third_match.winner_team_id == third_match.home_team_id else third_match.home_score),
    ]

    rounds = list(db.scalars(select(EventRound).where(EventRound.event_id == event_id).order_by(EventRound.sequence.desc())))
    target_round = rounds[0] if rounds else None

    scoring_model = db.get(ScoringModel, event.scoring_model_id) if event.scoring_model_id else None
    multiplier = event.points_multiplier or Decimal("2.0")
    default_base_points = {1: Decimal("9"), 2: Decimal("7"), 3: Decimal("6"), 4: Decimal("5")}

    for rank, team_id, score_val in rankings:
        reg = db.scalar(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id == team_id))
        if not reg:
            continue
        res = db.scalar(select(Result).where(Result.event_id == event_id, Result.registration_id == reg.id))
        if not res:
            res = Result(event_id=event_id, round_id=target_round.id if target_round else reg.round_id, registration_id=reg.id)
            db.add(res)
        res.rank = rank
        res.raw_value = Decimal(score_val or 0)
        res.competition_status = "NORMAL"
        res.state = ResultState.REVIEWED
        base_p = default_base_points.get(rank, Decimal("0"))
        res.points = base_p * multiplier
        res.finalized_by_id = user.id
        res.finalized_at = utcnow()

    db.commit()
    return {"message": "已成功将排球前四名排名与团体积分归档至成绩公布台，可一键终审发布大屏！"}


@router.get("/public/volleyball")
def public_volleyball(event_id: int | None = None, meet_id: int | None = None, db: Session = Depends(get_db)):
    if not event_id:
        stmt = select(Event).where(Event.event_type.in_(["TEAM", "BALL"]), Event.name.contains("排球"))
        if meet_id:
            stmt = stmt.where(Event.meet_id == meet_id)
        v_event = db.scalar(stmt)
        if not v_event:
            return {"has_tournament": False}
        event_id = v_event.id

    event = db.get(Event, event_id)
    matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id).order_by(TournamentMatch.id)))
    standings = volleyball_standings(event_id, db=db)
    return {
        "has_tournament": True,
        "event_id": event.id,
        "event_name": event.name,
        "standings": standings,
        "matches": [_match_dict(db, m) for m in matches],
    }


# ==============================================================================
# 🏓 乒乓球赛事模块 (Table Tennis Tournament Engine: Mixed Team & Singles)
# ==============================================================================

@router.get("/sports-teacher/table-tennis/team/status")
def table_tennis_team_status(event_id: int | None = None, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    """获取学院代表队在乒乓球混合团体赛中的名单配置与 3男2女 规则达标情况"""
    all_teams = list(db.scalars(select(CollegeTeam).order_by(CollegeTeam.college)))
    registered_team_ids = []
    if event_id:
        regs = list(db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id.is_not(None))))
        registered_team_ids = [r.college_team_id for r in regs]

    results = []
    for team in all_teams:
        members = list(db.scalars(select(CollegeTeamMember).where(CollegeTeamMember.team_id == team.id)))
        male_count = 0
        female_count = 0
        member_list = []
        for m in members:
            s = db.get(StudentRoster, m.student_id)
            if s:
                if s.gender == "男":
                    male_count += 1
                elif s.gender == "女":
                    female_count += 1
                member_list.append({
                    "id": m.id,
                    "student_id": s.id,
                    "name": s.name,
                    "gender": s.gender,
                    "student_no": s.student_no,
                    "role_title": m.role_title,
                })
        # 规程要求：混合团体赛各学院需要上报 3男、2女
        passed = (male_count >= 3 and female_count >= 2)
        tip = f"当前男{male_count}人、女{female_count}人"
        if not passed:
            tip += " (需至少3男2女)"
        else:
            tip += " (符合3男2女要求)"

        reg_row = db.scalar(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id == team.id)) if event_id else None
        results.append({
            "team_id": team.id,
            "college": team.college,
            "team_name": team.team_name,
            "is_registered": team.id in registered_team_ids,
            "group_tag": reg_row.group_tag if reg_row else None,
            "male_count": male_count,
            "female_count": female_count,
            "total_count": len(members),
            "rule_passed": passed,
            "rule_tip": tip,
            "members": member_list,
        })

    all_passed = all(item["rule_passed"] for item in results if item["is_registered"]) if registered_team_ids else False
    return {
        "teams": results,
        "registered_team_ids": registered_team_ids,
        "all_compliant": all_passed,
    }


@router.post("/sports-teacher/table-tennis/quick-create-event")
def table_tennis_quick_create_event(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    """快速创建乒乓球赛制项目（混合团体赛、男子单打、女子单打）"""
    meet_id = data.get("meet_id")
    if not meet_id:
        meet = db.scalar(select(SportsMeet).order_by(SportsMeet.id.desc()))
        if not meet:
            raise HTTPException(400, "当前系统中尚无运动会，请先创建运动会")
        meet_id = meet.id

    category = data.get("category", "TEAM")  # TEAM (混合团体), MS (男单), WS (女单)
    if category == "TEAM":
        name = data.get("name", "乒乓球混合团体赛")
        code = data.get("code", f"TT_TEAM_{int(datetime.now().timestamp()) % 1000}")
        gender = "MIXED"
        event_type = "TEAM"
        places = 4
        multiplier = Decimal("2.0")
        model = db.scalar(select(ScoringModel).where(ScoringModel.name.contains("乒乓球混合团体")))
    elif category == "MS":
        name = data.get("name", "男子乒乓球单打")
        code = data.get("code", f"TT_MS_{int(datetime.now().timestamp()) % 1000}")
        gender = "MALE"
        event_type = "INDIVIDUAL"
        places = 8
        multiplier = Decimal("1.0")
        model = db.scalar(select(ScoringModel).where(ScoringModel.name.contains("乒乓球单打")))
    else:
        name = data.get("name", "女子乒乓球单打")
        code = data.get("code", f"TT_WS_{int(datetime.now().timestamp()) % 1000}")
        gender = "FEMALE"
        event_type = "INDIVIDUAL"
        places = 8
        multiplier = Decimal("1.0")
        model = db.scalar(select(ScoringModel).where(ScoringModel.name.contains("乒乓球单打")))

    # 检查 code 是否重复
    if db.scalar(select(Event).where(Event.meet_id == meet_id, Event.code == code)):
        code = f"{code}_{int(datetime.now().timestamp()) % 100}"

    event = Event(
        meet_id=meet_id,
        code=code,
        name=name,
        gender_group=gender,
        participant_group="STUDENT",
        event_type=event_type,
        result_unit="分",
        sort_direction="DESC",
        stage="FINAL",
        qualification_count=0,
        scoring_places=places,
        points_multiplier=multiplier,
        scoring_model_id=model.id if model else None,
    )
    db.add(event)
    db.flush()

    round_row = EventRound(event_id=event.id, name="决赛", stage="FINAL", sequence=1, qualification_count=0)
    db.add(round_row)

    perm = EventAdminPermission(
        user_id=user.id,
        event_id=event.id,
        can_schedule=True,
        can_score=True,
        can_review=True,
        can_export=True,
        assigned_by_id=user.id,
    )
    db.add(perm)
    db.commit()

    return {"message": f"成功创建【{name}】比赛项目！", "event": {"id": event.id, "name": event.name, "category": category}}


@router.post("/sports-teacher/table-tennis/team/add-teams")
def table_tennis_team_add_teams(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    """向乒乓球混合团体赛添加参赛学院代表队"""
    event_id = data.get("event_id")
    team_ids = data.get("team_ids", [])
    if not event_id:
        raise HTTPException(400, "请指定比赛项目 ID")
    if not team_ids:
        raise HTTPException(400, "请至少勾选一支学院代表队")

    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    rounds = list(db.scalars(select(EventRound).where(EventRound.event_id == event_id).order_by(EventRound.sequence)))
    target_round_id = rounds[0].id if rounds else 1

    added_count = 0
    for tid in team_ids:
        existing = db.scalar(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id == tid))
        if not existing:
            reg = Registration(
                event_id=event_id,
                round_id=target_round_id,
                college_team_id=tid,
                status="REGISTERED",
            )
            db.add(reg)
            added_count += 1

    db.commit()
    return {"message": f"成功为【{event.name}】添加 {added_count} 支参赛代表队！", "added_count": added_count}


@router.get("/sports-teacher/table-tennis/team/teams")
def table_tennis_team_teams(event_id: int, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    """获取混合团体赛已报名参赛队伍列表及所有可用学院代表队"""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    all_teams = list(db.scalars(select(CollegeTeam).where(CollegeTeam.meet_id == event.meet_id, or_(CollegeTeam.event_id == event_id, CollegeTeam.event_id.is_(None))).order_by(CollegeTeam.college, CollegeTeam.team_name)))
    registered_regs = list(db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id.is_not(None))))
    registered_team_ids = [r.college_team_id for r in registered_regs]
    registered_teams = []
    for tid in registered_team_ids:
        t = db.get(CollegeTeam, tid)
        if t:
            members = list(db.scalars(select(CollegeTeamMember).where(CollegeTeamMember.team_id == t.id)))
            male_c = sum(1 for m in members if db.get(StudentRoster, m.student_id) and db.get(StudentRoster, m.student_id).gender == "男")
            female_c = sum(1 for m in members if db.get(StudentRoster, m.student_id) and db.get(StudentRoster, m.student_id).gender == "女")
            registered_teams.append({
                "id": t.id,
                "college": t.college,
                "team_name": t.team_name,
                "male_count": male_c,
                "female_count": female_c,
                "compliant": male_c >= 3 and female_c >= 2,
            })
    return {
        "registered_teams": registered_teams,
        "registered_team_ids": registered_team_ids,
        "all_available_teams": [{"id": t.id, "college": t.college, "team_name": t.team_name} for t in all_teams],
    }


def _default_team_rubbers(db: Session, home_team_id: int | None, away_team_id: int | None) -> list:
    """初始化混合团体赛 5 盘对阵结构：男单1 ➔ 女单1 ➔ 男单2 ➔ 女单2 ➔ 男单3"""
    home_males = []
    home_females = []
    away_males = []
    away_females = []

    if home_team_id:
        for m in db.scalars(select(CollegeTeamMember).where(CollegeTeamMember.team_id == home_team_id)):
            s = db.get(StudentRoster, m.student_id)
            if s:
                if s.gender == "男":
                    home_males.append(s.name)
                else:
                    home_females.append(s.name)

    if away_team_id:
        for m in db.scalars(select(CollegeTeamMember).where(CollegeTeamMember.team_id == away_team_id)):
            s = db.get(StudentRoster, m.student_id)
            if s:
                if s.gender == "男":
                    away_males.append(s.name)
                else:
                    away_females.append(s.name)

    rubbers = [
        {"order": 1, "type": "MALE_SINGLES", "name": "第1盘 · 男单1", "home_player": home_males[0] if len(home_males) > 0 else "主队男选手1", "away_player": away_males[0] if len(away_males) > 0 else "客队男选手1", "home_score": 0, "away_score": 0, "sets": [{"set": 1, "home": 11, "away": 8}, {"set": 2, "home": 11, "away": 9}], "winner": None},
        {"order": 2, "type": "FEMALE_SINGLES", "name": "第2盘 · 女单1", "home_player": home_females[0] if len(home_females) > 0 else "主队女选手1", "away_player": away_females[0] if len(away_females) > 0 else "客队女选手1", "home_score": 0, "away_score": 0, "sets": [{"set": 1, "home": 11, "away": 7}, {"set": 2, "home": 11, "away": 6}], "winner": None},
        {"order": 3, "type": "MALE_SINGLES", "name": "第3盘 · 男单2", "home_player": home_males[1] if len(home_males) > 1 else (home_males[0] if home_males else "主队男选手2"), "away_player": away_males[1] if len(away_males) > 1 else (away_males[0] if away_males else "客队男选手2"), "home_score": 0, "away_score": 0, "sets": [{"set": 1, "home": 11, "away": 9}, {"set": 2, "home": 8, "away": 11}, {"set": 3, "home": 11, "away": 7}], "winner": None},
        {"order": 4, "type": "FEMALE_SINGLES", "name": "第4盘 · 女单2", "home_player": home_females[1] if len(home_females) > 1 else (home_females[0] if home_females else "主队女选手2"), "away_player": away_females[1] if len(away_females) > 1 else (away_females[0] if away_females else "客队女选手2"), "home_score": 0, "away_score": 0, "sets": [{"set": 1, "home": 11, "away": 9}, {"set": 2, "home": 11, "away": 8}], "winner": None},
        {"order": 5, "type": "MALE_SINGLES", "name": "第5盘 · 男单3", "home_player": home_males[2] if len(home_males) > 2 else (home_males[0] if home_males else "主队男选手3"), "away_player": away_males[2] if len(away_males) > 2 else (away_males[0] if away_males else "客队男选手3"), "home_score": 0, "away_score": 0, "sets": [{"set": 1, "home": 11, "away": 5}, {"set": 2, "home": 11, "away": 8}], "winner": None},
    ]
    return rubbers


@router.post("/sports-teacher/table-tennis/team/groups/auto-generate")
def table_tennis_team_generate_groups(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    """混合团体赛分组抽签（每组3支参赛队伍），并生成男/女/男/女/男打满五盘循环赛程"""
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    registrations = list(db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id.is_not(None))))
    if len(registrations) < 3:
        raise HTTPException(400, "乒乓球混合团体赛至少需要 3 支参赛队伍")

    # 3男2女达标校验
    violations = []
    for reg in registrations:
        team = db.get(CollegeTeam, reg.college_team_id)
        if not team:
            continue
        members = list(db.scalars(select(CollegeTeamMember).where(CollegeTeamMember.team_id == team.id)))
        m_cnt = sum(1 for m in members if db.get(StudentRoster, m.student_id) and db.get(StudentRoster, m.student_id).gender == "男")
        f_cnt = sum(1 for m in members if db.get(StudentRoster, m.student_id) and db.get(StudentRoster, m.student_id).gender == "女")
        if m_cnt < 3 or f_cnt < 2:
            violations.append(f"{team.team_name}(男{m_cnt}女{f_cnt}，要求3男2女)")

    if violations and not data.get("ignore_gender_warning", False):
        tip = "、".join(violations)
        raise HTTPException(400, f"依据《乒乓球竞赛规程》，混合团体赛各学院必须上报3男、2女队员。以下队伍未达标：{tip}。请先在名单中补充队员！")

    all_team_ids = [r.college_team_id for r in registrations]
    # 规程要求：每组 3 支队伍
    # 将队伍每 3 队一组，分配进 A、B、C... 组
    group_names = ["A", "B", "C", "D"]
    group_map = {}
    
    a_team_ids = data.get("a_team_ids")
    b_team_ids = data.get("b_team_ids")

    if a_team_ids and b_team_ids:
        group_map["A"] = a_team_ids
        group_map["B"] = b_team_ids
    else:
        for idx, tid in enumerate(all_team_ids):
            g_idx = idx // 3
            g_name = group_names[g_idx] if g_idx < len(group_names) else f"G{g_idx+1}"
            group_map.setdefault(g_name, []).append(tid)

    # 更新注册组别
    for reg in registrations:
        for g_name, t_ids in group_map.items():
            if reg.college_team_id in t_ids:
                reg.group_tag = g_name
                reg.heat = f"{g_name}组"

    # 清除旧的分组比赛
    old_matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type.startswith("GROUP_"))))
    for m in old_matches:
        db.delete(m)
    db.flush()

    created_count = 0
    court_idx = 1
    for g_name, t_ids in group_map.items():
        m_idx = 1
        for i in range(len(t_ids)):
            for j in range(i + 1, len(t_ids)):
                t1, t2 = t_ids[i], t_ids[j]
                rubbers = _default_team_rubbers(db, t1, t2)
                match = TournamentMatch(
                    event_id=event_id,
                    stage_type=f"GROUP_{g_name}",
                    match_code=f"{g_name}_{i+1}-{j+1}",
                    match_name=f"{g_name}组单循环第{m_idx}轮 (打满5场)",
                    home_team_id=t1,
                    away_team_id=t2,
                    status="NOT_STARTED",
                    court_venue=f"乒乓球馆{court_idx}号台",
                    best_of=3,
                    team_rubber_detail=rubbers,
                )
                db.add(match)
                created_count += 1
                m_idx += 1
        court_idx += 1

    db.commit()
    return {"message": f"成功完成乒乓球混合团体赛抽签分组（每组3队），生成 {created_count} 场打满5盘单循环赛程！", "groups": {k: len(v) for k, v in group_map.items()}}


@router.get("/sports-teacher/table-tennis/team/matches")
def table_tennis_team_matches(event_id: int, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id).order_by(TournamentMatch.id)))
    return [_match_dict(db, m) for m in matches]


@router.put("/sports-teacher/table-tennis/team/matches/{match_id}")
def table_tennis_team_update_match(match_id: int, data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    """录入混合团体赛单场比分（5 盘打满，胜一场积2分负积1分弃权0分）"""
    match = db.get(TournamentMatch, match_id)
    if not match:
        raise HTTPException(404, "对阵比赛不存在")
    require_event_permission(db, user, match.event_id, "can_score")

    is_forfeit = data.get("is_forfeit", False)
    forfeit_team_id = data.get("forfeit_team_id")

    if is_forfeit and forfeit_team_id:
        match.forfeit_team_id = int(forfeit_team_id)
        if match.forfeit_team_id == match.home_team_id:
            match.home_score = 0
            match.away_score = 5
            match.winner_team_id = match.away_team_id
            match.loser_team_id = match.home_team_id
        else:
            match.home_score = 5
            match.away_score = 0
            match.winner_team_id = match.home_team_id
            match.loser_team_id = match.away_team_id
        match.status = "FORFEIT"
    else:
        match.forfeit_team_id = None
        rubbers = data.get("team_rubber_detail", [])
        if not rubbers or len(rubbers) < 5:
            raise HTTPException(400, "混合团体赛必须打满五场（男单1、女单1、男单2、女单2、男单3）")

        home_rubber_wins = 0
        away_rubber_wins = 0
        for r in rubbers:
            h_score = int(r.get("home_score", 0))
            a_score = int(r.get("away_score", 0))
            if h_score > a_score:
                r["winner"] = "HOME"
                home_rubber_wins += 1
            elif a_score > h_score:
                r["winner"] = "AWAY"
                away_rubber_wins += 1

        match.team_rubber_detail = rubbers
        match.home_score = home_rubber_wins
        match.away_score = away_rubber_wins

        if home_rubber_wins > away_rubber_wins:
            match.winner_team_id = match.home_team_id
            match.loser_team_id = match.away_team_id
        elif away_rubber_wins > home_rubber_wins:
            match.winner_team_id = match.away_team_id
            match.loser_team_id = match.home_team_id
        match.status = "FINISHED"

    if "court_venue" in data:
        match.court_venue = data["court_venue"]
    if "match_time" in data and data["match_time"]:
        match.match_time = datetime.fromisoformat(data["match_time"].replace("Z", ""))
    if "notes" in data:
        match.notes = data["notes"]

    db.commit()
    return {"message": "比分已录入，乒乓球混合团体积分榜已实时更新（胜2分，负1分，弃权0分）！", "match": _match_dict(db, match)}


@router.get("/sports-teacher/table-tennis/team/standings")
def table_tennis_team_standings(event_id: int, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    """计算混合团体各小组积分榜，并智能遴选'成绩最好的小组第二名'"""
    matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type.startswith("GROUP_"))))
    registrations = list(db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id.is_not(None))))

    # 汇总各组
    group_tags = sorted(list({r.group_tag for r in registrations if r.group_tag}))
    if not group_tags:
        group_tags = ["A", "B"]

    standings_by_group = {}
    second_places = []

    for g_name in group_tags:
        g_regs = [r for r in registrations if r.group_tag == g_name]
        g_team_ids = [r.college_team_id for r in g_regs]
        g_matches = [m for m in matches if m.stage_type == f"GROUP_{g_name}"]

        stats = {
            tid: {
                "team_id": tid,
                "team_name": db.get(CollegeTeam, tid).team_name if db.get(CollegeTeam, tid) else "队伍",
                "college": db.get(CollegeTeam, tid).college if db.get(CollegeTeam, tid) else "学院",
                "group_tag": g_name,
                "played": 0,
                "won": 0,
                "lost": 0,
                "forfeited": 0,
                "points": 0,         # 胜2分，负1分，弃权0分
                "rubbers_won": 0,    # 胜盘数
                "rubbers_lost": 0,   # 负盘数
                "rubber_diff": 0,    # 净胜盘
                "sets_won": 0,       # 胜局数
                "sets_lost": 0,      # 负局数
                "set_ratio": 0.0,    # 局分比
                "points_for": 0,     # 得分
                "points_against": 0, # 失分
                "point_ratio": 0.0,  # 得失分比
            }
            for tid in g_team_ids
        }

        for m in g_matches:
            if m.status in ["FINISHED", "FORFEIT"] and m.home_team_id in stats and m.away_team_id in stats:
                h = stats[m.home_team_id]
                a = stats[m.away_team_id]
                h["played"] += 1
                a["played"] += 1

                h["rubbers_won"] += (m.home_score or 0)
                h["rubbers_lost"] += (m.away_score or 0)
                a["rubbers_won"] += (m.away_score or 0)
                a["rubbers_lost"] += (m.home_score or 0)

                # 累加局分与小分
                if m.team_rubber_detail:
                    for r in m.team_rubber_detail:
                        h_sets = r.get("home_score", 0)
                        a_sets = r.get("away_score", 0)
                        h["sets_won"] += h_sets
                        h["sets_lost"] += a_sets
                        a["sets_won"] += a_sets
                        a["sets_lost"] += h_sets
                        for s_item in r.get("sets", []):
                            h["points_for"] += s_item.get("home", 0)
                            h["points_against"] += s_item.get("away", 0)
                            a["points_for"] += s_item.get("away", 0)
                            a["points_against"] += s_item.get("home", 0)

                # 积分计算：胜2分、负1分、弃权0分
                if m.status == "FORFEIT":
                    if m.forfeit_team_id == m.home_team_id:
                        h["forfeited"] += 1
                        h["lost"] += 1
                        h["points"] += 0
                        a["won"] += 1
                        a["points"] += 2
                    else:
                        a["forfeited"] += 1
                        a["lost"] += 1
                        a["points"] += 0
                        h["won"] += 1
                        h["points"] += 2
                else:
                    if m.winner_team_id == m.home_team_id:
                        h["won"] += 1
                        h["points"] += 2
                        a["lost"] += 1
                        a["points"] += 1
                    else:
                        a["won"] += 1
                        a["points"] += 2
                        h["lost"] += 1
                        h["points"] += 1

        for s in stats.values():
            s["rubber_diff"] = s["rubbers_won"] - s["rubbers_lost"]
            s["set_ratio"] = round(s["sets_won"] / s["sets_lost"], 4) if s["sets_lost"] > 0 else (s["sets_won"] * 100.0)
            s["point_ratio"] = round(s["points_for"] / s["points_against"], 4) if s["points_against"] > 0 else (s["points_for"] * 100.0)

        # 排序：总积分 -> 净胜盘 -> 局分比 -> 得失分比
        sorted_list = sorted(stats.values(), key=lambda item: (item["points"], item["rubber_diff"], item["set_ratio"], item["point_ratio"]), reverse=True)
        for idx, item in enumerate(sorted_list):
            item["rank"] = idx + 1
            if idx == 1:  # 小组第二
                second_places.append(item)

        standings_by_group[f"group_{g_name.lower()}"] = sorted_list

    # 遴选成绩最好的小组第二名
    best_second_team_id = None
    if second_places:
        sorted_seconds = sorted(second_places, key=lambda item: (item["points"], item["rubber_diff"], item["set_ratio"], item["point_ratio"]), reverse=True)
        sorted_seconds[0]["is_best_second"] = True
        best_second_team_id = sorted_seconds[0]["team_id"]
        for s in sorted_seconds[1:]:
            s["is_best_second"] = False

    return {
        "groups": standings_by_group,
        "best_second_team_id": best_second_team_id,
        "seconds_ranked": second_places,
    }


@router.post("/sports-teacher/table-tennis/team/advance-to-finals")
def table_tennis_team_advance_to_finals(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    """各小组第一名及成绩最好的小组第二名进入第二阶段交叉淘汰赛（争夺前四名）"""
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    standings_data = table_tennis_team_standings(event_id, db=db)
    groups = standings_data["groups"]

    if "group_a" not in groups or "group_b" not in groups:
        raise HTTPException(400, "至少需要A组和B组各自决出前两名")

    group_a = groups["group_a"]
    group_b = groups["group_b"]
    if len(group_a) < 2 or len(group_b) < 2:
        raise HTTPException(400, "各小组需至少有2支队伍")

    a1 = group_a[0]["team_id"]
    b1 = group_b[0]["team_id"]
    a2 = group_a[1]["team_id"]
    b2 = group_b[1]["team_id"]

    # 交叉对阵：A1 vs B2, B1 vs A2
    old_playoffs = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type.in_(["SEMIFINAL", "THIRD_PLACE", "FINAL"]))))
    for m in old_playoffs:
        db.delete(m)
    db.flush()

    sf1 = TournamentMatch(
        event_id=event_id,
        stage_type="SEMIFINAL",
        match_code="TT_SF1",
        match_name="乒乓球团体半决赛1 (A组第1 vs B组第2/最佳第二)",
        home_team_id=a1,
        away_team_id=b2,
        status="NOT_STARTED",
        court_venue="乒乓球馆1号台",
        best_of=3,
        team_rubber_detail=_default_team_rubbers(db, a1, b2),
    )
    sf2 = TournamentMatch(
        event_id=event_id,
        stage_type="SEMIFINAL",
        match_code="TT_SF2",
        match_name="乒乓球团体半决赛2 (B组第1 vs A组第2)",
        home_team_id=b1,
        away_team_id=a2,
        status="NOT_STARTED",
        court_venue="乒乓球馆2号台",
        best_of=3,
        team_rubber_detail=_default_team_rubbers(db, b1, a2),
    )
    db.add(sf1)
    db.add(sf2)
    db.commit()

    return {"message": "已成功提取小组第一名及成绩最好第二名生成第二阶段交叉半决赛！", "sf1": [a1, b2], "sf2": [b1, a2]}


@router.post("/sports-teacher/table-tennis/team/generate-finals")
def table_tennis_team_generate_finals(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    """生成乒乓球混合团体季军争夺赛与冠亚军总决赛"""
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    sf_matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type == "SEMIFINAL")))
    if len(sf_matches) < 2 or any(m.status not in ["FINISHED", "FORFEIT"] for m in sf_matches):
        raise HTTPException(400, "请先录入两场半决赛的比分并完赛，才能生成决赛与季军赛")

    sf1 = next(m for m in sf_matches if m.match_code in ["TT_SF1", "SF1"])
    sf2 = next(m for m in sf_matches if m.match_code in ["TT_SF2", "SF2"])

    old_finals = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type.in_(["THIRD_PLACE", "FINAL"]))))
    for m in old_finals:
        db.delete(m)
    db.flush()

    third_place = TournamentMatch(
        event_id=event_id,
        stage_type="THIRD_PLACE",
        match_code="TT_3RD",
        match_name="乒乓球团体季军争夺赛 (第3、4名决赛)",
        home_team_id=sf1.loser_team_id,
        away_team_id=sf2.loser_team_id,
        status="NOT_STARTED",
        court_venue="乒乓球馆2号台",
        best_of=3,
        team_rubber_detail=_default_team_rubbers(db, sf1.loser_team_id, sf2.loser_team_id),
    )
    championship = TournamentMatch(
        event_id=event_id,
        stage_type="FINAL",
        match_code="TT_FINAL",
        match_name="乒乓球团体冠亚军总决赛 (争夺第1、2名)",
        home_team_id=sf1.winner_team_id,
        away_team_id=sf2.winner_team_id,
        status="NOT_STARTED",
        court_venue="乒乓球馆1号台",
        best_of=3,
        team_rubber_detail=_default_team_rubbers(db, sf1.winner_team_id, sf2.winner_team_id),
    )
    db.add(third_place)
    db.add(championship)
    db.commit()

    return {"message": "已生成乒乓球混合团体冠亚军总决赛及三四名季军赛！"}


@router.post("/sports-teacher/table-tennis/team/finalize-results")
def table_tennis_team_finalize_results(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    """定稿归档混合团体赛前四名至成绩公布台"""
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_score")

    final_match = db.scalar(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type == "FINAL"))
    third_match = db.scalar(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type == "THIRD_PLACE"))

    if not final_match or final_match.status not in ["FINISHED", "FORFEIT"] or not third_match or third_match.status not in ["FINISHED", "FORFEIT"]:
        raise HTTPException(400, "混合团体冠亚军总决赛和三四名决赛均已完赛后方可定稿前四名成绩")

    rankings = [
        (1, final_match.winner_team_id, final_match.home_score if final_match.winner_team_id == final_match.home_team_id else final_match.away_score),
        (2, final_match.loser_team_id, final_match.away_score if final_match.winner_team_id == final_match.home_team_id else final_match.home_score),
        (3, third_match.winner_team_id, third_match.home_score if third_match.winner_team_id == third_match.home_team_id else third_match.away_score),
        (4, third_match.loser_team_id, third_match.away_score if third_match.winner_team_id == third_match.home_team_id else third_match.home_score),
    ]

    rounds = list(db.scalars(select(EventRound).where(EventRound.event_id == event_id).order_by(EventRound.sequence.desc())))
    target_round = rounds[0] if rounds else None
    multiplier = event.points_multiplier or Decimal("2.0")
    default_base_points = {1: Decimal("9"), 2: Decimal("7"), 3: Decimal("6"), 4: Decimal("5")}

    for rank, team_id, score_val in rankings:
        reg = db.scalar(select(Registration).where(Registration.event_id == event_id, Registration.college_team_id == team_id))
        if not reg:
            continue
        res = db.scalar(select(Result).where(Result.event_id == event_id, Result.registration_id == reg.id))
        if not res:
            res = Result(event_id=event_id, round_id=target_round.id if target_round else reg.round_id, registration_id=reg.id)
            db.add(res)
        res.rank = rank
        res.raw_value = Decimal(score_val or 0)
        res.competition_status = "NORMAL"
        res.state = ResultState.REVIEWED
        base_p = default_base_points.get(rank, Decimal("0"))
        res.points = base_p * multiplier
        res.finalized_by_id = user.id
        res.finalized_at = utcnow()

    db.commit()
    return {"message": "已成功将乒乓球混合团体前四名排名与团体积分归档至公布台！"}


# ------------------------------------------------------------------------------
# 🏓 单打比赛部分 (Men's & Women's Singles Engine: 前三局二胜，八强后五局三胜)
# ------------------------------------------------------------------------------

@router.get("/sports-teacher/table-tennis/singles/athletes")
def table_tennis_singles_athletes(event_id: int, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    """获取单打项目报名运动员及种子序号（每院3人，种子在前）"""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")

    registrations = list(db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.student_id.is_not(None)).order_by(Registration.id)))
    athletes = []
    college_counts = {}
    for r in registrations:
        s = db.get(StudentRoster, r.student_id)
        if s:
            c_cnt = college_counts.get(s.college, 0) + 1
            college_counts[s.college] = c_cnt
            seed_no = int(r.heat.replace("种子", "")) if (r.heat and "种子" in r.heat) else c_cnt
            athletes.append({
                "registration_id": r.id,
                "student_id": s.id,
                "student_no": s.student_no,
                "name": s.name,
                "gender": s.gender,
                "college": s.college,
                "seed_no": seed_no,
                "status": r.status,
            })
    return {"athletes": athletes, "college_counts": college_counts}


@router.post("/sports-teacher/table-tennis/singles/add-athletes")
def table_tennis_singles_add_athletes(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    """为单打比赛批量录入运动员（可标注1/2/3号种子）"""
    event_id = data.get("event_id")
    student_entries = data.get("student_entries", [])  # [{"student_id": 1, "seed_no": 1}, ...]
    if not event_id:
        raise HTTPException(400, "请指定单打比赛项目 ID")

    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    rounds = list(db.scalars(select(EventRound).where(EventRound.event_id == event_id).order_by(EventRound.sequence)))
    target_round_id = rounds[0].id if rounds else 1

    added = 0
    for entry in student_entries:
        sid = entry["student_id"]
        seed = entry.get("seed_no", 1)
        existing = db.scalar(select(Registration).where(Registration.event_id == event_id, Registration.student_id == sid))
        if not existing:
            reg = Registration(
                event_id=event_id,
                round_id=target_round_id,
                student_id=sid,
                heat=f"种子{seed}",
                status="REGISTERED",
            )
            db.add(reg)
            added += 1
        else:
            existing.heat = f"种子{seed}"

    db.commit()
    return {"message": f"成功更新 {len(student_entries)} 名单打参赛选手！", "added_count": added}


@router.post("/sports-teacher/table-tennis/singles/draw")
def table_tennis_singles_draw(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    """根据种子排位与同院回避原则生成淘汰赛签表（八强前三局两胜，八强起五局三胜）"""
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    registrations = list(db.scalars(select(Registration).where(Registration.event_id == event_id, Registration.student_id.is_not(None)).order_by(Registration.id)))
    if len(registrations) < 4:
        raise HTTPException(400, "单打淘汰赛至少需要 4 名选手")

    # 清除旧单打比赛
    old_matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id)))
    for m in old_matches:
        db.delete(m)
    db.flush()

    # 提取运动员对象并根据种子排位
    athlete_list = []
    for r in registrations:
        s = db.get(StudentRoster, r.student_id)
        if s:
            seed_no = 1
            if r.heat and "种子" in r.heat:
                try:
                    seed_no = int(r.heat.replace("种子", ""))
                except Exception:
                    seed_no = 1
            athlete_list.append({"id": s.id, "name": s.name, "college": s.college, "seed_no": seed_no})

    # 同院回避与种子位分布
    # 按种子分组：1号种子分布在不同对区
    seed1 = [a for a in athlete_list if a["seed_no"] == 1]
    seed2 = [a for a in athlete_list if a["seed_no"] == 2]
    seed3 = [a for a in athlete_list if a["seed_no"] >= 3]
    ordered_athletes = seed1 + seed2 + seed3

    # 生成首轮对阵
    # 如果选手数量 <= 8，首轮直接是 1/4 决赛 (八强)，采用五局三胜制；若 > 8 则首轮是资格赛/1/8 决赛，采用三局两胜制
    is_top8 = (len(ordered_athletes) <= 8)
    initial_stage = "QUARTERFINAL" if is_top8 else "ROUND_OF_16"
    initial_best_of = 5 if is_top8 else 3

    matches_count = len(ordered_athletes) // 2
    for i in range(matches_count):
        h_student = ordered_athletes[i]
        a_student = ordered_athletes[len(ordered_athletes) - 1 - i]
        m = TournamentMatch(
            event_id=event_id,
            stage_type=initial_stage,
            match_code=f"TT_{'QF' if is_top8 else 'R16'}_{i+1}",
            match_name=f"{'1/4决赛第' if is_top8 else '1/8决赛第'}{i+1}场 ({'五局三胜' if initial_best_of == 5 else '三局两胜'})",
            home_student_id=h_student["id"],
            away_student_id=a_student["id"],
            status="NOT_STARTED",
            best_of=initial_best_of,
            court_venue=f"乒乓球馆{i+1}号台",
        )
        db.add(m)

    db.commit()
    return {"message": f"成功完成单打签表编排（生成 {matches_count} 场首轮淘汰对阵，前期采用{initial_best_of}局{ (initial_best_of+1)//2 }胜制）！"}


@router.get("/sports-teacher/table-tennis/singles/matches")
def table_tennis_singles_matches(event_id: int, _actor: User = Depends(business_admin), db: Session = Depends(get_db)):
    matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id).order_by(TournamentMatch.id)))
    return [_match_dict(db, m) for m in matches]


@router.put("/sports-teacher/table-tennis/singles/matches/{match_id}")
def table_tennis_singles_update_match(match_id: int, data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    """录入单打比赛比分（11分制，支持三局两胜与五局三胜）"""
    match = db.get(TournamentMatch, match_id)
    if not match:
        raise HTTPException(404, "单打对阵比赛不存在")
    require_event_permission(db, user, match.event_id, "can_score")

    sets = data.get("sets_detail", [])
    if not sets:
        raise HTTPException(400, "请录入各局比分（每局11分制）")

    best_of = match.best_of or 3
    target_wins = (best_of + 1) // 2

    home_wins = 0
    away_wins = 0
    for s in sets:
        h = int(s.get("home", 0))
        a = int(s.get("away", 0))
        if h > a:
            home_wins += 1
        elif a > h:
            away_wins += 1

    if home_wins < target_wins and away_wins < target_wins:
        raise HTTPException(400, f"当前赛制为{best_of}局{target_wins}胜制，获胜方需赢得 {target_wins} 局（当前 {home_wins}:{away_wins}）")

    match.sets_detail = sets
    match.home_score = home_wins
    match.away_score = away_wins
    if home_wins > away_wins:
        match.winner_student_id = match.home_student_id
        match.loser_student_id = match.away_student_id
    else:
        match.winner_student_id = match.away_student_id
        match.loser_student_id = match.home_student_id
    match.status = "FINISHED"

    if "court_venue" in data:
        match.court_venue = data["court_venue"]
    if "match_time" in data and data["match_time"]:
        match.match_time = datetime.fromisoformat(data["match_time"].replace("Z", ""))
    if "notes" in data:
        match.notes = data["notes"]

    db.commit()
    return {"message": f"单打比分录入成功，已决出晋级选手！", "match": _match_dict(db, match)}


@router.post("/sports-teacher/table-tennis/singles/advance-next-round")
def table_tennis_singles_advance_next_round(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    """单打晋级下一轮（自动处理：进入八强后切换为五局三胜制）"""
    event_id = data.get("event_id")
    current_stage = data.get("current_stage")  # ROUND_OF_16, QUARTERFINAL, SEMIFINAL
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_schedule")

    curr_matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type == current_stage).order_by(TournamentMatch.id)))
    if not curr_matches or any(m.status != "FINISHED" for m in curr_matches):
        raise HTTPException(400, f"请先录入当前轮次（{current_stage}）全部场次的比分并完赛")

    winners = [m.winner_student_id for m in curr_matches]

    if current_stage in ["ROUND_OF_16", "PRELIMINARY"]:
        # 晋级到八强 (1/4 决赛) -> 规程要求：进入八强后采用五局三胜制！
        next_stage = "QUARTERFINAL"
        next_best_of = 5
        pairs_count = len(winners) // 2
        for i in range(pairs_count):
            h_id = winners[i * 2]
            a_id = winners[i * 2 + 1]
            m = TournamentMatch(
                event_id=event_id,
                stage_type=next_stage,
                match_code=f"TT_QF_{i+1}",
                match_name=f"1/4决赛第{i+1}场 (进入八强·五局三胜制)",
                home_student_id=h_id,
                away_student_id=a_id,
                status="NOT_STARTED",
                best_of=next_best_of,
                court_venue=f"乒乓球馆{i+1}号台",
            )
            db.add(m)
        msg = f"已顺利晋级八强（1/4决赛）！依据竞赛规程，八强后自动切换为【五局三胜制】。"

    elif current_stage == "QUARTERFINAL":
        # 晋级到半决赛
        next_stage = "SEMIFINAL"
        next_best_of = 5
        sf1 = TournamentMatch(
            event_id=event_id,
            stage_type=next_stage,
            match_code="TT_SF1",
            match_name="单打半决赛第1场 (五局三胜制)",
            home_student_id=winners[0],
            away_student_id=winners[1],
            status="NOT_STARTED",
            best_of=next_best_of,
            court_venue="乒乓球馆1号台",
        )
        sf2 = TournamentMatch(
            event_id=event_id,
            stage_type=next_stage,
            match_code="TT_SF2",
            match_name="单打半决赛第2场 (五局三胜制)",
            home_student_id=winners[2] if len(winners) > 2 else winners[0],
            away_student_id=winners[3] if len(winners) > 3 else winners[1],
            status="NOT_STARTED",
            best_of=next_best_of,
            court_venue="乒乓球馆2号台",
        )
        db.add(sf1)
        db.add(sf2)
        msg = "已生成单打半决赛对阵（五局三胜制）！"

    elif current_stage == "SEMIFINAL":
        # 生成季军赛与总决赛
        sf1 = curr_matches[0]
        sf2 = curr_matches[1]
        third_place = TournamentMatch(
            event_id=event_id,
            stage_type="THIRD_PLACE",
            match_code="TT_3RD",
            match_name="单打季军争夺赛 (第3、4名决赛·五局三胜)",
            home_student_id=sf1.loser_student_id,
            away_student_id=sf2.loser_student_id,
            status="NOT_STARTED",
            best_of=5,
            court_venue="乒乓球馆2号台",
        )
        championship = TournamentMatch(
            event_id=event_id,
            stage_type="FINAL",
            match_code="TT_FINAL",
            match_name="单打冠亚军总决赛 (争夺冠军·五局三胜)",
            home_student_id=sf1.winner_student_id,
            away_student_id=sf2.winner_student_id,
            status="NOT_STARTED",
            best_of=5,
            court_venue="乒乓球馆1号台",
        )
        db.add(third_place)
        db.add(championship)
        msg = "已生成单打冠亚军总决赛及季军争夺赛（五局三胜制）！"
    else:
        raise HTTPException(400, "未知轮次")

    db.commit()
    return {"message": msg}


@router.post("/sports-teacher/table-tennis/singles/finalize-results")
def table_tennis_singles_finalize_results(data: dict, user: User = Depends(business_admin), db: Session = Depends(get_db)):
    """定稿单打比赛成绩并归档至成绩公布台"""
    event_id = data.get("event_id")
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "比赛项目不存在")
    require_event_permission(db, user, event_id, "can_score")

    final_match = db.scalar(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type == "FINAL"))
    third_match = db.scalar(select(TournamentMatch).where(TournamentMatch.event_id == event_id, TournamentMatch.stage_type == "THIRD_PLACE"))

    if not final_match or final_match.status != "FINISHED" or not third_match or third_match.status != "FINISHED":
        raise HTTPException(400, "单打总决赛与季军赛均完赛后方可定稿成绩")

    rankings = [
        (1, final_match.winner_student_id, final_match.home_score if final_match.winner_student_id == final_match.home_student_id else final_match.away_score),
        (2, final_match.loser_student_id, final_match.away_score if final_match.winner_student_id == final_match.home_student_id else final_match.home_score),
        (3, third_match.winner_student_id, third_match.home_score if third_match.winner_student_id == third_match.home_student_id else third_match.away_score),
        (4, third_match.loser_student_id, third_match.away_score if third_match.winner_student_id == third_match.home_student_id else third_match.home_score),
    ]

    rounds = list(db.scalars(select(EventRound).where(EventRound.event_id == event_id).order_by(EventRound.sequence.desc())))
    target_round = rounds[0] if rounds else None
    multiplier = event.points_multiplier or Decimal("1.0")
    default_base_points = {1: Decimal("9"), 2: Decimal("7"), 3: Decimal("6"), 4: Decimal("5")}

    for rank, sid, score_val in rankings:
        reg = db.scalar(select(Registration).where(Registration.event_id == event_id, Registration.student_id == sid))
        if not reg:
            continue
        res = db.scalar(select(Result).where(Result.event_id == event_id, Result.registration_id == reg.id))
        if not res:
            res = Result(event_id=event_id, round_id=target_round.id if target_round else reg.round_id, registration_id=reg.id)
            db.add(res)
        res.rank = rank
        res.raw_value = Decimal(score_val or 0)
        res.competition_status = "NORMAL"
        res.state = ResultState.REVIEWED
        base_p = default_base_points.get(rank, Decimal("0"))
        res.points = base_p * multiplier
        res.finalized_by_id = user.id
        res.finalized_at = utcnow()

    db.commit()
    return {"message": f"已成功将【{event.name}】前四名名次与个人积分归档至成绩公布台！"}


@router.get("/public/table-tennis")
def public_table_tennis(event_id: int | None = None, meet_id: int | None = None, db: Session = Depends(get_db)):
    """公开端大屏乒乓球赛况查询接口"""
    stmt = select(Event).where(Event.name.contains("乒乓球"))
    if meet_id:
        stmt = stmt.where(Event.meet_id == meet_id)
    events = list(db.scalars(stmt))
    if not events:
        return {"has_tournament": False}

    current_event = db.get(Event, event_id) if event_id else events[0]
    matches = list(db.scalars(select(TournamentMatch).where(TournamentMatch.event_id == current_event.id).order_by(TournamentMatch.id)))

    standings = None
    if current_event.event_type == "TEAM":
        standings = table_tennis_team_standings(current_event.id, db=db)

    return {
        "has_tournament": True,
        "current_event": {
            "id": current_event.id,
            "name": current_event.name,
            "event_type": current_event.event_type,
            "gender_group": current_event.gender_group,
        },
        "available_events": [{"id": e.id, "name": e.name, "event_type": e.event_type} for e in events],
        "standings": standings,
        "matches": [_match_dict(db, m) for m in matches],
    }
