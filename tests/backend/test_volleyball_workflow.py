import os
from io import BytesIO
from pathlib import Path


from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from backend.app.database import Base, SessionLocal, engine
from backend.app.main import app
from backend.app.models import Event, EventRound, CollegeTeam, CollegeTeamMember, TournamentMatch, Result, Role, User, StudentRoster
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


def test_volleyball_full_tournament_and_gender_rules_workflow():
    with TestClient(app) as client:
        teacher = login(client, "admin", "admin0001", "Admin123456!")
        auth = headers(teacher["access_token"])

        # 1. 获取运动会与代表队
        meets = client.get("/api/v1/sports-teacher/meets", headers=auth).json()
        meet_id = meets[0]["id"]

        # 创建 6 支学院代表队
        colleges = ["软件学院", "自动化学院", "经管学院", "数理学院", "材料学院", "外语学院"]
        team_ids = []
        for c in colleges:
            t = client.post("/api/v1/sports-teacher/college-teams", headers=auth, json={"meet_id": meet_id, "college": c, "team_name": f"{c}排球队"})
            if t.status_code == 200:
                team_ids.append(t.json()["id"])
            else:
                existing = client.get("/api/v1/sports-teacher/college-teams", headers=auth, params={"meet_id": meet_id}).json()
                team_ids.append(next(item["id"] for item in existing if item["college"] == c))

        # 为各代表队创建学生名单（男、女生）
        for idx, c in enumerate(colleges):
            # 每队创建 2 名男生和 2 名女生（满足女生不少于 2 人）
            s_m1 = client.post("/api/v1/sports-teacher/students", headers=auth, json={"student_no": f"2699{idx:02d}01", "name": f"{c}男甲", "gender": "男", "college": c, "major": "通用专业", "class_name": "2601"}).json()
            s_m2 = client.post("/api/v1/sports-teacher/students", headers=auth, json={"student_no": f"2699{idx:02d}02", "name": f"{c}男乙", "gender": "男", "college": c, "major": "通用专业", "class_name": "2601"}).json()
            s_f1 = client.post("/api/v1/sports-teacher/students", headers=auth, json={"student_no": f"2699{idx:02d}03", "name": f"{c}女甲", "gender": "女", "college": c, "major": "通用专业", "class_name": "2601"}).json()
            s_f2 = client.post("/api/v1/sports-teacher/students", headers=auth, json={"student_no": f"2699{idx:02d}04", "name": f"{c}女乙", "gender": "女", "college": c, "major": "通用专业", "class_name": "2601"}).json()

            # 前 5 队正常添加 2 女 2 男，第 6 队先只加 1 女 2 男（用于测试性别不足警告）
            if idx < 5:
                client.post(f"/api/v1/sports-teacher/college-teams/{team_ids[idx]}/members/batch", headers=auth, json={"student_ids": [s_m1["id"], s_m2["id"], s_f1["id"], s_f2["id"]]})
            else:
                client.post(f"/api/v1/sports-teacher/college-teams/{team_ids[idx]}/members/batch", headers=auth, json={"student_ids": [s_m1["id"], s_m2["id"], s_f1["id"]]})

        # 2. 一键创建排球赛事项目
        event_res = client.post(
            "/api/v1/sports-teacher/volleyball/quick-create-event",
            headers=auth,
            json={"meet_id": meet_id, "name": "男女混合排球联赛", "code": "VB2026", "gender_group": "MIXED"},
        )
        assert event_res.status_code == 200, event_res.text
        event_id = event_res.json()["event"]["id"]

        # 3. 关联代表队
        add_teams_res = client.post(
            "/api/v1/sports-teacher/volleyball/add-teams",
            headers=auth,
            json={"event_id": event_id, "team_ids": team_ids},
        )
        assert add_teams_res.status_code == 200, add_teams_res.text

        # 4. 尝试 A/B 组抽签生成赛程（因第 6 队女生只有 1 人，应触发拦截提示）
        gen_fail = client.post(
            "/api/v1/sports-teacher/volleyball/groups/auto-generate",
            headers=auth,
            json={"event_id": event_id, "a_team_ids": team_ids[:3], "b_team_ids": team_ids[3:]},
        )
        assert gen_fail.status_code == 400
        assert "女生不能低于两人" in gen_fail.json()["detail"]

        # 为第 6 队补足第 2 名女生队员
        s_f2_last = client.get("/api/v1/sports-teacher/students", headers=auth, params={"keyword": f"{colleges[5]}女乙"}).json()["items"][0]
        client.post(f"/api/v1/sports-teacher/college-teams/{team_ids[5]}/members", headers=auth, json={"student_id": s_f2_last["id"], "role_title": "主攻"})

        # 再次抽签分组，校验通过
        gen_ok = client.post(
            "/api/v1/sports-teacher/volleyball/groups/auto-generate",
            headers=auth,
            json={"event_id": event_id, "a_team_ids": team_ids[:3], "b_team_ids": team_ids[3:]},
        )
        assert gen_ok.status_code == 200, gen_ok.text
        assert gen_ok.json()["a_count"] == 3
        assert gen_ok.json()["b_count"] == 3

        matches = client.get("/api/v1/sports-teacher/volleyball/matches", headers=auth, params={"event_id": event_id}).json()
        assert len(matches) == 6  # 3场A组 + 3场B组

        # 5. 第一阶段比分录入与测试计分模型（胜4分，1:2负2分，0:2负1分，弃权0分判2:0）
        # A 组比赛：
        a_matches = [m for m in matches if m["stage_type"] == "GROUP_A"]
        # 第1场：2:0 胜（胜方拿4分，负方0:2拿1分）
        client.put(
            f"/api/v1/sports-teacher/volleyball/matches/{a_matches[0]['id']}",
            headers=auth,
            json={"sets_detail": [{"home": 25, "away": 18}, {"home": 25, "away": 20}]},
        )
        # 第2场：2:1 胜（胜方拿4分，负方1:2拿2分）
        client.put(
            f"/api/v1/sports-teacher/volleyball/matches/{a_matches[1]['id']}",
            headers=auth,
            json={"sets_detail": [{"home": 25, "away": 21}, {"home": 22, "away": 25}, {"home": 25, "away": 19}]},
        )
        # 第3场：客队迟到15分钟弃权（主队 2:0 胜积4分，客队弃权积0分）
        client.put(
            f"/api/v1/sports-teacher/volleyball/matches/{a_matches[2]['id']}",
            headers=auth,
            json={"is_forfeit": True, "forfeit_team_id": a_matches[2]["away_team_id"]},
        )

        # B 组比赛：
        b_matches = [m for m in matches if m["stage_type"] == "GROUP_B"]
        client.put(
            f"/api/v1/sports-teacher/volleyball/matches/{b_matches[0]['id']}",
            headers=auth,
            json={"sets_detail": [{"home": 25, "away": 15}, {"home": 25, "away": 17}]},
        )
        client.put(
            f"/api/v1/sports-teacher/volleyball/matches/{b_matches[1]['id']}",
            headers=auth,
            json={"sets_detail": [{"home": 25, "away": 20}, {"home": 25, "away": 22}]},
        )
        client.put(
            f"/api/v1/sports-teacher/volleyball/matches/{b_matches[2]['id']}",
            headers=auth,
            json={"sets_detail": [{"home": 25, "away": 23}, {"home": 25, "away": 21}]},
        )

        # 6. 验证排球积分榜（胜4分，负1:2积2分，负0:2积1分，弃权0分）
        standings = client.get("/api/v1/sports-teacher/volleyball/standings", headers=auth, params={"event_id": event_id}).json()
        assert len(standings["group_a"]) == 3
        assert len(standings["group_b"]) == 3

        # A 组第1名全胜应积 8 分（2场胜）
        assert standings["group_a"][0]["points"] == 8
        assert standings["group_a"][0]["won"] == 2
        # A 组第2名积 4 分
        assert standings["group_a"][1]["points"] >= 2

        # 7. 第二阶段：依据排球积分榜提取小组前二名（A1, A2, B1, B2）生成交叉半决赛
        adv = client.post("/api/v1/sports-teacher/volleyball/advance-to-finals", headers=auth, json={"event_id": event_id})
        assert adv.status_code == 200, adv.text

        sf_matches = [m for m in client.get("/api/v1/sports-teacher/volleyball/matches", headers=auth, params={"event_id": event_id}).json() if m["stage_type"] == "SEMIFINAL"]
        assert len(sf_matches) == 2

        # 8. 录入半决赛三局两胜比分
        client.put(f"/api/v1/sports-teacher/volleyball/matches/{sf_matches[0]['id']}", headers=auth, json={"sets_detail": [{"home": 25, "away": 20}, {"home": 25, "away": 19}]})
        client.put(f"/api/v1/sports-teacher/volleyball/matches/{sf_matches[1]['id']}", headers=auth, json={"sets_detail": [{"home": 21, "away": 25}, {"home": 25, "away": 22}, {"home": 25, "away": 23}]})

        # 9. 生成冠亚军总决赛及三四名季军赛
        gen_finals = client.post("/api/v1/sports-teacher/volleyball/generate-finals", headers=auth, json={"event_id": event_id})
        assert gen_finals.status_code == 200, gen_finals.text

        final_matches = client.get("/api/v1/sports-teacher/volleyball/matches", headers=auth, params={"event_id": event_id}).json()
        third_m = next(m for m in final_matches if m["stage_type"] == "THIRD_PLACE")
        champ_m = next(m for m in final_matches if m["stage_type"] == "FINAL")

        # 10. 录入决赛与季军赛比分
        client.put(f"/api/v1/sports-teacher/volleyball/matches/{third_m['id']}", headers=auth, json={"sets_detail": [{"home": 25, "away": 22}, {"home": 25, "away": 20}]})
        client.put(f"/api/v1/sports-teacher/volleyball/matches/{champ_m['id']}", headers=auth, json={"sets_detail": [{"home": 25, "away": 23}, {"home": 23, "away": 25}, {"home": 25, "away": 21}]})

        # 11. 定稿前四名成绩并验证成绩公布台
        fin = client.post("/api/v1/sports-teacher/volleyball/finalize-results", headers=auth, json={"event_id": event_id})
        assert fin.status_code == 200, fin.text

        results_in_admin = client.get("/api/v1/admin/results", headers=auth, params={"event_id": event_id}).json()
        assert len(results_in_admin) == 4
        # 第1名冠军应该获得积分 9 * 2 = 18 分
        first_place = next(r for r in results_in_admin if r["rank"] == 1)
        assert float(first_place["points"]) == 18.0

        # 12. 发布至大屏并验证公开端
        pub = client.post("/api/v1/sports-teacher/results/publish", headers=auth, json={"result_ids": [r["id"] for r in results_in_admin]})
        assert pub.status_code == 200, pub.text

        public_vb = client.get("/api/v1/public/volleyball", params={"event_id": event_id}).json()
        assert public_vb["has_tournament"] is True
        assert len(public_vb["matches"]) >= 10
        assert len(public_vb["standings"]["group_a"]) == 3
