from __future__ import annotations

import statistics
from decimal import Decimal
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Event, EventRound, Registration, Result
from ..services import participant_for_registration


# Reasonable physical boundary checks based on typical college athletics
PHYSICAL_LIMITS: dict[str, dict[str, float]] = {
    # event code substring or unit
    "100": {"min": 9.58, "max": 60.0, "unit": "秒"},
    "200": {"min": 19.19, "max": 120.0, "unit": "秒"},
    "400": {"min": 43.03, "max": 240.0, "unit": "秒"},
    "800": {"min": 100.0, "max": 600.0, "unit": "秒"},
    "1500": {"min": 200.0, "max": 1200.0, "unit": "秒"},
    "跳远": {"min": 1.0, "max": 8.95, "unit": "米"},
    "跳高": {"min": 0.8, "max": 2.45, "unit": "米"},
    "铅球": {"min": 2.0, "max": 23.5, "unit": "米"},
    "前单跳": {"min": 10.0, "max": 4000.0, "unit": "次"},
    "集体单摇": {"min": 10.0, "max": 300.0, "unit": "秒"},
    "8字": {"min": 5.0, "max": 800.0, "unit": "次"},
}


def detect_result_anomalies(
    db: Session,
    event_id: int | None = None,
    meet_id: int | None = None,
) -> dict[str, Any]:
    """Inspect results and detect anomalies with heuristic and statistical checks."""
    stmt = select(Result)
    if event_id:
        stmt = stmt.where(Result.event_id == event_id)
    elif meet_id:
        stmt = stmt.join(Event, Result.event_id == Event.id).where(Event.meet_id == meet_id)

    results = list(db.scalars(stmt))
    total_scanned = len(results)

    anomalies: list[dict[str, Any]] = []

    # Group by event_id and round_id for group deviation analysis
    grouped_by_event_round: dict[tuple[int, int | None], list[Result]] = {}
    for r in results:
        key = (r.event_id, r.round_id)
        grouped_by_event_round.setdefault(key, []).append(r)

    # 1. Individual rule checks
    for r in results:
        event = db.get(Event, r.event_id)
        ev_name = event.name if event else f"项目 #{r.event_id}"
        reg = db.get(Registration, r.registration_id)
        part = participant_for_registration(db, reg)
        part_name = part.get("name") or "未知选手"
        st_no = part.get("student_no")
        college = part.get("college")
        round_row = db.get(EventRound, r.round_id) if r.round_id else None
        round_name = round_row.name if round_row else (event.stage if event else "")

        val = float(r.raw_value) if r.raw_value is not None else None
        status = (r.competition_status or "NORMAL").upper()

        # Check A: Status vs Value contradiction
        # Non-normal status (DNF, DNS, DQ) should not normally have valid non-zero score
        if status in ("DNF", "DNS", "DQ") and val is not None and val > 0:
            anomalies.append({
                "result_id": r.id,
                "event_id": r.event_id,
                "event_name": ev_name,
                "round_name": round_name,
                "participant_name": part_name,
                "student_no": st_no,
                "college": college,
                "field": "competition_status & raw_value",
                "value": f"{status} / {val}",
                "anomaly_level": "HIGH",
                "issue_type": "状态与成绩冲突",
                "reason": f"选手状态标记为【{status}】（未完赛/未到场/违规），但填报了有效成绩数值 ({val})",
                "suggested_action": "请裁判人工确认是否应将成绩清零，或纠正选手比赛状态为 NORMAL",
            })

        # Check B: NORMAL status but missing raw_value
        elif status == "NORMAL" and val is None and r.state != "DRAFT":
            anomalies.append({
                "result_id": r.id,
                "event_id": r.event_id,
                "event_name": ev_name,
                "round_name": round_name,
                "participant_name": part_name,
                "student_no": st_no,
                "college": college,
                "field": "raw_value",
                "value": "NULL",
                "anomaly_level": "MEDIUM",
                "issue_type": "缺失成绩数值",
                "reason": "选手状态为正常 (NORMAL)，但尚未录入成绩数值",
                "suggested_action": "请计分员补录该选手成绩或核查是否弃权",
            })

        # Check C: Negative or Zero value where not applicable
        elif val is not None and val <= 0 and status == "NORMAL":
            anomalies.append({
                "result_id": r.id,
                "event_id": r.event_id,
                "event_name": ev_name,
                "round_name": round_name,
                "participant_name": part_name,
                "student_no": st_no,
                "college": college,
                "field": "raw_value",
                "value": val,
                "anomaly_level": "HIGH",
                "issue_type": "非法非正数值",
                "reason": f"比赛项目正常完赛成绩不可为 0 或负数 (当前填报 {val})",
                "suggested_action": "请重新核实成绩并纠正录入",
            })

        # Check D: Physical limits check
        if val is not None and val > 0 and status == "NORMAL":
            for limit_key, limits in PHYSICAL_LIMITS.items():
                if limit_key in ev_name:
                    if val < limits["min"]:
                        anomalies.append({
                            "result_id": r.id,
                            "event_id": r.event_id,
                            "event_name": ev_name,
                            "round_name": round_name,
                            "participant_name": part_name,
                            "student_no": st_no,
                            "college": college,
                            "field": "raw_value",
                            "value": f"{val} {limits['unit']}",
                            "anomaly_level": "HIGH",
                            "issue_type": "超出人体物理极限(过低)",
                            "reason": f"成绩 {val} {limits['unit']} 明显优于人类/世界极限({limits['min']} {limits['unit']})，疑似计时单位有误或少输入数字",
                            "suggested_action": "请裁判长与终点计时长复核原始计时单",
                        })
                    elif val > limits["max"]:
                        anomalies.append({
                            "result_id": r.id,
                            "event_id": r.event_id,
                            "event_name": ev_name,
                            "round_name": round_name,
                            "participant_name": part_name,
                            "student_no": st_no,
                            "college": college,
                            "field": "raw_value",
                            "value": f"{val} {limits['unit']}",
                            "anomaly_level": "MEDIUM",
                            "issue_type": "数值过大可能异常",
                            "reason": f"成绩 {val} {limits['unit']} 远超出常规高校田径赛事用时/测距范围({limits['max']})",
                            "suggested_action": "核查录入时是否包含了分钟或额外字符",
                        })
                    break

    # 2. Group statistical outlier checks (Z-Score / IQR)
    for (ev_id, rd_id), group_results in grouped_by_event_round.items():
        valid_vals = [
            (r, float(r.raw_value))
            for r in group_results
            if r.raw_value is not None and r.competition_status == "NORMAL" and float(r.raw_value) > 0
        ]
        if len(valid_vals) >= 4:
            scores = [v for _, v in valid_vals]
            mean = statistics.mean(scores)
            stdev = statistics.stdev(scores) if len(scores) > 1 else 0

            if stdev > 0.001:
                for r, v in valid_vals:
                    z = abs(v - mean) / stdev
                    if z >= 3.0:
                        ev = db.get(Event, r.event_id)
                        reg = db.get(Registration, r.registration_id)
                        part = participant_for_registration(db, reg)
                        anomalies.append({
                            "result_id": r.id,
                            "event_id": r.event_id,
                            "event_name": ev.name if ev else "",
                            "round_name": "本轮比赛",
                            "participant_name": part.get("name") or "",
                            "student_no": part.get("student_no"),
                            "college": part.get("college"),
                            "field": "raw_value",
                            "value": v,
                            "anomaly_level": "MEDIUM",
                            "issue_type": "同组严重离群(Z-Score > 3)",
                            "reason": f"该成绩 ({v}) 偏离同组其他选手平均水平达 {z:.1f} 个标准差 (组均值: {mean:.2f})",
                            "suggested_action": "建议裁判员人工核对当组原始比分记录表",
                        })

    high_count = sum(1 for a in anomalies if a["anomaly_level"] == "HIGH")
    med_count = sum(1 for a in anomalies if a["anomaly_level"] == "MEDIUM")
    low_count = sum(1 for a in anomalies if a["anomaly_level"] == "LOW")

    return {
        "total_scanned": total_scanned,
        "anomaly_count": len(anomalies),
        "high_count": high_count,
        "medium_count": med_count,
        "low_count": low_count,
        "items": anomalies,
    }
