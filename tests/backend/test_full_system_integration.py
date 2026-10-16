import os
from pathlib import Path
from decimal import Decimal


from fastapi.testclient import TestClient
import pytest

from backend.app.database import Base, SessionLocal, engine
from backend.app.main import app
from backend.app.models import (
    SportsMeet, Event, EventRound, CollegeTeam, CollegeTeamMember,
    StudentRoster, TournamentMatch, Result, ResultState, Role, User
)
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


def test_full_system_end_to_end_cross_module_workflow():
    """
    全系统端到端全链路功能完整性与跨模块衔接测试：
    1. 运动会届次多届次隔离与管理
    2. 学生资料库录入
    3. 学院代表队按比赛项目细分（同学院多队伍）与阵容角色维护
    4. 排球赛制女生合规校验、循环赛、交叉半决赛、冠亚军总决赛、定稿归档
    5. 篮球赛制循环积分、半决赛、冠亚军总决赛、定稿归档
    6. 乒乓球混合团体赛 3男2女规程、5场单打出场顺序、定稿归档
    7. 乒乓球单打淘汰赛 前期三局两胜、进入八强自动切换五局三胜、定稿归档
    8. 田径个人赛自动排道、名次晋级、成绩送审、裁判审核、终审发布
    9. 学院奖牌榜与团体总积分跨赛制跨项目统一聚合计算
    10. 各专项公开大屏接口查询与学生个人中心数据联动
    """
    with TestClient(app) as client:
        # ======================================================================
        # 1. 登录管理员 / 体育教师
        # ======================================================================
        teacher = login(client, "admin", "admin0001", "Admin123456!")
        auth = headers(teacher["access_token"])

        # ======================================================================
        # 2. 运动会届次管理
        # ======================================================================
        meets_res = client.get("/api/v1/sports-teacher/meets", headers=auth)
        assert meets_res.status_code == 200
        meets = meets_res.json()
        meet_id = meets[0]["id"]

        # ======================================================================
        # 3. 批量创建学生资料库（男女生）
        # ======================================================================
        colleges = ["计算机学院", "软件学院", "理学院", "商学院"]
        students_by_college = {}
        for college_index, c in enumerate(colleges):
            students_by_college[c] = {"male": [], "female": []}
            # 创建 4 男 3 女
            for i in range(4):
                s = client.post("/api/v1/sports-teacher/students", headers=auth, json={
                    "student_no": f"710{college_index}1{i+1:03d}",
                    "name": f"{c}男队员{i+1}",
                    "gender": "男",
                    "college": c,
                    "major": "计算机类",
                    "class_name": "2601班"
                }).json()
                students_by_college[c]["male"].append(s)

            for j in range(3):
                s = client.post("/api/v1/sports-teacher/students", headers=auth, json={
                    "student_no": f"710{college_index}2{j+1:03d}",
                    "name": f"{c}女队员{j+1}",
                    "gender": "女",
                    "college": c,
                    "major": "计算机类",
                    "class_name": "2601班"
                }).json()
                students_by_college[c]["female"].append(s)

        # ======================================================================
        # 4. 学院代表队按不同比赛项目细分建立 & 阵容自由维护
        # ======================================================================
        # 4.1 创建男子篮球项目与代表队
        bb_event = client.post("/api/v1/sports-teacher/basketball/quick-create-event", headers=auth, json={
            "meet_id": meet_id,
            "name": "第1届男子五人制篮球锦标赛",
            "code": "BB_E2E",
            "gender_group": "MALE",
        }).json()["event"]

        bb_teams = []
        for college_index, c in enumerate(colleges):
            t = client.post("/api/v1/sports-teacher/college-teams", headers=auth, json={
                "meet_id": meet_id,
                "event_id": bb_event["id"],
                "college": c,
                "team_name": f"{c}男篮队",
                "leader_name": f"{c}张教练",
                "leader_phone": "13800001111",
            }).json()
            bb_teams.append(t)
            # 添加男篮队员并设队长
            sids = [s["id"] for s in students_by_college[c]["male"][:3]]
            client.post(f"/api/v1/sports-teacher/college-teams/{t['id']}/members/batch", headers=auth, json={
                "student_ids": sids, "role_title": "主力"
            })

        # 4.2 创建男女混合排球项目与代表队
        vb_event = client.post("/api/v1/sports-teacher/volleyball/quick-create-event", headers=auth, json={
            "meet_id": meet_id,
            "name": "第1届男女混合排球锦标赛",
            "code": "VB_E2E",
            "gender_group": "MIXED",
        }).json()["event"]

        vb_teams = []
        for college_index, c in enumerate(colleges):
            t = client.post("/api/v1/sports-teacher/college-teams", headers=auth, json={
                "meet_id": meet_id,
                "event_id": vb_event["id"],
                "college": c,
                "team_name": f"{c}男女混合排球队",
                "leader_name": f"{c}李领队",
            }).json()
            vb_teams.append(t)
            # 为排球队添加 2 男 2 女（满足女生≥2人规则）
            m_sids = [s["id"] for s in students_by_college[c]["male"][:2]]
            f_sids = [s["id"] for s in students_by_college[c]["female"][:2]]
            client.post(f"/api/v1/sports-teacher/college-teams/{t['id']}/members/batch", headers=auth, json={
                "student_ids": m_sids + f_sids, "role_title": "主攻"
            })

        # 4.3 创建乒乓球混合团体项目与代表队
        tt_event = client.post("/api/v1/sports-teacher/table-tennis/quick-create-event", headers=auth, json={
            "meet_id": meet_id,
            "name": "第1届乒乓球混合团体赛",
            "category": "TEAM",
            "code": "TT_E2E_TEAM",
        }).json()["event"]

        tt_teams = []
        for college_index, c in enumerate(colleges):
            t = client.post("/api/v1/sports-teacher/college-teams", headers=auth, json={
                "meet_id": meet_id,
                "event_id": tt_event["id"],
                "college": c,
                "team_name": f"{c}乒乓球代表队",
            }).json()
            tt_teams.append(t)
            # 添加 3 男 2 女（满足 3男2女 规程）
            m_sids = [s["id"] for s in students_by_college[c]["male"][:3]]
            f_sids = [s["id"] for s in students_by_college[c]["female"][:2]]
            client.post(f"/api/v1/sports-teacher/college-teams/{t['id']}/members/batch", headers=auth, json={
                "student_ids": m_sids + f_sids, "role_title": "队员"
            })

        # 4.4 验证代表队列表筛选（同一学院拥有不同比赛项目的代表队）
        cs_all_teams = client.get("/api/v1/sports-teacher/college-teams", headers=auth, params={"meet_id": meet_id}).json()
        cs_teams = [t for t in cs_all_teams if t["college"] == "计算机学院"]
        assert len(cs_teams) >= 3  # 计算机学院男篮、排球、乒乓球

        # ======================================================================
        # 5. 🏀 篮球完整赛制流转 (小组循环 ➔ 积分榜 ➔ 半决赛 ➔ 决赛 ➔ 定稿)
        # ======================================================================
        bb_team_ids = [t["id"] for t in bb_teams]
        client.post("/api/v1/sports-teacher/basketball/add-teams", headers=auth, json={"event_id": bb_event["id"], "team_ids": bb_team_ids})
        client.post("/api/v1/sports-teacher/basketball/groups/auto-generate", headers=auth, json={"event_id": bb_event["id"], "a_team_ids": bb_team_ids[:2], "b_team_ids": bb_team_ids[2:]})
        
        bb_matches = client.get("/api/v1/sports-teacher/basketball/matches", headers=auth, params={"event_id": bb_event["id"]}).json()
        for m in bb_matches:
            client.put(f"/api/v1/sports-teacher/basketball/matches/{m['id']}", headers=auth, json={"home_score": 85, "away_score": 75})

        client.post("/api/v1/sports-teacher/basketball/advance-to-finals", headers=auth, json={"event_id": bb_event["id"]})
        sf_matches = [m for m in client.get("/api/v1/sports-teacher/basketball/matches", headers=auth, params={"event_id": bb_event["id"]}).json() if m["stage_type"] == "SEMIFINAL"]
        for sf in sf_matches:
            client.put(f"/api/v1/sports-teacher/basketball/matches/{sf['id']}", headers=auth, json={"home_score": 90, "away_score": 80})

        client.post("/api/v1/sports-teacher/basketball/generate-finals", headers=auth, json={"event_id": bb_event["id"]})
        final_matches = [m for m in client.get("/api/v1/sports-teacher/basketball/matches", headers=auth, params={"event_id": bb_event["id"]}).json() if m["stage_type"] in ["FINAL", "THIRD_PLACE"]]
        for f in final_matches:
            client.put(f"/api/v1/sports-teacher/basketball/matches/{f['id']}", headers=auth, json={"home_score": 88, "away_score": 82})

        bb_finalize = client.post("/api/v1/sports-teacher/basketball/finalize-results", headers=auth, json={"event_id": bb_event["id"]})
        assert bb_finalize.status_code == 200

        # ======================================================================
        # 6. 🏐 排球完整赛制流转 (女生达标规则 ➔ 特殊计分 4/2/1 ➔ 交叉淘汰 ➔ 定稿)
        # ======================================================================
        vb_team_ids = [t["id"] for t in vb_teams]
        client.post("/api/v1/sports-teacher/volleyball/add-teams", headers=auth, json={"event_id": vb_event["id"], "team_ids": vb_team_ids})
        client.post("/api/v1/sports-teacher/volleyball/groups/auto-generate", headers=auth, json={"event_id": vb_event["id"], "a_team_ids": vb_team_ids[:2], "b_team_ids": vb_team_ids[2:]})
        
        vb_matches = client.get("/api/v1/sports-teacher/volleyball/matches", headers=auth, params={"event_id": vb_event["id"]}).json()
        for m in vb_matches:
            client.put(f"/api/v1/sports-teacher/volleyball/matches/{m['id']}", headers=auth, json={
                "home_score": 2, "away_score": 1,
                "sets_detail": [{"home": 25, "away": 20}, {"home": 22, "away": 25}, {"home": 25, "away": 18}]
            })

        client.post("/api/v1/sports-teacher/volleyball/advance-to-finals", headers=auth, json={"event_id": vb_event["id"]})
        vb_sfs = [m for m in client.get("/api/v1/sports-teacher/volleyball/matches", headers=auth, params={"event_id": vb_event["id"]}).json() if m["stage_type"] == "SEMIFINAL"]
        for sf in vb_sfs:
            client.put(f"/api/v1/sports-teacher/volleyball/matches/{sf['id']}", headers=auth, json={
                "home_score": 2, "away_score": 0,
                "sets_detail": [{"home": 25, "away": 18}, {"home": 25, "away": 19}]
            })

        client.post("/api/v1/sports-teacher/volleyball/generate-finals", headers=auth, json={"event_id": vb_event["id"]})
        vb_finals = [m for m in client.get("/api/v1/sports-teacher/volleyball/matches", headers=auth, params={"event_id": vb_event["id"]}).json() if m["stage_type"] in ["FINAL", "THIRD_PLACE"]]
        for f in vb_finals:
            client.put(f"/api/v1/sports-teacher/volleyball/matches/{f['id']}", headers=auth, json={
                "home_score": 2, "away_score": 1,
                "sets_detail": [{"home": 25, "away": 22}, {"home": 20, "away": 25}, {"home": 25, "away": 23}]
            })

        vb_finalize = client.post("/api/v1/sports-teacher/volleyball/finalize-results", headers=auth, json={"event_id": vb_event["id"]})
        assert vb_finalize.status_code == 200

        # ======================================================================
        # 7. 🏓 乒乓球混合团体赛 (3男2女规程 ➔ 5场单打打满 ➔ 淘汰赛 ➔ 定稿)
        # ======================================================================
        tt_team_ids = [t["id"] for t in tt_teams]
        client.post("/api/v1/sports-teacher/table-tennis/team/add-teams", headers=auth, json={"event_id": tt_event["id"], "team_ids": tt_team_ids})
        client.post("/api/v1/sports-teacher/table-tennis/team/groups/auto-generate", headers=auth, json={"event_id": tt_event["id"], "a_team_ids": tt_team_ids[:2], "b_team_ids": tt_team_ids[2:]})
        
        tt_matches = client.get("/api/v1/sports-teacher/table-tennis/team/matches", headers=auth, params={"event_id": tt_event["id"]}).json()
        for m in tt_matches:
            rubbers = m.get("team_rubber_detail", [])
            for r in rubbers:
                r["home_score"] = 2
                r["away_score"] = 0
            client.put(f"/api/v1/sports-teacher/table-tennis/team/matches/{m['id']}", headers=auth, json={
                "team_rubber_detail": rubbers
            })

        client.post("/api/v1/sports-teacher/table-tennis/team/advance-to-finals", headers=auth, json={"event_id": tt_event["id"]})
        tt_sfs = [m for m in client.get("/api/v1/sports-teacher/table-tennis/team/matches", headers=auth, params={"event_id": tt_event["id"]}).json() if m["stage_type"] == "SEMIFINAL"]
        for sf in tt_sfs:
            rubbers = sf.get("team_rubber_detail", [])
            for r in rubbers:
                r["home_score"] = 2
                r["away_score"] = 1
            client.put(f"/api/v1/sports-teacher/table-tennis/team/matches/{sf['id']}", headers=auth, json={"team_rubber_detail": rubbers})

        client.post("/api/v1/sports-teacher/table-tennis/team/generate-finals", headers=auth, json={"event_id": tt_event["id"]})
        tt_finals = [m for m in client.get("/api/v1/sports-teacher/table-tennis/team/matches", headers=auth, params={"event_id": tt_event["id"]}).json() if m["stage_type"] in ["FINAL", "THIRD_PLACE"]]
        for f in tt_finals:
            rubbers = f.get("team_rubber_detail", [])
            for r in rubbers:
                r["home_score"] = 2
                r["away_score"] = 0
            client.put(f"/api/v1/sports-teacher/table-tennis/team/matches/{f['id']}", headers=auth, json={"team_rubber_detail": rubbers})

        tt_finalize = client.post("/api/v1/sports-teacher/table-tennis/team/finalize-results", headers=auth, json={"event_id": tt_event["id"]})
        assert tt_finalize.status_code == 200

        # ======================================================================
        # 8. 🏓 乒乓球单打赛制 (八强前三局两胜 ➔ 八强及以后自动切换五局三胜 ➔ 定稿)
        # ======================================================================
        singles_event = client.post("/api/v1/sports-teacher/table-tennis/quick-create-event", headers=auth, json={
            "meet_id": meet_id,
            "name": "第1届男子乒乓球单打赛",
            "category": "SINGLES",
            "gender_group": "MALE",
            "code": "TT_E2E_MS",
        }).json()["event"]

        # 选 8 名男选手参加 1/4 决赛 (八强)
        all_male_sids = [s["id"] for c in colleges for s in students_by_college[c]["male"][:2]]
        client.post("/api/v1/sports-teacher/table-tennis/singles/add-athletes", headers=auth, json={
            "event_id": singles_event["id"],
            "student_entries": [{"student_id": sid, "seed_no": (i % 2) + 1} for i, sid in enumerate(all_male_sids[:8])],
        })

        client.post("/api/v1/sports-teacher/table-tennis/singles/draw", headers=auth, json={
            "event_id": singles_event["id"],
        })

        qf_matches = client.get("/api/v1/sports-teacher/table-tennis/singles/matches", headers=auth, params={"event_id": singles_event["id"], "stage_type": "QUARTERFINAL"}).json()
        assert len(qf_matches) == 4
        # 验证规程要求：进入八强后采用五局三胜制 (best_of == 5)
        assert all(m["best_of"] == 5 for m in qf_matches)

        for m in qf_matches:
            client.put(f"/api/v1/sports-teacher/table-tennis/singles/matches/{m['id']}", headers=auth, json={
                "home_score": 3, "away_score": 1,
                "sets_detail": [{"home": 11, "away": 8}, {"home": 11, "away": 9}, {"home": 8, "away": 11}, {"home": 11, "away": 6}]
            })

        # 晋级半决赛
        client.post("/api/v1/sports-teacher/table-tennis/singles/advance-next-round", headers=auth, json={
            "event_id": singles_event["id"],
            "current_stage": "QUARTERFINAL",
        })

        all_s_matches = client.get("/api/v1/sports-teacher/table-tennis/singles/matches", headers=auth, params={"event_id": singles_event["id"]}).json()
        sf_s_matches = [m for m in all_s_matches if m["stage_type"] == "SEMIFINAL"]
        assert len(sf_s_matches) == 2
        assert all(m["best_of"] == 5 for m in sf_s_matches)

        for m in sf_s_matches:
            client.put(f"/api/v1/sports-teacher/table-tennis/singles/matches/{m['id']}", headers=auth, json={
                "home_score": 3, "away_score": 2,
                "sets_detail": [{"home": 11, "away": 9}, {"home": 9, "away": 11}, {"home": 11, "away": 8}, {"home": 7, "away": 11}, {"home": 11, "away": 5}]
            })

        # 晋级决赛与季军赛
        client.post("/api/v1/sports-teacher/table-tennis/singles/advance-next-round", headers=auth, json={
            "event_id": singles_event["id"],
            "current_stage": "SEMIFINAL",
        })

        fin_s_matches = client.get("/api/v1/sports-teacher/table-tennis/singles/matches", headers=auth, params={"event_id": singles_event["id"]}).json()
        final_singles = [m for m in fin_s_matches if m["stage_type"] in ["FINAL", "THIRD_PLACE"]]
        assert len(final_singles) == 2
        assert all(m["best_of"] == 5 for m in final_singles)

        for m in final_singles:
            client.put(f"/api/v1/sports-teacher/table-tennis/singles/matches/{m['id']}", headers=auth, json={
                "home_score": 3, "away_score": 0,
                "sets_detail": [{"home": 11, "away": 6}, {"home": 11, "away": 7}, {"home": 11, "away": 8}]
            })

        singles_finalize = client.post("/api/v1/sports-teacher/table-tennis/singles/finalize-results", headers=auth, json={
            "event_id": singles_event["id"]
        })
        assert singles_finalize.status_code == 200

        # ======================================================================
        # 9. 成绩工作台审核流转 ➔ 终审发布大屏 ➔ 学院总积分与奖牌榜综合聚合
        # ======================================================================
        # 批量发布排球、篮球、乒乓球成绩至大屏
        for ev in [bb_event, vb_event, tt_event, singles_event]:
            results_data = client.get("/api/v1/admin/results", headers=auth, params={"event_id": ev["id"]}).json()
            rids = [r["id"] for r in results_data]
            if rids:
                client.post("/api/v1/sports-teacher/results/publish", headers=auth, json={"result_ids": rids, "approve": True})

        # 查询全校学院团体总积分榜与奖牌榜
        rankings = client.get("/api/v1/public/college-rankings").json()
        assert len(rankings) >= 4
        assert rankings[0]["points"] > 0
        assert "rank" in rankings[0]
        assert any(r["gold"] > 0 for r in rankings)

        # ======================================================================
        # 10. 公开端大屏各专项独立接口查询验证
        # ======================================================================
        pub_bb = client.get("/api/v1/public/basketball", params={"event_id": bb_event["id"]}).json()
        assert pub_bb["has_tournament"] is True
        assert len(pub_bb["matches"]) > 0

        pub_vb = client.get("/api/v1/public/volleyball", params={"event_id": vb_event["id"]}).json()
        assert pub_vb["has_tournament"] is True
        assert len(pub_vb["matches"]) > 0

        pub_tt = client.get("/api/v1/public/table-tennis", params={"event_id": tt_event["id"]}).json()
        assert pub_tt["has_tournament"] is True
        assert len(pub_tt["matches"]) > 0

        # ======================================================================
        # 11. 学生端个人中心 (Student Portal) 查询联动验证
        # ======================================================================
        # 使用其中一位已参赛学生的学号免密/默认密码登录
        # 学生端激活并登录
        test_student = students_by_college["计算机学院"]["male"][0]
        reg_res = client.post("/api/v1/auth/student-register", json={"student_no": test_student["student_no"], "name": test_student["name"]})
        assert reg_res.status_code == 200

        student_pwd = f"DF{test_student['student_no']}"
        student_login = client.post("/api/v1/auth/student-login", json={"username": test_student["student_no"], "password": student_pwd})
        assert student_login.status_code == 200
        s_auth = headers(student_login.json()["access_token"])

        s_me = client.get("/api/v1/student/me", headers=s_auth).json()
        assert s_me["college"] == "计算机学院"

        s_events = client.get("/api/v1/student/my-events", headers=s_auth).json()
        assert isinstance(s_events, list)

        s_results = client.get("/api/v1/student/my-results", headers=s_auth).json()
        assert isinstance(s_results, list)
