from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    AdministratorProfile,
    CollegeTeam,
    CollegeTeamMember,
    Event,
    EventAdminPermission,
    EventRound,
    EventSchedule,
    Registration,
    Result,
    ResultReview,
    ResultState,
    Role,
    ScoringModel,
    ScoringModelBinding,
    ScoringModelItem,
    SportsMeet,
    StudentRoster,
    SystemSetting,
    User,
    utcnow,
)
from .security import hash_password, initial_student_password


DEFAULT_SETTINGS = {
    "system_name": "校园运动会赛事成绩管理系统",
    "short_name": "校园运动会赛事成绩管理系统",
    "browser_title": "校园运动会赛事成绩管理系统",
    "login_heading": "让每一次冲刺，都被准确记录",
    "login_subtitle": "赛事编排、成绩审核与荣誉发布，一站式协同完成",
    "primary_color": "#246BFD",
    "footer": "校园运动会赛事组委会 · 数据以终审发布为准",
    "results_page_name": "赛事成绩中心",
    "logo_text": "跃",
}


def _user(db: Session, username: str, password: str, role: str, name: str, department: str | None = None, first_change: bool = False) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        display_name=name,
        department=department,
        first_login_change_required=first_change,
    )
    db.add(user)
    db.flush()
    return user


def seed_database(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)):
        return
    settings = get_settings()
    dev = _user(db, settings.initial_developer_username, settings.initial_developer_password, Role.DEVELOPER, "系统开发员", "信息中心")
    teacher = _user(db, "admin0001", settings.demo_admin_password, Role.SPORTS_TEACHER, "李老师", "体育部")
    scorer = _user(db, "admin0002", settings.demo_admin_password, Role.SCORER, "王计分员", "体育部")
    referee = _user(db, "admin0003", settings.demo_admin_password, Role.REFEREE, "赵裁判", "体育部")
    both = _user(db, "admin0004", settings.demo_admin_password, Role.REFEREE_SCORER, "陈老师", "体育部")
    for index, user in enumerate([teacher, scorer, referee, both], 1):
        db.add(AdministratorProfile(user_id=user.id, employee_no=f"T{index:04d}"))

    for key, value in DEFAULT_SETTINGS.items():
        db.add(SystemSetting(key=key, value=value, updated_by_id=dev.id))

    standard = ScoringModel(
        name="田径前八名标准计分",
        description="前八名 9、7、6、5、4、3、2、1 分，接力与集体项目双倍",
        status="ENABLED",
        places=8,
        individual_multiplier=1,
        relay_multiplier=2,
        team_multiplier=2,
        tie_rule="AVERAGE_OCCUPIED",
        non_finish_points={"DNS": 0, "DNF": 0, "DQ": 0, "NM": 0},
        tiebreak_rules=["gold", "silver", "bronze"],
        created_by_id=teacher.id,
        updated_by_id=teacher.id,
    )
    demo = ScoringModel(
        name="趣味项目演示计分",
        description="用于趣味集体项目的演示模型",
        status="DRAFT",
        places=6,
        individual_multiplier=1,
        relay_multiplier=2,
        team_multiplier=2,
        tie_rule="AVERAGE_OCCUPIED",
        non_finish_points={"DNS": 0, "DNF": 0, "DQ": 0, "NM": 0},
        tiebreak_rules=["gold", "silver", "bronze"],
        created_by_id=teacher.id,
        updated_by_id=teacher.id,
    )
    volleyball_model = ScoringModel(
        name="排球分组循环及交叉淘汰计分模型",
        description="依据《排球竞赛规则》：第一阶段分组单循环（胜场积4分、1:2负积2分、0:2负积1分、15分钟未到场弃权积0分并判0:2）；第二阶段交叉淘汰争夺前四名（第1至4名分别计9/7/6/5分，团体双倍系数）",
        status="ENABLED",
        places=4,
        individual_multiplier=1,
        relay_multiplier=2,
        team_multiplier=2,
        tie_rule="AVERAGE_OCCUPIED",
        non_finish_points={"FORFEIT": 0, "DNS": 0, "DNF": 0, "DQ": 0},
        tiebreak_rules=["set_ratio", "point_ratio"],
        created_by_id=teacher.id,
        updated_by_id=teacher.id,
    )
    table_tennis_team_model = ScoringModel(
        name="乒乓球混合团体计分模型",
        description="依据《乒乓球竞赛规则》：每场打满五盘（男/女/男/女/男），胜一场积2分、负积1分、弃权积0分；第二阶段交叉淘汰争夺前四名（第1至4名分别计9/7/6/5分，团体双倍系数）",
        status="ENABLED",
        places=4,
        individual_multiplier=1,
        relay_multiplier=2,
        team_multiplier=2,
        tie_rule="AVERAGE_OCCUPIED",
        non_finish_points={"FORFEIT": 0, "DNS": 0, "DNF": 0, "DQ": 0},
        tiebreak_rules=["rubber_diff", "set_ratio", "point_ratio"],
        created_by_id=teacher.id,
        updated_by_id=teacher.id,
    )
    table_tennis_singles_model = ScoringModel(
        name="乒乓球单打淘汰计分模型",
        description="依据《乒乓球竞赛规则》：八强前采用三局两胜制，进入八强后采用五局三胜制；前八名分别计 9、7、6、5、4、3、2、1 分",
        status="ENABLED",
        places=8,
        individual_multiplier=1,
        relay_multiplier=2,
        team_multiplier=2,
        tie_rule="AVERAGE_OCCUPIED",
        non_finish_points={"DNS": 0, "DNF": 0, "DQ": 0, "NM": 0},
        tiebreak_rules=["gold", "silver", "bronze"],
        created_by_id=teacher.id,
        updated_by_id=teacher.id,
    )
    db.add_all([standard, demo, volleyball_model, table_tennis_team_model, table_tennis_singles_model])
    db.flush()
    for place, points in enumerate([9, 7, 6, 5, 4, 3, 2, 1], 1):
        db.add(ScoringModelItem(model_id=standard.id, place=place, points=points))
        db.add(ScoringModelItem(model_id=table_tennis_singles_model.id, place=place, points=points))
    for place, points in enumerate([7, 5, 4, 3, 2, 1], 1):
        db.add(ScoringModelItem(model_id=demo.id, place=place, points=points))
    for place, points in enumerate([9, 7, 6, 5], 1):
        db.add(ScoringModelItem(model_id=volleyball_model.id, place=place, points=points))
        db.add(ScoringModelItem(model_id=table_tennis_team_model.id, place=place, points=points))

    meet = SportsMeet(
        name="春季校园田径运动会",
        edition=str(date.today().year),
        start_date=date.today() + timedelta(days=5),
        end_date=date.today() + timedelta(days=7),
        status="COMPETING",
        public_visible=True,
        created_by_id=teacher.id,
    )
    db.add(meet)
    db.flush()
    db.add(
        ScoringModelBinding(
            meet_id=meet.id,
            event_id=None,
            model_id=standard.id,
            model_version=standard.version,
            snapshot={"name": standard.name, "points": [9, 7, 6, 5, 4, 3, 2, 1], "relay_multiplier": 2},
            bound_by_id=teacher.id,
        )
    )

    event_100 = Event(
        meet_id=meet.id, code="M100", name="男子100米", gender_group="MALE", event_type="INDIVIDUAL",
        result_unit="秒", sort_direction="ASC", stage="FINAL", scoring_places=8, points_multiplier=1,
    )
    event_long = Event(
        meet_id=meet.id, code="WLJ", name="女子跳远", gender_group="FEMALE", event_type="INDIVIDUAL",
        result_unit="米", sort_direction="DESC", stage="FINAL", scoring_places=8, points_multiplier=1,
    )
    event_relay = Event(
        meet_id=meet.id, code="MR400", name="男子4×100米接力", gender_group="MALE", event_type="RELAY",
        result_unit="秒", sort_direction="ASC", stage="FINAL", scoring_places=8, points_multiplier=1,
    )
    event_basketball = Event(
        meet_id=meet.id, code="MBB", name="男子篮球赛", gender_group="MALE", event_type="TEAM",
        result_unit="分", sort_direction="DESC", stage="FINAL", scoring_places=4, points_multiplier=2,
    )
    event_volleyball = Event(
        meet_id=meet.id, code="MVB", name="男女混合排球赛", gender_group="MIXED", event_type="TEAM",
        result_unit="分", sort_direction="DESC", stage="FINAL", scoring_places=4, points_multiplier=2,
        scoring_model_id=volleyball_model.id,
    )
    event_tt_team = Event(
        meet_id=meet.id, code="TT_TEAM", name="乒乓球混合团体赛", gender_group="MIXED", event_type="TEAM",
        result_unit="分", sort_direction="DESC", stage="FINAL", scoring_places=4, points_multiplier=2,
        scoring_model_id=table_tennis_team_model.id,
    )
    event_tt_ms = Event(
        meet_id=meet.id, code="TT_MS", name="男子乒乓球单打", gender_group="MALE", event_type="INDIVIDUAL",
        result_unit="分", sort_direction="DESC", stage="FINAL", scoring_places=8, points_multiplier=1,
        scoring_model_id=table_tennis_singles_model.id,
    )
    event_tt_ws = Event(
        meet_id=meet.id, code="TT_WS", name="女子乒乓球单打", gender_group="FEMALE", event_type="INDIVIDUAL",
        result_unit="分", sort_direction="DESC", stage="FINAL", scoring_places=8, points_multiplier=1,
        scoring_model_id=table_tennis_singles_model.id,
    )
    event_rope_single = Event(
        meet_id=meet.id, code="ROPE_SINGLE", name="跳绳 - “前单跳”团体挑战赛", gender_group="MIXED", event_type="TEAM",
        result_unit="次", sort_direction="DESC", stage="FINAL", scoring_places=8, points_multiplier=1,
    )
    event_rope_sync = Event(
        meet_id=meet.id, code="ROPE_SYNC", name="跳绳 - 集体单摇跳", gender_group="MIXED", event_type="TEAM",
        result_unit="秒", sort_direction="ASC", stage="FINAL", scoring_places=8, points_multiplier=1,
    )
    event_rope_fig8 = Event(
        meet_id=meet.id, code="ROPE_FIG8", name="跳绳 - “8”字环绕跳", gender_group="MIXED", event_type="TEAM",
        result_unit="次", sort_direction="DESC", stage="FINAL", scoring_places=8, points_multiplier=1,
    )
    db.add_all([event_100, event_long, event_relay, event_basketball, event_volleyball, event_tt_team, event_tt_ms, event_tt_ws, event_rope_single, event_rope_sync, event_rope_fig8])
    db.flush()
    round_100 = EventRound(event_id=event_100.id, name="决赛", stage="FINAL", sequence=1)
    round_long = EventRound(event_id=event_long.id, name="决赛", stage="FINAL", sequence=1)
    round_basketball = EventRound(event_id=event_basketball.id, name="决赛", stage="FINAL", sequence=1)
    round_volleyball = EventRound(event_id=event_volleyball.id, name="决赛", stage="FINAL", sequence=1)
    round_tt_team = EventRound(event_id=event_tt_team.id, name="决赛", stage="FINAL", sequence=1)
    round_tt_ms = EventRound(event_id=event_tt_ms.id, name="决赛", stage="FINAL", sequence=1)
    round_tt_ws = EventRound(event_id=event_tt_ws.id, name="决赛", stage="FINAL", sequence=1)
    round_rope_single = EventRound(event_id=event_rope_single.id, name="决赛", stage="FINAL", sequence=1)
    round_rope_sync = EventRound(event_id=event_rope_sync.id, name="决赛", stage="FINAL", sequence=1)
    round_rope_fig8 = EventRound(event_id=event_rope_fig8.id, name="决赛", stage="FINAL", sequence=1)
    db.add_all([round_100, round_long, round_basketball, round_volleyball, round_tt_team, round_tt_ms, round_tt_ws, round_rope_single, round_rope_sync, round_rope_fig8])
    db.flush()
    start = datetime.now().replace(microsecond=0) + timedelta(days=5)
    db.add_all([
        EventSchedule(event_id=event_100.id, round_id=round_100.id, competition_at=start.replace(hour=9, minute=30), check_in_at=start.replace(hour=9, minute=0), venue="东田径场 · 主跑道", heat="决赛第1组", status="NOT_STARTED", published=True, operator_id=scorer.id),
        EventSchedule(event_id=event_long.id, round_id=round_long.id, competition_at=start.replace(hour=14, minute=0), check_in_at=start.replace(hour=13, minute=30), venue="东田径场 · 跳远区", heat="决赛", status="NOT_STARTED", published=True, operator_id=both.id),
        EventSchedule(event_id=event_rope_single.id, round_id=round_rope_single.id, competition_at=start.replace(hour=15, minute=0), check_in_at=start.replace(hour=14, minute=30), venue="体育馆主馆 · 跳绳区A", heat="第1组", status="NOT_STARTED", published=True, operator_id=scorer.id),
        EventSchedule(event_id=event_rope_sync.id, round_id=round_rope_sync.id, competition_at=start.replace(hour=15, minute=30), check_in_at=start.replace(hour=15, minute=0), venue="体育馆主馆 · 跳绳区B", heat="第1组", status="NOT_STARTED", published=True, operator_id=scorer.id),
        EventSchedule(event_id=event_rope_fig8.id, round_id=round_rope_fig8.id, competition_at=start.replace(hour=16, minute=0), check_in_at=start.replace(hour=15, minute=30), venue="体育馆主馆 · 中央场地", heat="第1组", status="NOT_STARTED", published=True, operator_id=scorer.id),
    ])
    db.add_all([
        EventAdminPermission(user_id=scorer.id, event_id=event_100.id, can_schedule=True, can_score=True, can_export=True, assigned_by_id=teacher.id),
        EventAdminPermission(user_id=referee.id, event_id=event_100.id, can_review=True, can_export=True, assigned_by_id=teacher.id),
        EventAdminPermission(user_id=both.id, event_id=event_long.id, can_schedule=True, can_score=True, can_review=True, can_export=True, assigned_by_id=teacher.id),
    ])
    for ev in [event_basketball, event_volleyball, event_tt_team, event_tt_ms, event_tt_ws, event_rope_single, event_rope_sync, event_rope_fig8]:
        for u in [teacher, scorer, both]:
            db.add(EventAdminPermission(user_id=u.id, event_id=ev.id, can_schedule=True, can_score=True, can_review=True, can_export=True, assigned_by_id=teacher.id))

    # 预置学院代表队
    college_names = ["信息工程学院", "机电工程学院", "建筑工程学院", "经济管理学院", "外国语学院", "艺术设计学院"]
    college_teams_map = {}
    for c_name in college_names:
        team = CollegeTeam(meet_id=meet.id, college=c_name, team_name=f"{c_name}代表队", leader_name="体育部领队", created_by_id=teacher.id)
        db.add(team)
        db.flush()
        college_teams_map[c_name] = team
        db.add(Registration(event_id=event_basketball.id, round_id=round_basketball.id, college_team_id=team.id, status="REGISTERED"))
        db.add(Registration(event_id=event_volleyball.id, round_id=round_volleyball.id, college_team_id=team.id, status="REGISTERED"))
        db.add(Registration(event_id=event_tt_team.id, round_id=round_tt_team.id, college_team_id=team.id, status="REGISTERED"))
        db.add(Registration(event_id=event_rope_single.id, round_id=round_rope_single.id, college_team_id=team.id, status="REGISTERED"))
        db.add(Registration(event_id=event_rope_sync.id, round_id=round_rope_sync.id, college_team_id=team.id, status="REGISTERED"))
        db.add(Registration(event_id=event_rope_fig8.id, round_id=round_rope_fig8.id, college_team_id=team.id, status="REGISTERED"))

    # 每个学院配置 3 男 3 女（满足混合团体 3男2女 以及 单打男3女3要求）
    student_data = [
        # 信息工程学院 (3男 3女)
        ("26001001", "张晨", "男", "信息工程学院", "软件工程", "软工2601", "11.24"),
        ("26001002", "李明", "男", "信息工程学院", "软件工程", "软工2601", None),
        ("26001003", "赵静", "女", "信息工程学院", "软件工程", "软工2601", None),
        ("26001004", "孙雨", "女", "信息工程学院", "软件工程", "软工2601", None),
        ("26001005", "王鹏", "男", "信息工程学院", "软件工程", "软工2601", None),
        ("26001006", "陈梦", "女", "信息工程学院", "软件工程", "软工2601", None),

        # 机电工程学院 (3男 3女)
        ("26002001", "李昊", "男", "机电工程学院", "机械设计", "机械2602", "11.31"),
        ("26002002", "王强", "男", "机电工程学院", "机械设计", "机械2602", None),
        ("26002003", "刘芳", "女", "机电工程学院", "机械设计", "机械2602", None),
        ("26002004", "陈婷", "女", "机电工程学院", "机械设计", "机械2602", None),
        ("26002005", "张伟", "男", "机电工程学院", "机械设计", "机械2602", None),
        ("26002006", "丁宁", "女", "机电工程学院", "机械设计", "机械2602", None),

        # 建筑工程学院 (3男 3女)
        ("26003001", "周宇", "男", "建筑工程学院", "土木工程", "土木2601", "11.46"),
        ("26003002", "杨帆", "男", "建筑工程学院", "土木工程", "土木2601", None),
        ("26003003", "吴雪", "女", "建筑工程学院", "土木工程", "土木2601", None),
        ("26003004", "郑洁", "女", "建筑工程学院", "土木工程", "土木2601", None),
        ("26003005", "马龙", "男", "建筑工程学院", "土木工程", "土木2601", None),
        ("26003006", "王曼昱", "女", "建筑工程学院", "土木工程", "土木2601", None),

        # 经济管理学院 (3男 3女)
        ("26004001", "林悦", "女", "经济管理学院", "工商管理", "工商2601", None),
        ("26004002", "黄伟", "男", "经济管理学院", "工商管理", "工商2601", None),
        ("26004003", "徐娜", "女", "经济管理学院", "工商管理", "工商2601", None),
        ("26004004", "何磊", "男", "经济管理学院", "工商管理", "工商2601", None),
        ("26004005", "樊振东", "男", "经济管理学院", "工商管理", "工商2601", None),
        ("26004006", "孙颖莎", "女", "经济管理学院", "工商管理", "工商2601", None),

        # 外国语学院 (3男 3女)
        ("26005001", "宋涛", "男", "外国语学院", "英语", "英语2601", None),
        ("26005002", "马骏", "男", "外国语学院", "英语", "英语2601", None),
        ("26005003", "韩梅", "女", "外国语学院", "英语", "英语2601", None),
        ("26005004", "董莉", "女", "外国语学院", "英语", "英语2601", None),
        ("26005005", "许昕", "男", "外国语学院", "英语", "英语2601", None),
        ("26005006", "刘诗雯", "女", "外国语学院", "英语", "英语2601", None),

        # 艺术设计学院 (3男 3女)
        ("26006001", "杜峰", "男", "艺术设计学院", "视觉传达", "视传2601", None),
        ("26006002", "高健", "男", "艺术设计学院", "视觉传达", "视传2601", None),
        ("26006003", "谢雅", "女", "艺术设计学院", "视觉传达", "视传2601", None),
        ("26006004", "冯琳", "女", "艺术设计学院", "视觉传达", "视传2601", None),
        ("26006005", "王楚钦", "男", "艺术设计学院", "视觉传达", "视传2601", None),
        ("26006006", "钱天一", "女", "艺术设计学院", "视觉传达", "视传2601", None),
    ]

    college_males = {}
    college_females = {}

    for index, (student_no, name, gender, college, major, class_name, result_value) in enumerate(student_data):
        student_user = _user(db, student_no, initial_student_password(student_no), Role.STUDENT, name, college, False)
        student = StudentRoster(student_no=student_no, name=name, gender=gender, college=college, major=major, class_name=class_name, activated=True, user_id=student_user.id)
        db.add(student)
        db.flush()

        # 关联学院代表队（混合团体赛 3男2女 / 排球队员）
        team = college_teams_map.get(college)
        if team:
            db.add(CollegeTeamMember(team_id=team.id, student_id=student.id, role_title="主力" if gender == "男" else "主力", is_starter=True))

        # 记录单打报名候选
        if gender == "男":
            college_males.setdefault(college, []).append(student)
        else:
            college_females.setdefault(college, []).append(student)

        # 田径 100m / 跳远 演示成绩
        if index in [0, 6, 12, 18]:
            target_event = event_100 if gender == "男" else event_long
            target_round = round_100 if gender == "男" else round_long
            pos = [0, 6, 12, 18].index(index)
            registration = Registration(event_id=target_event.id, round_id=target_round.id, student_id=student.id, bib_no=f"A{pos + 1:03d}", heat="第1组", lane=str(pos + 3))
            db.add(registration)
            db.flush()
            if result_value:
                result = Result(
                    event_id=target_event.id,
                    round_id=target_round.id,
                    registration_id=registration.id,
                    raw_value=Decimal(result_value),
                    competition_status="NORMAL",
                    rank=pos + 1,
                    points=Decimal([9, 7, 6][pos]),
                    state=ResultState.PUBLISHED,
                    entered_by_id=scorer.id,
                    reviewed_by_id=referee.id,
                    finalized_by_id=teacher.id,
                    publisher_id=teacher.id,
                    entered_at=utcnow() - timedelta(hours=2),
                    reviewed_at=utcnow() - timedelta(hours=1),
                    finalized_at=utcnow(),
                    published_at=utcnow(),
                    published_version=1,
                    published_raw_value=Decimal(result_value),
                    published_competition_status="NORMAL",
                    published_rank=pos + 1,
                    published_points=Decimal([9, 7, 6][pos]),
                )
                db.add(result)
                db.flush()
                for action, operator, to_state, delta in [
                    ("ENTER", scorer, "SUBMITTED", 2),
                    ("REVIEW", referee, "REVIEWED", 1),
                    ("PUBLISH", teacher, "PUBLISHED", 0),
                ]:
                    db.add(ResultReview(result_id=result.id, action=action, from_state=None, to_state=to_state, comment="演示流程记录", operator_id=operator.id, operator_name_snapshot=operator.display_name, operator_username_snapshot=operator.username, created_at=utcnow() - timedelta(hours=delta)))

    # 为乒乓球单打比赛注册各学院男、女各 3 名运动员（种子选手排序 1/2/3）
    for c_name in college_names:
        m_list = college_males.get(c_name, [])[:3]
        for seed_idx, s in enumerate(m_list, 1):
            db.add(Registration(event_id=event_tt_ms.id, round_id=round_tt_ms.id, student_id=s.id, heat=f"种子{seed_idx}", status="REGISTERED"))
        f_list = college_females.get(c_name, [])[:3]
        for seed_idx, s in enumerate(f_list, 1):
            db.add(Registration(event_id=event_tt_ws.id, round_id=round_tt_ws.id, student_id=s.id, heat=f"种子{seed_idx}", status="REGISTERED"))

    standard.locked_by_published_results = True
    db.commit()
