import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test_rope.db")
os.environ.setdefault("AUTO_SEED", "true")

from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.database import Base, SessionLocal, engine
from backend.app.main import app
from backend.app.models import CollegeTeam, CollegeTeamMember, Event, EventRound, Registration, Result, ScoringModel, ScoringModelBinding, StudentRoster
from backend.app.seed import seed_database


def _auth_header(client: TestClient, username: str = "admin0001", password: str = "Admin123456!") -> dict[str, str]:
    res = client.post("/api/v1/auth/admin-login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_rope_skipping_workflow():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)

    client = TestClient(app)
    headers = _auth_header(client, "admin0001")

    # 1. 验证跳绳三个项目已初始化且各学院代表队已报名
    res = client.get("/api/v1/sports-teacher/events", headers=headers)
    assert res.status_code == 200
    events = res.json()
    rope_single = next((e for e in events if e["code"] == "ROPE_SINGLE"), None)
    rope_sync = next((e for e in events if e["code"] == "ROPE_SYNC"), None)
    rope_fig8 = next((e for e in events if e["code"] == "ROPE_FIG8"), None)

    assert rope_single is not None, "跳绳前单跳项目不存在"
    assert rope_sync is not None, "跳绳集体单摇跳项目不存在"
    assert rope_fig8 is not None, "跳绳8字环绕跳项目不存在"

    # 2. 测试“前单跳”团体赛 (男女各5人累加总次数，次数多者列前)
    with SessionLocal() as db:
        r_single_round = db.scalar(select(EventRound).where(EventRound.event_id == rope_single["id"]))
        regs = list(db.scalars(select(Registration).where(Registration.event_id == rope_single["id"])))
        assert len(regs) >= 2
        reg1, reg2 = regs[0], regs[1]

    # 信息学院: 1680次, 机电学院: 1520次
    res1 = client.put("/api/v1/admin/results", json={
        "event_id": rope_single["id"],
        "round_id": r_single_round.id,
        "registration_id": reg1.id,
        "raw_value": 1680,
        "competition_status": "NORMAL",
        "notes": "前单跳 10人总次数: 1680次"
    }, headers=headers)
    assert res1.status_code == 200

    res2 = client.put("/api/v1/admin/results", json={
        "event_id": rope_single["id"],
        "round_id": r_single_round.id,
        "registration_id": reg2.id,
        "raw_value": 1520,
        "competition_status": "NORMAL",
        "notes": "前单跳 10人总次数: 1520次"
    }, headers=headers)
    assert res2.status_code == 200

    res_list = client.get(f"/api/v1/admin/results?event_id={rope_single['id']}&round_id={r_single_round.id}", headers=headers).json()
    assert len(res_list) == 2
    assert res_list[0]["raw_value"] == 1680
    assert res_list[0]["rank"] == 1
    assert res_list[1]["raw_value"] == 1520
    assert res_list[1]["rank"] == 2

    # 3. 测试“集体单摇跳” (用时少者名次居前，未在规定时间完成者按有效次数排在后面)
    with SessionLocal() as db:
        r_sync_round = db.scalar(select(EventRound).where(EventRound.event_id == rope_sync["id"]))
        sync_regs = list(db.scalars(select(Registration).where(Registration.event_id == rope_sync["id"])))
        assert len(sync_regs) >= 4

    # 队伍A: 32.5秒完成, 队伍B: 45.0秒完成, 队伍C: 未完成(26次, raw_value=1004), 队伍D: 未完成(20次, raw_value=1010)
    client.put("/api/v1/admin/results", json={"event_id": rope_sync["id"], "round_id": r_sync_round.id, "registration_id": sync_regs[0].id, "raw_value": 32.5, "competition_status": "NORMAL", "notes": "30次用时 32.5秒"}, headers=headers)
    client.put("/api/v1/admin/results", json={"event_id": rope_sync["id"], "round_id": r_sync_round.id, "registration_id": sync_regs[1].id, "raw_value": 45.0, "competition_status": "NORMAL", "notes": "30次用时 45.0秒"}, headers=headers)
    client.put("/api/v1/admin/results", json={"event_id": rope_sync["id"], "round_id": r_sync_round.id, "registration_id": sync_regs[2].id, "raw_value": 1004.0, "competition_status": "NORMAL", "notes": "未完成 (实跳26次)"}, headers=headers)
    client.put("/api/v1/admin/results", json={"event_id": rope_sync["id"], "round_id": r_sync_round.id, "registration_id": sync_regs[3].id, "raw_value": 1010.0, "competition_status": "NORMAL", "notes": "未完成 (实跳20次)"}, headers=headers)

    sync_res = client.get(f"/api/v1/admin/results?event_id={rope_sync['id']}&round_id={r_sync_round.id}", headers=headers).json()
    assert sync_res[0]["registration_id"] == sync_regs[0].id and sync_res[0]["rank"] == 1
    assert sync_res[1]["registration_id"] == sync_regs[1].id and sync_res[1]["rank"] == 2
    assert sync_res[2]["registration_id"] == sync_regs[2].id and sync_res[2]["rank"] == 3
    assert sync_res[3]["registration_id"] == sync_regs[3].id and sync_res[3]["rank"] == 4

    # 4. 测试发布流转与公开大屏
    result_ids = [r["id"] for r in sync_res]
    client.post("/api/v1/admin/results/submit", json={"result_ids": result_ids, "approve": True, "comment": "送审"}, headers=headers)
    client.post("/api/v1/admin/results/review", json={"result_ids": result_ids, "approve": True, "comment": "裁判长审核通过"}, headers=headers)
    client.post("/api/v1/sports-teacher/results/final-review", json={"result_ids": result_ids, "approve": True, "comment": "终审通过"}, headers=headers)
    pub_res = client.post("/api/v1/sports-teacher/results/publish", json={"result_ids": result_ids, "approve": True}, headers=headers)
    assert pub_res.status_code == 200

    public_data = client.get("/api/v1/public/results").json()
    assert any(item["event_name"] == rope_sync["name"] for item in public_data)


def _fill_team_to_22(db: Session, team: CollegeTeam) -> tuple[list[int], list[int]]:
    existing = list(db.scalars(select(CollegeTeamMember).where(CollegeTeamMember.team_id == team.id)))
    male_ids = []
    female_ids = []
    for member in existing:
        student = db.get(StudentRoster, member.student_id)
        (male_ids if student.gender == "男" else female_ids).append(student.id)
    for gender, target in [("男", male_ids), ("女", female_ids)]:
        while len(target) < 11:
            index = len(target) + 1
            student = StudentRoster(
                student_no=f"R{team.id:03d}{'M' if gender == '男' else 'F'}{index:03d}",
                name=f"{team.college}{gender}队员{index}",
                gender=gender,
                college=team.college,
                major="跳绳专项",
                class_name="跳绳队",
            )
            db.add(student)
            db.flush()
            db.add(CollegeTeamMember(team_id=team.id, student_id=student.id, role_title="跳绳队员", is_starter=True))
            target.append(student.id)
    db.commit()
    return male_ids, female_ids


def _lineup_payload(event: dict, team_id: int, male_ids: list[int], female_ids: list[int]) -> dict:
    if event["code"] in {"ROPE_SINGLE", "ROPE_SYNC"}:
        jumpers = male_ids[:5] + female_ids[:5]
    else:
        jumpers = male_ids[:10] + female_ids[:10]
    turners = [] if event["code"] == "ROPE_SINGLE" else [male_ids[-1], female_ids[-1]]
    members = [
        {"student_id": student_id, "role": "JUMPER", "sequence": index}
        for index, student_id in enumerate(jumpers, 1)
    ] + [
        {"student_id": student_id, "role": "TURNER", "sequence": index}
        for index, student_id in enumerate(turners, 1)
    ]
    return {"event_id": event["id"], "college_team_id": team_id, "members": members}


def test_structured_rope_lineups_results_and_tie_points():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)

    with TestClient(app) as client:
        headers = _auth_header(client, "admin0001")
        meet_id = client.get("/api/v1/sports-teacher/meets", headers=headers).json()[0]["id"]
        initialized = client.post("/api/v1/sports-teacher/rope/initialize", headers=headers, json={"meet_id": meet_id})
        assert initialized.status_code == 200, initialized.text
        # 初始化/同步必须可重复执行，且不会重复创建项目、轮次、报名或计分模型。
        for _ in range(2):
            repeated = client.post("/api/v1/sports-teacher/rope/initialize", headers=headers, json={"meet_id": meet_id})
            assert repeated.status_code == 200, repeated.text
            assert "新增 0 个项目、0 条学院报名记录" in repeated.json()["message"]
        status = client.get("/api/v1/sports-teacher/rope/status", headers=headers, params={"meet_id": meet_id}).json()
        events = {event["code"]: event for event in status["events"]}
        assert set(events) == {"ROPE_SINGLE", "ROPE_SYNC", "ROPE_FIG8"}
        event_ids = [event["id"] for event in events.values()]
        with SessionLocal() as db:
            generic_team_count = db.scalar(select(func.count(CollegeTeam.id)).where(CollegeTeam.meet_id == meet_id, CollegeTeam.event_id.is_(None)))
            assert db.scalar(select(func.count(Event.id)).where(Event.meet_id == meet_id, Event.code.in_(events))) == 3
            assert db.scalar(select(func.count(EventRound.id)).where(EventRound.event_id.in_(event_ids))) == 9
            assert db.scalar(select(func.count(EventRound.id)).where(EventRound.event_id.in_(event_ids), EventRound.stage == "FINAL")) == 3
            assert db.scalar(select(func.count(Registration.id)).where(Registration.event_id.in_(event_ids))) == generic_team_count * 3
            assert db.scalar(select(func.count(ScoringModel.id)).where(ScoringModel.name.like("跳绳赛制计分模型%"))) == 1
            assert db.scalar(select(func.count(ScoringModelBinding.id)).where(ScoringModelBinding.event_id.in_(event_ids))) == 3

        first_team = events["ROPE_SINGLE"]["teams"][0]
        invalid = client.put(
            "/api/v1/sports-teacher/rope/lineups",
            headers=headers,
            json={
                "event_id": events["ROPE_SINGLE"]["id"],
                "college_team_id": first_team["team_id"],
                "members": [
                    {"student_id": member["student_id"], "role": "JUMPER", "sequence": index}
                    for index, member in enumerate(first_team["members"], 1)
                ],
            },
        )
        assert invalid.status_code == 422
        assert "必须登记 22 人" in invalid.json()["detail"]

        team_ids = [team["team_id"] for team in events["ROPE_SINGLE"]["teams"][:4]]
        assert len(team_ids) == 4
        rosters = {}
        with SessionLocal() as db:
            for team_id in team_ids:
                rosters[team_id] = _fill_team_to_22(db, db.get(CollegeTeam, team_id))

        # 学院队总人数边界：21 拒绝、22 接受、23 拒绝。
        boundary_team_id = team_ids[2]
        boundary_males, boundary_females = rosters[boundary_team_id]
        with SessionLocal() as db:
            removed_member = db.scalar(
                select(CollegeTeamMember).where(
                    CollegeTeamMember.team_id == boundary_team_id,
                    CollegeTeamMember.student_id == boundary_males[-1],
                )
            )
            db.delete(removed_member)
            db.commit()
        count_21 = client.put(
            "/api/v1/sports-teacher/rope/lineups",
            headers=headers,
            json=_lineup_payload(events["ROPE_SINGLE"], boundary_team_id, boundary_males, boundary_females),
        )
        assert count_21.status_code == 422 and "当前 21 人" in count_21.json()["detail"]
        with SessionLocal() as db:
            db.add(CollegeTeamMember(team_id=boundary_team_id, student_id=boundary_males[-1], role_title="跳绳队员", is_starter=True))
            extra = StudentRoster(
                student_no=f"R{boundary_team_id:03d}EXTRA",
                name="跳绳边界测试额外队员",
                gender="男",
                college=db.get(CollegeTeam, boundary_team_id).college,
                major="跳绳专项",
                class_name="跳绳队",
            )
            db.add(extra)
            db.flush()
            db.add(CollegeTeamMember(team_id=boundary_team_id, student_id=extra.id, role_title="跳绳队员", is_starter=True))
            db.commit()
            extra_id = extra.id
        count_23 = client.put(
            "/api/v1/sports-teacher/rope/lineups",
            headers=headers,
            json=_lineup_payload(events["ROPE_SINGLE"], boundary_team_id, boundary_males, boundary_females),
        )
        assert count_23.status_code == 422 and "当前 23 人" in count_23.json()["detail"]
        with SessionLocal() as db:
            db.delete(db.scalar(select(CollegeTeamMember).where(CollegeTeamMember.team_id == boundary_team_id, CollegeTeamMember.student_id == extra_id)))
            db.commit()

        # 直接绕过前端调用 API 时，错误男女比例和同一学生角色/阵容重复仍必须拒绝。
        wrong_gender = _lineup_payload(events["ROPE_SINGLE"], boundary_team_id, boundary_males, boundary_females)
        wrong_gender["members"] = [
            {"student_id": student_id, "role": "JUMPER", "sequence": index}
            for index, student_id in enumerate(boundary_males[:6] + boundary_females[:4], 1)
        ]
        wrong_gender_response = client.put("/api/v1/sports-teacher/rope/lineups", headers=headers, json=wrong_gender)
        assert wrong_gender_response.status_code == 422 and "当前男 6 人、女 4 人" in wrong_gender_response.json()["detail"]
        duplicate_role = _lineup_payload(events["ROPE_SYNC"], boundary_team_id, boundary_males, boundary_females)
        duplicate_role["members"][-1]["student_id"] = duplicate_role["members"][0]["student_id"]
        duplicate_response = client.put("/api/v1/sports-teacher/rope/lineups", headers=headers, json=duplicate_role)
        assert duplicate_response.status_code == 422 and "不能在同一项目阵容中重复" in duplicate_response.json()["detail"]

        for event in events.values():
            for team_id in team_ids:
                male_ids, female_ids = rosters[team_id]
                saved = client.put(
                    "/api/v1/sports-teacher/rope/lineups",
                    headers=headers,
                    json=_lineup_payload(event, team_id, male_ids, female_ids),
                )
                assert saved.status_code == 200, saved.text
                assert saved.json()["status"]["valid"] is True

        refreshed = client.get("/api/v1/sports-teacher/rope/status", headers=headers, params={"meet_id": meet_id}).json()
        refreshed_events = {event["code"]: event for event in refreshed["events"]}
        for event in refreshed_events.values():
            assert all(team["lineup_status"]["valid"] for team in event["teams"] if team["team_id"] in team_ids)

        single = refreshed_events["ROPE_SINGLE"]
        single_teams = [team for team in single["teams"] if team["team_id"] in team_ids]
        for index, team in enumerate(single_teams):
            response = client.put(
                "/api/v1/admin/rope/results",
                headers=headers,
                json={
                    "event_id": single["id"],
                    "round_id": single["round_id"],
                    "registration_id": team["registration_id"],
                    "individual_counts": [100 if index < 3 else 90] * 10,
                },
            )
            assert response.status_code == 200, response.text
        single_results = client.get(
            "/api/v1/admin/results",
            headers=headers,
            params={"event_id": single["id"], "round_id": single["round_id"]},
        ).json()
        assert [row["rank"] for row in single_results] == [1, 1, 1, 4]
        # 三队并列第一占用第 1—3 名，积分为 (9 + 7 + 6) / 3；下一队必须为第 4 名。
        assert all(float(row["points"]) == 7.33 for row in single_results[:3])
        assert float(single_results[3]["points"]) == 5.0
        assert all(row["rope_detail"]["individual_counts"] == [100] * 10 for row in single_results[:3])

        sync = refreshed_events["ROPE_SYNC"]
        sync_teams = [team for team in sync["teams"] if team["team_id"] in team_ids[:2]]
        completed = client.put(
            "/api/v1/admin/rope/results",
            headers=headers,
            json={"event_id": sync["id"], "round_id": sync["round_id"], "registration_id": sync_teams[0]["registration_id"], "completed_target": True, "elapsed_seconds": 42.5},
        )
        incomplete = client.put(
            "/api/v1/admin/rope/results",
            headers=headers,
            json={"event_id": sync["id"], "round_id": sync["round_id"], "registration_id": sync_teams[1]["registration_id"], "completed_target": False, "completed_count": 28},
        )
        assert completed.status_code == 200, completed.text
        assert incomplete.status_code == 200, incomplete.text
        sync_results = client.get(
            "/api/v1/admin/results",
            headers=headers,
            params={"event_id": sync["id"], "round_id": sync["round_id"]},
        ).json()
        assert sync_results[0]["rope_detail"]["completed_target"] is True
        assert sync_results[0]["rank"] == 1
        assert sync_results[1]["rope_detail"]["completed_count"] == 28
        assert sync_results[1]["rank"] == 2

        fig8 = refreshed_events["ROPE_FIG8"]
        fig8_teams = [team for team in fig8["teams"] if team["team_id"] in team_ids[:2]]
        for team in fig8_teams:
            response = client.put(
                "/api/v1/admin/rope/results",
                headers=headers,
                json={"event_id": fig8["id"], "round_id": fig8["round_id"], "registration_id": team["registration_id"], "completed_count": 188},
            )
            assert response.status_code == 200, response.text
        fig8_results = client.get(
            "/api/v1/admin/results",
            headers=headers,
            params={"event_id": fig8["id"], "round_id": fig8["round_id"]},
        ).json()
        assert [row["rank"] for row in fig8_results] == [1, 1]
        assert all(float(row["points"]) == 8.0 for row in fig8_results)

        result_ids = [row["id"] for row in fig8_results]
        action_payload = {"result_ids": result_ids, "approve": True, "comment": "跳绳赛制发布快照测试"}
        submitted = client.post("/api/v1/admin/results/submit", headers=headers, json=action_payload)
        reviewed = client.post("/api/v1/admin/results/review", headers=headers, json=action_payload)
        final_reviewed = client.post("/api/v1/sports-teacher/results/final-review", headers=headers, json=action_payload)
        published = client.post("/api/v1/sports-teacher/results/publish", headers=headers, json=action_payload)
        assert submitted.status_code == 200, submitted.text
        assert reviewed.status_code == 200, reviewed.text
        assert final_reviewed.status_code == 200, final_reviewed.text
        assert published.status_code == 200, published.text

        public_results = client.get("/api/v1/public/results", params={"event_id": fig8["id"]})
        assert public_results.status_code == 200, public_results.text
        public_rows = public_results.json()
        assert len(public_rows) == 2
        assert [row["rank"] for row in public_rows] == [1, 1]
        assert all(float(row["points"]) == 8.0 for row in public_rows)
        assert all(row["rope_detail"]["completed_count"] == 188 for row in public_rows)
