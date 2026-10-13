"""目标Render七学院同步的隔离数据验证。"""
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from backend.app.database import Base
from backend.app.seed import seed_database
from backend.app.models import CollegeTeam, StudentRoster, User
from backend.app.college_policy import DEFAULT_COLLEGES, configured_colleges, require_participating_college
from backend.app.college_maintenance import synchronize_render_colleges
from fastapi import HTTPException
import pytest


def test_render_sync_limits_colleges_and_keeps_accounts_students_and_repeat_state(tmp_path):
    local_engine = create_engine(f'sqlite:///{(tmp_path / "college_scope.db").as_posix()}')
    try:
        Base.metadata.create_all(local_engine)
        with Session(local_engine) as db:
            seed_database(db)
            users = db.scalar(select(func.count(User.id)))
            students = db.scalar(select(func.count(StudentRoster.id)))
            synchronize_render_colleges(db)
            db.commit()
            assert configured_colleges(db) == list(DEFAULT_COLLEGES)
            assert set(db.scalars(select(CollegeTeam.college))) == set(DEFAULT_COLLEGES)
            assert db.scalar(select(func.count(User.id))) == users
            assert db.scalar(select(func.count(StudentRoster.id))) == students
            require_participating_college(db, '食品工程学院')
            with pytest.raises(HTTPException) as error:
                require_participating_college(db, '名单外学院')
            assert error.value.status_code == 422
            db.commit()
            synchronize_render_colleges(db)
            db.commit()
            assert db.scalar(select(func.count(CollegeTeam.id))) == 7
    finally:
        local_engine.dispose()
