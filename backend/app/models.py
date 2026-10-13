from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Role(StrEnum):
    DEVELOPER = "DEVELOPER"
    SPORTS_TEACHER = "SPORTS_TEACHER"
    REFEREE = "REFEREE"
    SCORER = "SCORER"
    REFEREE_SCORER = "REFEREE_SCORER"
    STUDENT = "STUDENT"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"


class ResultState(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"
    RETURNED = "RETURNED"
    PUBLISHED = "PUBLISHED"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), default=UserStatus.ACTIVE)
    display_name: Mapped[str] = mapped_column(String(64))
    department: Mapped[str | None] = mapped_column(String(128))
    first_login_change_required: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    frozen_reason: Mapped[str | None] = mapped_column(String(255))
    token_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AdministratorProfile(Base):
    __tablename__ = "administrator_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    employee_no: Mapped[str] = mapped_column(String(64), unique=True)
    phone: Mapped[str | None] = mapped_column(String(32))


class StudentRoster(Base):
    __tablename__ = "student_roster"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    gender: Mapped[str] = mapped_column(String(8))
    college: Mapped[str] = mapped_column(String(128), index=True)
    major: Mapped[str] = mapped_column(String(128))
    class_name: Mapped[str] = mapped_column(String(128))
    activated: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SportsMeet(Base):
    __tablename__ = "sports_meets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    edition: Mapped[str] = mapped_column(String(32))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    registration_start: Mapped[datetime | None] = mapped_column(DateTime)
    registration_end: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(24), default="PREPARING", index=True)
    public_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("name", "edition", name="uq_sports_meet_name_edition"),)


class CollegeTeam(Base):
    __tablename__ = "college_teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    meet_id: Mapped[int] = mapped_column(ForeignKey("sports_meets.id"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    college: Mapped[str] = mapped_column(String(128), index=True)
    team_name: Mapped[str] = mapped_column(String(160))
    leader_name: Mapped[str | None] = mapped_column(String(64))
    leader_phone: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("meet_id", "college", "team_name", name="uq_college_team_meet_college_team_name"),)


class CollegeTeamMember(Base):
    __tablename__ = "college_team_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("college_teams.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_roster.id"), index=True)
    role_title: Mapped[str | None] = mapped_column(String(64))  # 队长/主攻/副攻/二传/自由人/队员
    is_starter: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("team_id", "student_id", name="uq_college_team_member"),)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    meet_id: Mapped[int] = mapped_column(ForeignKey("sports_meets.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(128))
    gender_group: Mapped[str] = mapped_column(String(16), index=True)
    participant_group: Mapped[str] = mapped_column(String(16), default="STUDENT")
    event_type: Mapped[str] = mapped_column(String(16), default="INDIVIDUAL")
    result_unit: Mapped[str] = mapped_column(String(16), default="秒")
    sort_direction: Mapped[str] = mapped_column(String(8), default="ASC")
    stage: Mapped[str] = mapped_column(String(16), default="FINAL", index=True)
    qualification_count: Mapped[int] = mapped_column(Integer, default=0)
    scoring_places: Mapped[int] = mapped_column(Integer, default=8)
    points_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=1)
    scoring_model_id: Mapped[int | None] = mapped_column(ForeignKey("scoring_models.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("meet_id", "code", name="uq_event_meet_code"),)


class EventAdminPermission(Base):
    __tablename__ = "event_admin_permissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    can_schedule: Mapped[bool] = mapped_column(Boolean, default=False)
    can_score: Mapped[bool] = mapped_column(Boolean, default=False)
    can_review: Mapped[bool] = mapped_column(Boolean, default=False)
    can_export: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_event_admin_permission"),)


class EventRound(Base):
    __tablename__ = "event_rounds"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    name: Mapped[str] = mapped_column(String(32))
    stage: Mapped[str] = mapped_column(String(16), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    qualification_count: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("event_id", "sequence", name="uq_event_round_sequence"),)


class EventSchedule(Base):
    __tablename__ = "event_schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    round_id: Mapped[int | None] = mapped_column(ForeignKey("event_rounds.id"))
    competition_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime)
    venue: Mapped[str] = mapped_column(String(128))
    heat: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="NOT_STARTED")
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Registration(Base):
    __tablename__ = "registrations"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("event_rounds.id"), index=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("student_roster.id"), index=True)
    college_team_id: Mapped[int | None] = mapped_column(ForeignKey("college_teams.id"), index=True)
    bib_no: Mapped[str | None] = mapped_column(String(32))
    heat: Mapped[str | None] = mapped_column(String(32))
    lane: Mapped[str | None] = mapped_column(String(16))
    group_tag: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="REGISTERED")
    __table_args__ = (
        UniqueConstraint("event_id", "round_id", "student_id", name="uq_registration_round_student"),
        UniqueConstraint("event_id", "round_id", "college_team_id", name="uq_registration_round_college_team"),
        CheckConstraint(
            "(student_id IS NOT NULL AND college_team_id IS NULL) OR (student_id IS NULL AND college_team_id IS NOT NULL)",
            name="ck_registration_exactly_one_participant",
        ),
    )


