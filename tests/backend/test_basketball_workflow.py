import os
from io import BytesIO
from pathlib import Path


from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from backend.app.database import Base, SessionLocal, engine
from backend.app.main import app
from backend.app.models import Event, EventRound, CollegeTeam, TournamentMatch, Result, Role, User
from backend.app.seed import seed_database


@pytest.fixture(scope="session", autouse=True)
def fresh_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    yield
    engine.dispose()


def login(client: TestClient, kind: str, username: str, password: str) -> dict:
    response = client.post(f"/api/v1/auth/{kind}-login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_basketball_full_tournament_workflow():
    with TestClient(app) as client:
        teacher = login(client, "admin", "admin0001", "Admin123456!")
        auth = headers(teacher["access_token"])

        # 1. 获取运动会与代表队
        meets = client.get("/api/v1/sports-teacher/meets", headers=auth).json()
        meet_id = meets[0]["id"]

        # 创建 6 支学院代表队
        colleges = ["信息学院", "机电学院", "经管学院", "建筑学院", "艺术学院", "外国语学院"]
        team_ids = []
        for c in colleges:
            t = client.post("/api/v1/sports-teacher/college-teams", headers=auth, json={"meet_id": meet_id, "college": c, "team_name": f"{c}男篮"})
            if t.status_code == 200:
                team_ids.append(t.json()["id"])
            else:
                existing = client.get("/api/v1/sports-teacher/college-teams", headers=auth, params={"meet_id": meet_id}).json()
                team_ids.append(next(item["id"] for item in existing if item["college"] == c))

        # 2. 创建篮球比赛项目 (男子篮球)
        event_res = client.post(
            "/api/v1/sports-teacher/events",
            headers=auth,
            json={
                "meet_id": meet_id,
                "code": "MBB2026",
                "name": "男子篮球赛",
                "gender_group": "MALE",
                "event_type": "TEAM",
                "result_unit": "分",
                "sort_direction": "DESC",
                "stage": "FINAL",
                "scoring_places": 4,
                "points_multiplier": 2,
            },
        )
        assert event_res.status_code == 200, event_res.text
        event_id = event_res.json()["id"]

        # 获取生成的轮次并加入名单
        roster = client.get("/api/v1/sports-teacher/event-registrations", headers=auth, params={"event_id": event_id}).json()
        round_id = roster["rounds"][0]["id"]

        add_reg = client.post(
            "/api/v1/sports-teacher/event-registrations/batch",
            headers=auth,
            json={"event_id": event_id, "round_id": round_id, "participant_ids": team_ids},
        )
        assert add_reg.status_code == 200, add_reg.text

        # 3. 第一阶段：A / B 组抽签分组与单循环赛程生成 (A组3队, B组3队)
        gen = client.post(
            "/api/v1/sports-teacher/basketball/groups/auto-generate",
            headers=auth,
            json={"event_id": event_id, "a_team_ids": team_ids[:3], "b_team_ids": team_ids[3:]},
        )
        assert gen.status_code == 200, gen.text
        assert gen.json()["a_count"] == 3
        assert gen.json()["b_count"] == 3

        matches = client.get("/api/v1/sports-teacher/basketball/matches", headers=auth, params={"event_id": event_id}).json()
        assert len(matches) == 6  # 3场A组 + 3场B组

        # 4. 录入小组赛比分（胜者+2分，负者+1分）
        # A 组比赛
        a_matches = [m for m in matches if m["stage_type"] == "GROUP_A"]
        client.put(f"/api/v1/sports-teacher/basketball/matches/{a_matches[0]['id']}", headers=auth, json={"home_score": 85, "away_score": 70})
        client.put(f"/api/v1/sports-teacher/basketball/matches/{a_matches[1]['id']}", headers=auth, json={"home_score": 90, "away_score": 60})
        client.put(f"/api/v1/sports-teacher/basketball/matches/{a_matches[2]['id']}", headers=auth, json={"home_score": 75, "away_score": 65})

        # B 组比赛
        b_matches = [m for m in matches if m["stage_type"] == "GROUP_B"]
        client.put(f"/api/v1/sports-teacher/basketball/matches/{b_matches[0]['id']}", headers=auth, json={"home_score": 78, "away_score": 68})
        client.put(f"/api/v1/sports-teacher/basketball/matches/{b_matches[1]['id']}", headers=auth, json={"home_score": 82, "away_score": 62})
        client.put(f"/api/v1/sports-teacher/basketball/matches/{b_matches[2]['id']}", headers=auth, json={"home_score": 70, "away_score": 60})

        # 5. 验证小组积分榜（胜2分、负1分）
        standings = client.get("/api/v1/sports-teacher/basketball/standings", headers=auth, params={"event_id": event_id}).json()
        assert len(standings["group_a"]) == 3
        assert len(standings["group_b"]) == 3
        # 第一名全胜应积 4 分 (2场胜)
        assert standings["group_a"][0]["points"] == 4
        assert standings["group_a"][0]["won"] == 2

        # 6. 第二阶段：依据小组前两名生成半决赛 (A1 vs B2, B1 vs A2)
        adv = client.post("/api/v1/sports-teacher/basketball/advance-to-finals", headers=auth, json={"event_id": event_id})
        assert adv.status_code == 200, adv.text

        all_matches = client.get("/api/v1/sports-teacher/basketball/matches", headers=auth, params={"event_id": event_id}).json()
        sf_matches = [m for m in all_matches if m["stage_type"] == "SEMIFINAL"]
        assert len(sf_matches) == 2

        # 7. 录入半决赛比分
        client.put(f"/api/v1/sports-teacher/basketball/matches/{sf_matches[0]['id']}", headers=auth, json={"home_score": 95, "away_score": 88})
        client.put(f"/api/v1/sports-teacher/basketball/matches/{sf_matches[1]['id']}", headers=auth, json={"home_score": 76, "away_score": 80})

        # 8. 生成冠亚军总决赛 & 三四名季军赛
        gen_finals = client.post("/api/v1/sports-teacher/basketball/generate-finals", headers=auth, json={"event_id": event_id})
        assert gen_finals.status_code == 200, gen_finals.text

        final_matches = client.get("/api/v1/sports-teacher/basketball/matches", headers=auth, params={"event_id": event_id}).json()
        third_m = next(m for m in final_matches if m["stage_type"] == "THIRD_PLACE")
        champ_m = next(m for m in final_matches if m["stage_type"] == "FINAL")

        # 9. 录入决赛与季军赛比分
        client.put(f"/api/v1/sports-teacher/basketball/matches/{third_m['id']}", headers=auth, json={"home_score": 72, "away_score": 68})
        client.put(f"/api/v1/sports-teacher/basketball/matches/{champ_m['id']}", headers=auth, json={"home_score": 89, "away_score": 85})

        # 10. 决出前四名并一键定稿归档至成绩公布台
        fin = client.post("/api/v1/sports-teacher/basketball/finalize-results", headers=auth, json={"event_id": event_id})
        assert fin.status_code == 200, fin.text

        # 11. 验证在成绩公布台生成了前四名成绩记录
        results_in_admin = client.get("/api/v1/admin/results", headers=auth, params={"event_id": event_id}).json()
        assert len(results_in_admin) == 4
        # 第1名冠军应该获得积分 9 * 2 = 18 分
        first_place = next(r for r in results_in_admin if r["rank"] == 1)
        assert float(first_place["points"]) == 18.0

        # 12. 发布到大屏并验证公开端
        pub = client.post("/api/v1/sports-teacher/results/publish", headers=auth, json={"result_ids": [r["id"] for r in results_in_admin]})
        assert pub.status_code == 200, pub.text

        public_bball = client.get("/api/v1/public/basketball", params={"event_id": event_id}).json()
        assert public_bball["has_tournament"] is True
        assert len(public_bball["matches"]) >= 10
