import os
from decimal import Decimal
from pathlib import Path


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.database import Base, SessionLocal, engine, ensure_sqlite_team_registration_schema
from backend.app.main import app
from backend.app.models import (
    CollegeTeam,
    CollegeTeamMember,
    Event,
    EventRound,
    Registration,
    Result,
    ScoringModel,
    ScoringModelItem,
    SportsMeet,
    StudentRoster,
    TournamentMatch,
    User,
    Role,
)
from backend.app.seed import seed_database


@pytest.fixture(scope="session", autouse=True)
def fresh_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_team_registration_schema()
    with SessionLocal() as db:
        seed_database(db)
    yield
    engine.dispose()


def login(client: TestClient, username: str = "admin0001", password: str = "Admin123456!") -> dict:
    response = client.post("/api/v1/auth/admin-login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_table_tennis_team_rules_and_roster():
    """测试乒乓球混合团体赛 3男2女 名单配额检查与抽签拦截"""
    with TestClient(app) as client:
        headers = login(client)

        # 1. 查找乒乓球混合团体赛项目
        with SessionLocal() as db:
            tt_event = db.scalar(select(Event).where(Event.code == "TT_TEAM"))
            assert tt_event is not None
            event_id = tt_event.id

        # 2. 查询各队名单达标状态 (种子数据中每个学院代表队已配置 3男3女，均满足3男2女要求)
        res = client.get("/api/v1/sports-teacher/table-tennis/team/status", params={"event_id": event_id}, headers=headers)
        assert res.status_code == 200
        status_data = res.json()
        assert len(status_data["teams"]) >= 6
        assert status_data["all_compliant"] is True

        # 3. 测试若某队队员被清空导致不足 3男2女 时，分组抽签被拦截
        with SessionLocal() as db:
            first_team = db.scalar(select(CollegeTeam).limit(1))
            # 临时删除该队的队员
            db.query(CollegeTeamMember).filter(CollegeTeamMember.team_id == first_team.id).delete()
            db.commit()

        res_fail = client.post(
            "/api/v1/sports-teacher/table-tennis/team/groups/auto-generate",
            json={"event_id": event_id},
            headers=headers,
        )
        assert res_fail.status_code == 400
        assert "混合团体赛各学院必须上报3男、2女队员" in res_fail.json()["detail"]

        # 4. 恢复该学院队员（添加3男2女）
        with SessionLocal() as db:
            students = list(db.scalars(select(StudentRoster).where(StudentRoster.college == first_team.college)))
            for s in students:
                db.add(CollegeTeamMember(team_id=first_team.id, student_id=s.id, role_title="主力", is_starter=True))
            db.commit()

        # 再次抽签分组，应成功
        res_succ = client.post(
            "/api/v1/sports-teacher/table-tennis/team/groups/auto-generate",
            json={"event_id": event_id},
            headers=headers,
        )
        assert res_succ.status_code == 200
        assert "成功完成乒乓球混合团体赛抽签分组" in res_succ.json()["message"]


def test_table_tennis_team_match_scoring_and_forfeit():
    """测试混合团体赛 5 盘单打打满（男/女/男/女/男），胜2分负1分弃权0分与积分榜核算"""
    with TestClient(app) as client:
        headers = login(client)

        with SessionLocal() as db:
            tt_event = db.scalar(select(Event).where(Event.code == "TT_TEAM"))
            event_id = tt_event.id

        # 获取比赛列表
        res_matches = client.get("/api/v1/sports-teacher/table-tennis/team/matches", params={"event_id": event_id}, headers=headers)
        assert res_matches.status_code == 200
        matches = res_matches.json()
        assert len(matches) > 0

        # 录入第 1 场正常完赛比分（打满 5 盘，主队 3:2 胜出）
        m1 = matches[0]
        rubbers_m1 = [
            {"order": 1, "type": "MALE_SINGLES", "name": "男单1", "home_score": 2, "away_score": 0, "sets": [{"home": 11, "away": 9}, {"home": 11, "away": 8}]},
            {"order": 2, "type": "FEMALE_SINGLES", "name": "女单1", "home_score": 1, "away_score": 2, "sets": [{"home": 11, "away": 8}, {"home": 9, "away": 11}, {"home": 8, "away": 11}]},
            {"order": 3, "type": "MALE_SINGLES", "name": "男单2", "home_score": 2, "away_score": 1, "sets": [{"home": 11, "away": 7}, {"home": 8, "away": 11}, {"home": 11, "away": 9}]},
            {"order": 4, "type": "FEMALE_SINGLES", "name": "女单2", "home_score": 0, "away_score": 2, "sets": [{"home": 7, "away": 11}, {"home": 6, "away": 11}]},
            {"order": 5, "type": "MALE_SINGLES", "name": "男单3", "home_score": 2, "away_score": 0, "sets": [{"home": 11, "away": 6}, {"home": 11, "away": 8}]},
        ]
        res_score = client.put(
            f"/api/v1/sports-teacher/table-tennis/team/matches/{m1['id']}",
            json={"team_rubber_detail": rubbers_m1, "court_venue": "乒乓球1号台"},
            headers=headers,
        )
        assert res_score.status_code == 200
        m1_updated = res_score.json()["match"]
        assert m1_updated["home_score"] == 3
        assert m1_updated["away_score"] == 2
        assert m1_updated["winner_team_id"] == m1_updated["home_team_id"]

        # 录入第 2 场为弃权（客队弃权，判 5:0 胜，弃权方积 0 分，胜方积 2 分）
        if len(matches) > 1:
            m2 = matches[1]
            res_forfeit = client.put(
                f"/api/v1/sports-teacher/table-tennis/team/matches/{m2['id']}",
                json={"is_forfeit": True, "forfeit_team_id": m2["away_team_id"]},
                headers=headers,
            )
            assert res_forfeit.status_code == 200
            m2_updated = res_forfeit.json()["match"]
            assert m2_updated["status"] == "FORFEIT"
            assert m2_updated["home_score"] == 5
            assert m2_updated["away_score"] == 0

        # 录入剩余比赛比分
        for m in matches[2:]:
            rubbers = [
                {"order": 1, "type": "MALE_SINGLES", "home_score": 2, "away_score": 0},
                {"order": 2, "type": "FEMALE_SINGLES", "home_score": 2, "away_score": 0},
                {"order": 3, "type": "MALE_SINGLES", "home_score": 2, "away_score": 0},
                {"order": 4, "type": "FEMALE_SINGLES", "home_score": 0, "away_score": 2},
                {"order": 5, "type": "MALE_SINGLES", "home_score": 0, "away_score": 2},
            ]
            client.put(f"/api/v1/sports-teacher/table-tennis/team/matches/{m['id']}", json={"team_rubber_detail": rubbers}, headers=headers)

        # 检查积分榜与成绩最好第二名算法
        res_standings = client.get("/api/v1/sports-teacher/table-tennis/team/standings", params={"event_id": event_id}, headers=headers)
        assert res_standings.status_code == 200
        st_data = res_standings.json()
        assert "group_a" in st_data["groups"]
        assert "group_b" in st_data["groups"]
        # 验证胜积2分，负积1分，弃权积0分
        g_a = st_data["groups"]["group_a"]
        for t in g_a:
            expected_points = t["won"] * 2 + (t["lost"] - t["forfeited"]) * 1
            assert t["points"] == expected_points


def test_table_tennis_team_playoffs_and_finals():
    """测试混合团体赛第二阶段交叉半决赛、决胜赛与定稿归档"""
    with TestClient(app) as client:
        headers = login(client)

        with SessionLocal() as db:
            tt_event = db.scalar(select(Event).where(Event.code == "TT_TEAM"))
            event_id = tt_event.id

        # 1. 晋级第二阶段交叉半决赛
        res_adv = client.post("/api/v1/sports-teacher/table-tennis/team/advance-to-finals", json={"event_id": event_id}, headers=headers)
        assert res_adv.status_code == 200
        assert "已成功提取小组第一名及成绩最好第二名生成第二阶段交叉半决赛" in res_adv.json()["message"]

        # 2. 录入两场半决赛比分
        res_matches = client.get("/api/v1/sports-teacher/table-tennis/team/matches", params={"event_id": event_id}, headers=headers)
        sf_matches = [m for m in res_matches.json() if m["stage_type"] == "SEMIFINAL"]
        assert len(sf_matches) == 2

        for sf in sf_matches:
            rubbers = [
                {"order": 1, "home_score": 2, "away_score": 0},
                {"order": 2, "home_score": 2, "away_score": 1},
                {"order": 3, "home_score": 2, "away_score": 0},
                {"order": 4, "home_score": 0, "away_score": 2},
                {"order": 5, "home_score": 1, "away_score": 2},
            ]
            client.put(f"/api/v1/sports-teacher/table-tennis/team/matches/{sf['id']}", json={"team_rubber_detail": rubbers}, headers=headers)

        # 3. 生成决赛与季军赛
        res_finals = client.post("/api/v1/sports-teacher/table-tennis/team/generate-finals", json={"event_id": event_id}, headers=headers)
        assert res_finals.status_code == 200

        # 4. 录入决赛与季军赛比分
        res_matches = client.get("/api/v1/sports-teacher/table-tennis/team/matches", params={"event_id": event_id}, headers=headers)
        final_matches = [m for m in res_matches.json() if m["stage_type"] in ["FINAL", "THIRD_PLACE"]]
        assert len(final_matches) == 2

        for fm in final_matches:
            rubbers = [
                {"order": 1, "home_score": 2, "away_score": 0},
                {"order": 2, "home_score": 2, "away_score": 0},
                {"order": 3, "home_score": 2, "away_score": 0},
                {"order": 4, "home_score": 0, "away_score": 2},
                {"order": 5, "home_score": 0, "away_score": 2},
            ]
            client.put(f"/api/v1/sports-teacher/table-tennis/team/matches/{fm['id']}", json={"team_rubber_detail": rubbers}, headers=headers)

        # 5. 定稿归档前四名
        res_finalize = client.post("/api/v1/sports-teacher/table-tennis/team/finalize-results", json={"event_id": event_id}, headers=headers)
        assert res_finalize.status_code == 200
        assert "归档至公布台" in res_finalize.json()["message"]

        # 验证成绩表中的前四名积分（双倍系数：第1名18分，第2名14分，第3名12分，第4名10分）
        with SessionLocal() as db:
            results = list(db.scalars(select(Result).where(Result.event_id == event_id).order_by(Result.rank)))
            assert len(results) == 4
            assert results[0].rank == 1 and results[0].points == Decimal("18.00")
            assert results[1].rank == 2 and results[1].points == Decimal("14.00")
            assert results[2].rank == 3 and results[2].points == Decimal("12.00")
            assert results[3].rank == 4 and results[3].points == Decimal("10.00")


def test_table_tennis_singles_workflow():
    """测试男子/女子单打：报名配额、种子回避签表、前期三局两胜、进入八强五局三胜、决胜定稿"""
    with TestClient(app) as client:
        headers = login(client)

        with SessionLocal() as db:
            ms_event = db.scalar(select(Event).where(Event.code == "TT_MS"))
            assert ms_event is not None
            event_id = ms_event.id

        # 1. 查询报名运动员与种子排位（每个学院各 3 名运动员）
        res_athletes = client.get("/api/v1/sports-teacher/table-tennis/singles/athletes", params={"event_id": event_id}, headers=headers)
        assert res_athletes.status_code == 200
        ath_data = res_athletes.json()
        assert len(ath_data["athletes"]) >= 12
        for c, cnt in ath_data["college_counts"].items():
            assert cnt == 3  # 每学院 3 名选手

        # 2. 种子排序与同院回避签表编排 (前期淘汰赛为三局两胜制)
        res_draw = client.post("/api/v1/sports-teacher/table-tennis/singles/draw", json={"event_id": event_id}, headers=headers)
        assert res_draw.status_code == 200
        assert "成功完成单打签表编排" in res_draw.json()["message"]

        # 3. 获取首轮淘汰赛比赛
        res_matches = client.get("/api/v1/sports-teacher/table-tennis/singles/matches", params={"event_id": event_id}, headers=headers)
        assert res_matches.status_code == 200
        matches = res_matches.json()
        assert len(matches) > 0

        first_stage = matches[0]["stage_type"]
        initial_best_of = matches[0]["best_of"]

        # 4. 录入首轮比赛比分
        for m in matches:
            if initial_best_of == 3:
                # 三局两胜制，2:0 胜出
                sets = [{"set": 1, "home": 11, "away": 8}, {"set": 2, "home": 11, "away": 9}]
            else:
                # 五局三胜制，3:0 胜出
                sets = [{"set": 1, "home": 11, "away": 6}, {"set": 2, "home": 11, "away": 7}, {"set": 3, "home": 11, "away": 5}]
            res_put = client.put(f"/api/v1/sports-teacher/table-tennis/singles/matches/{m['id']}", json={"sets_detail": sets}, headers=headers)
            assert res_put.status_code == 200

        # 5. 晋级下一轮：验证进入八强（QUARTERFINAL）后自动切换为五局三胜制
        res_next = client.post(
            "/api/v1/sports-teacher/table-tennis/singles/advance-next-round",
            json={"event_id": event_id, "current_stage": first_stage},
            headers=headers,
        )
        assert res_next.status_code == 200

        res_matches2 = client.get("/api/v1/sports-teacher/table-tennis/singles/matches", params={"event_id": event_id}, headers=headers)
        new_matches = res_matches2.json()

        # 检查新轮次是否全部为五局三胜 (best_of == 5)
        unplayed = [m for m in new_matches if m["status"] == "NOT_STARTED"]
        assert len(unplayed) > 0
        for m in unplayed:
            assert m["best_of"] == 5

        # 录入五局三胜制比分并完赛到决赛
        curr_unplayed = unplayed
        while curr_unplayed:
            curr_stage = curr_unplayed[0]["stage_type"]
            for m in curr_unplayed:
                # 录入五局三胜（3:1 胜出）
                sets = [
                    {"set": 1, "home": 11, "away": 9},
                    {"set": 2, "home": 8, "away": 11},
                    {"set": 3, "home": 11, "away": 7},
                    {"set": 4, "home": 11, "away": 6},
                ]
                res_put = client.put(f"/api/v1/sports-teacher/table-tennis/singles/matches/{m['id']}", json={"sets_detail": sets}, headers=headers)
                assert res_put.status_code == 200

            if curr_stage in ["FINAL", "THIRD_PLACE"]:
                break

            res_adv = client.post(
                "/api/v1/sports-teacher/table-tennis/singles/advance-next-round",
                json={"event_id": event_id, "current_stage": curr_stage},
                headers=headers,
            )
            assert res_adv.status_code == 200

            all_m = client.get("/api/v1/sports-teacher/table-tennis/singles/matches", params={"event_id": event_id}, headers=headers).json()
            curr_unplayed = [m for m in all_m if m["status"] == "NOT_STARTED"]

        # 6. 定稿归档单打前四名成绩
        res_finalize = client.post("/api/v1/sports-teacher/table-tennis/singles/finalize-results", json={"event_id": event_id}, headers=headers)
        assert res_finalize.status_code == 200
        assert "归档至成绩公布台" in res_finalize.json()["message"]

        # 验证单打第1至4名积分（9, 7, 6, 5分）
        with SessionLocal() as db:
            results = list(db.scalars(select(Result).where(Result.event_id == event_id).order_by(Result.rank)))
            assert len(results) == 4
            assert results[0].rank == 1 and results[0].points == Decimal("9.00")
            assert results[1].rank == 2 and results[1].points == Decimal("7.00")
            assert results[2].rank == 3 and results[2].points == Decimal("6.00")
            assert results[3].rank == 4 and results[3].points == Decimal("5.00")


def test_public_table_tennis_api():
    """测试公开大屏端乒乓球赛况接口"""
    with TestClient(app) as client:
        res = client.get("/api/v1/public/table-tennis")
        assert res.status_code == 200
        data = res.json()
        assert data["has_tournament"] is True
        assert len(data["available_events"]) >= 3