class TournamentMatch(Base):
    __tablename__ = "tournament_matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    round_id: Mapped[int | None] = mapped_column(ForeignKey("event_rounds.id"), index=True)
    stage_type: Mapped[str] = mapped_column(String(24), index=True)  # GROUP_A, GROUP_B, SEMIFINAL, THIRD_PLACE, FINAL
    match_code: Mapped[str] = mapped_column(String(32))             # 如 "A1-A2", "B1-B3", "SF1", "SF2", "3RD", "FINAL"
    match_name: Mapped[str | None] = mapped_column(String(64))      # 如 "A组第1轮", "半决赛1", "冠亚军总决赛"
    home_team_id: Mapped[int | None] = mapped_column(ForeignKey("college_teams.id"))
    away_team_id: Mapped[int | None] = mapped_column(ForeignKey("college_teams.id"))
    home_student_id: Mapped[int | None] = mapped_column(ForeignKey("student_roster.id"))
    away_student_id: Mapped[int | None] = mapped_column(ForeignKey("student_roster.id"))
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("college_teams.id"))
    loser_team_id: Mapped[int | None] = mapped_column(ForeignKey("college_teams.id"))
    winner_student_id: Mapped[int | None] = mapped_column(ForeignKey("student_roster.id"))
    loser_student_id: Mapped[int | None] = mapped_column(ForeignKey("student_roster.id"))
    status: Mapped[str] = mapped_column(String(24), default="NOT_STARTED", index=True)  # NOT_STARTED, IN_PROGRESS, FINISHED, FORFEIT
    best_of: Mapped[int | None] = mapped_column(Integer, default=3)  # 3: 三局两胜, 5: 五局三胜
    court_venue: Mapped[str | None] = mapped_column(String(128))
    match_time: Mapped[datetime | None] = mapped_column(DateTime)
    sets_detail: Mapped[list | None] = mapped_column(JSON)            # 各局小比分，如 [{"set": 1, "home": 11, "away": 8}, ...]
    team_rubber_detail: Mapped[list | None] = mapped_column(JSON)     # 团体赛5盘详情 [{"order": 1, "type": "MALE_SINGLES", "name": "男单1", "home_player": "张三", "away_player": "李四", "home_score": 2, "away_score": 1, "sets": [{"home": 11, "away": 9}, ...], "winner": "HOME"}, ...]
    forfeit_team_id: Mapped[int | None] = mapped_column(ForeignKey("college_teams.id"))  # 弃权队伍 ID
    notes: Mapped[str | None] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Result(Base):
    __tablename__ = "results"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    round_id: Mapped[int | None] = mapped_column(ForeignKey("event_rounds.id"), index=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("registrations.id"), index=True)
    raw_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    competition_status: Mapped[str] = mapped_column(String(8), default="NORMAL")
    rank: Mapped[int | None] = mapped_column(Integer)
    points: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    state: Mapped[str] = mapped_column(String(16), default=ResultState.DRAFT, index=True)
    notes: Mapped[str | None] = mapped_column(String(255))
    entered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    finalized_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    publisher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    entered_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    published_version: Mapped[int | None] = mapped_column(Integer)
    published_raw_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    published_competition_status: Mapped[str | None] = mapped_column(String(8))
    published_notes: Mapped[str | None] = mapped_column(String(255))
    published_rank: Mapped[int | None] = mapped_column(Integer)
    published_points: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    modification_reason: Mapped[str | None] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("round_id", "registration_id", name="uq_result_round_registration"),)


