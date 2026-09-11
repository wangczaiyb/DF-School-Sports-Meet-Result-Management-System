from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class StudentRegisterRequest(BaseModel):
    student_no: str
    name: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class AccountCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str
    password: str = Field(min_length=8)
    role: str
    department: str | None = None
    employee_no: str | None = None
    phone: str | None = None
    enabled: bool = True


class AccountUpdate(BaseModel):
    username: str | None = None
    display_name: str | None = None
    password: str | None = Field(default=None, min_length=8)
    role: str | None = None
    department: str | None = None
    employee_no: str | None = None
    phone: str | None = None


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=2)


class ResetPasswordRequest(BaseModel):
    password: str | None = Field(default=None, min_length=8)


class MeetCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    edition: str = Field(min_length=1, max_length=32)
    start_date: date
    end_date: date
    status: str = "PREPARING"
    public_visible: bool = True


class StudentRosterCreate(BaseModel):
    student_no: str = Field(min_length=6, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    gender: str
    college: str = Field(min_length=1, max_length=128)
    major: str = Field(min_length=1, max_length=128)
    class_name: str = Field(min_length=1, max_length=128)


class CollegeTeamCreate(BaseModel):
    meet_id: int
    event_id: int | None = None
    college: str = Field(min_length=1, max_length=128)
    team_name: str | None = Field(default=None, max_length=160)
    leader_name: str | None = Field(default=None, max_length=64)
    leader_phone: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=255)


class CollegeTeamGenerate(BaseModel):
    meet_id: int
    event_id: int | None = None


class CollegeTeamMemberCreate(BaseModel):
    student_id: int
    role_title: str | None = Field(default="队员", max_length=64)
    is_starter: bool = False


class CollegeTeamMemberUpdate(BaseModel):
    role_title: str | None = Field(default="队员", max_length=64)
    is_starter: bool = False


class CollegeTeamMemberBatchCreate(BaseModel):
    student_ids: list[int] = Field(min_length=1)
    role_title: str | None = Field(default="队员", max_length=64)


class RegistrationBatchCreate(BaseModel):
    event_id: int
    round_id: int
    participant_ids: list[int] = Field(min_length=1)
    heat: str | None = Field(default=None, max_length=32)
    status: Literal["REGISTERED", "CHECKED_IN", "ALTERNATE", "ABSENT", "WITHDRAWN"] = "REGISTERED"


class RegistrationUpdate(BaseModel):
    bib_no: str | None = Field(default=None, max_length=32)
    heat: str | None = Field(default=None, max_length=32)
    lane: str | None = Field(default=None, max_length=16)
    status: Literal["REGISTERED", "CHECKED_IN", "ALTERNATE", "ABSENT", "WITHDRAWN"] = "REGISTERED"


class RegistrationSeedRequest(BaseModel):
    event_id: int
    round_id: int
    lanes_per_heat: int = Field(default=8, ge=2, le=12)


class RegistrationAdvanceRequest(BaseModel):
    event_id: int
    from_round_id: int
    to_round_id: int
    count: int = Field(ge=1, le=200)
    alternates: int = Field(default=0, ge=0, le=20)


class EventCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    meet_id: int
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    gender_group: str = Field(min_length=1, max_length=16)
    participant_group: str = Field(default="STUDENT", min_length=1, max_length=16)
    event_type: str = Field(default="INDIVIDUAL", min_length=1, max_length=16)
    result_unit: str = Field(default="秒", min_length=1, max_length=16)
    sort_direction: str = Field(default="ASC", min_length=1, max_length=8)
    stage: str = Field(default="FINAL", min_length=1, max_length=16)
    qualification_count: int = 0
    scoring_places: int = 8
    points_multiplier: Decimal = Decimal("1")


class PermissionUpsert(BaseModel):
    user_id: int
    event_id: int
    can_schedule: bool = False
    can_score: bool = False
    can_review: bool = False
    can_export: bool = False


class ScheduleUpsert(BaseModel):
    event_id: int
    round_id: int | None = None
    competition_at: datetime
    check_in_at: datetime | None = None
    venue: str
    heat: str | None = None
    notes: str | None = None
    status: str = "NOT_STARTED"
    published: bool = False


class ResultEntry(BaseModel):
    event_id: int
    round_id: int
    registration_id: int
    raw_value: Decimal | None = None
    competition_status: str = "NORMAL"
    notes: str | None = None
    modification_reason: str | None = None


class RopeLineupMemberInput(BaseModel):
    student_id: int
    role: str
    sequence: int = Field(default=1, ge=1, le=30)


class RopeLineupUpsert(BaseModel):
    event_id: int
    college_team_id: int
    members: list[RopeLineupMemberInput] = Field(min_length=1, max_length=22)


class RopeInitializeRequest(BaseModel):
    meet_id: int


class RopeResultEntry(BaseModel):
    event_id: int
    round_id: int
    registration_id: int
    individual_counts: list[int] | None = None
    completed_target: bool | None = None
    elapsed_seconds: Decimal | None = None
    completed_count: int | None = None
    notes: str | None = Field(default=None, max_length=255)
    modification_reason: str | None = Field(default=None, max_length=255)


class ResultAction(BaseModel):
    result_ids: list[int]
    comment: str | None = None
    approve: bool = True


class ScoringModelCreate(BaseModel):
    name: str
    description: str | None = None
    places: int = 8
    points: list[Decimal] = Field(default_factory=lambda: [Decimal(x) for x in [9, 7, 6, 5, 4, 3, 2, 1]])
    individual_multiplier: Decimal = Decimal("1")
    relay_multiplier: Decimal = Decimal("2")
    team_multiplier: Decimal = Decimal("2")
    status: str = "DRAFT"


class ModelBindRequest(BaseModel):
    meet_id: int
    event_id: int | None = None


class SettingsUpdate(BaseModel):
    values: dict[str, str]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
