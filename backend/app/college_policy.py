"""学校参加团体比赛的学院范围。已有配置时按配置校验。"""
import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import SystemSetting

DEFAULT_COLLEGES = (
    "信息工程学院", "机电工程学院", "外国语学院", "食品工程学院",
    "艺术设计学院", "建筑工程学院", "人文学院",
)


def configured_colleges(db: Session) -> list[str] | None:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "participating_colleges"))
    if setting is None:
        return None
    try:
        colleges = json.loads(setting.value)
        if not isinstance(colleges, list) or any(not isinstance(value, str) or not value.strip() for value in colleges):
            raise ValueError()
        return list(dict.fromkeys(value.strip() for value in colleges))
    except (ValueError, TypeError) as exc:
        raise HTTPException(500, "参赛学院配置格式不正确，请联系开发人员") from exc


def require_participating_college(db: Session, college: str) -> None:
    allowed = configured_colleges(db)
    if allowed is not None and college.strip() not in allowed:
        raise HTTPException(422, "该学院不在本校参赛学院范围内，请选择：" + "、".join(allowed))