class RopeLineupMember(Base):
    __tablename__ = "rope_lineup_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    college_team_id: Mapped[int] = mapped_column(ForeignKey("college_teams.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student_roster.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # JUMPER / TURNER
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (
        UniqueConstraint("event_id", "college_team_id", "student_id", name="uq_rope_lineup_event_team_student"),
        CheckConstraint("role IN ('JUMPER', 'TURNER')", name="ck_rope_lineup_role"),
    )


class RopeResultDetail(Base):
    __tablename__ = "rope_result_details"
    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("results.id", ondelete="CASCADE"), unique=True, index=True)
    individual_counts: Mapped[list | None] = mapped_column(JSON)
    completed_target: Mapped[bool | None] = mapped_column(Boolean)
    elapsed_seconds: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    completed_count: Mapped[int | None] = mapped_column(Integer)
    published_detail: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ResultReview(Base):
    __tablename__ = "result_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("results.id"), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    from_state: Mapped[str | None] = mapped_column(String(16))
    to_state: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str | None] = mapped_column(String(255))
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    operator_name_snapshot: Mapped[str] = mapped_column(String(64))
    operator_username_snapshot: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class QualificationRecord(Base):
    __tablename__ = "qualification_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("registrations.id"), index=True)
    from_round_id: Mapped[int] = mapped_column(ForeignKey("event_rounds.id"))
    next_round_id: Mapped[int | None] = mapped_column(ForeignKey("event_rounds.id"))
    status: Mapped[str] = mapped_column(String(24), index=True)
    adjustment_reason: Mapped[str | None] = mapped_column(String(255))
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)


class ScoringModel(Base):
    __tablename__ = "scoring_models"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", index=True)
    places: Mapped[int] = mapped_column(Integer, default=8)
    individual_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=1)
    relay_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=2)
    team_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=2)
    tie_rule: Mapped[str] = mapped_column(String(32), default="AVERAGE_OCCUPIED")
    non_finish_points: Mapped[dict] = mapped_column(JSON, default=dict)
    tiebreak_rules: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("scoring_models.id"))
    locked_by_published_results: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ScoringModelItem(Base):
    __tablename__ = "scoring_model_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("scoring_models.id"), index=True)
    place: Mapped[int] = mapped_column(Integer)
    points: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    __table_args__ = (UniqueConstraint("model_id", "place", name="uq_scoring_model_place"),)


class ScoringModelBinding(Base):
    __tablename__ = "scoring_model_bindings"
    id: Mapped[int] = mapped_column(primary_key=True)
    meet_id: Mapped[int] = mapped_column(ForeignKey("sports_meets.id"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), index=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("scoring_models.id"))
    model_version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    bound_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bound_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ScoreExport(Base):
    __tablename__ = "score_exports"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    state: Mapped[str] = mapped_column(String(16))
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512))
    exporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    exported_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    value: Mapped[str] = mapped_column(Text)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    actor_username: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(64))
    before_data: Mapped[dict | None] = mapped_column(JSON)
    after_data: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


Index("idx_results_event_state_published", Result.event_id, Result.state, Result.published_at)
Index("idx_permissions_user_event", EventAdminPermission.user_id, EventAdminPermission.event_id)
Index("idx_schedules_published_time", EventSchedule.published, EventSchedule.competition_at)

# Register AI assistance models with SQLAlchemy metadata
from .ai.models import AIModelConfig, AIConversation, AIMessage, AIToolLog, AIAuditLog  # noqa: E402, F401

