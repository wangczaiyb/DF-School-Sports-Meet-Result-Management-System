"""回归：基础学院齐全但跳绳项目只关联5学院时，补齐8学院且保留已有业务数据。"""
from datetime import date
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.api import ROPE_EVENT_CONFIG, router
from backend.app.college_policy import DEFAULT_COLLEGES
from backend.app.database import Base, get_db
from backend.app.dependencies import business_admin
from backend.app.models import CollegeTeam, Event, EventRound, Registration, Result, Role, SportsMeet, SystemSetting, User
from backend.app.rope_college_sync import synchronize_existing_rope_meets, synchronize_rope_colleges


@pytest.fixture
def context():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        actor = User(username='teacher', display_name='体育部老师', role=Role.SPORTS_TEACHER,
                     password_hash='unused', status='ACTIVE')
        db.add(actor)
        db.flush()
        meet = SportsMeet(name='学院同步验证', edition='2026', start_date=date(2026, 10, 20), end_date=date(2026, 10, 21), created_by_id=actor.id)
        db.add(meet)
        db.add(SystemSetting(key='participating_colleges', value=json.dumps(list(DEFAULT_COLLEGES)), updated_by_id=actor.id))
        db.flush()
        teams = []
        for college in [DEFAULT_COLLEGES[index] for index in [0, 1, 2, 4, 5]]:
            team = CollegeTeam(meet_id=meet.id, college=college, team_name=f'{college}代表队', created_by_id=actor.id)
            db.add(team)
            teams.append(team)
        db.flush()
        for code, config in ROPE_EVENT_CONFIG.items():
            event = Event(meet_id=meet.id, code=code, name=config['name'], gender_group='MIXED',
                          event_type='TEAM', result_unit=config['unit'], sort_direction=config['sort'], stage='FINAL')
            db.add(event)
            db.flush()
            final = EventRound(event_id=event.id, name='决赛', stage='FINAL', sequence=3, qualification_count=0)
            db.add(final)
            db.flush()
            for index, team in enumerate(teams):
                registration = Registration(event_id=event.id, round_id=final.id, college_team_id=team.id,
                                            status='WITHDRAWN' if index == 4 else 'REGISTERED')
                db.add(registration)
                db.flush()
                if code == 'ROPE_SINGLE' and index == 0:
                    db.add(Result(event_id=event.id, round_id=final.id, registration_id=registration.id,
                                  raw_value=1000, rank=1, points=9, state='PUBLISHED', published_raw_value=1000,
                                  published_rank=1, published_points=9, published_version=1))
        db.commit()
        app = FastAPI()
        app.include_router(router, prefix='/api/v1')
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[business_admin] = lambda: actor
        with TestClient(app) as client:
            yield db, actor, meet, client
    engine.dispose()


def assert_eight_colleges(client, meet_id):
    response = client.get('/api/v1/sports-teacher/rope/status', params={'meet_id': meet_id})
    assert response.status_code == 200, response.text
    events = response.json()['events']
    assert len(events) == 3
    for event in events:
        assert len(event['teams']) == 8
        assert {team['college'] for team in event['teams']} == set(DEFAULT_COLLEGES)


def test_sync_creates_missing_total_teams_and_registrations_without_overwriting(context):
    db, actor, meet, client = context
    results_before = db.execute(Result.__table__.select()).all()
    registrations_before = db.execute(Registration.__table__.select()).all()
    report = synchronize_rope_colleges(db, meet.id, actor)
    db.commit()
    assert report == {'created_teams': 3, 'created_registrations': 9, 'college_count': 8}
    assert_eight_colleges(client, meet.id)
    assert db.execute(Result.__table__.select()).all() == results_before
    existing_ids = [row.id for row in registrations_before]
    assert db.execute(Registration.__table__.select().where(Registration.id.in_(existing_ids))).all() == registrations_before
    assert synchronize_rope_colleges(db, meet.id, actor) == {'created_teams': 0, 'created_registrations': 0, 'college_count': 8}


def test_startup_repairs_eight_existing_teams_with_only_five_rope_registrations(context):
    db, actor, meet, client = context
    for college in ['食品工程学院', '人文学院', '经济管理学院']:
        db.add(CollegeTeam(meet_id=meet.id, college=college, team_name=f'{college}代表队', created_by_id=actor.id))
    db.commit()
    report = synchronize_existing_rope_meets(db)
    db.commit()
    assert report == [{'meet_id': meet.id, 'created_teams': 0, 'created_registrations': 9, 'college_count': 8}]
    assert_eight_colleges(client, meet.id)
    assert synchronize_existing_rope_meets(db) == []


def test_initialize_synchronizes_all_configured_colleges_and_remains_idempotent(context):
    _, _, meet, client = context
    response = client.post('/api/v1/sports-teacher/rope/initialize', json={'meet_id': meet.id})
    assert response.status_code == 200, response.text
    assert response.json()['created_teams'] == 3
    assert response.json()['created_registrations'] == 9
    assert response.json()['college_count'] == 8
    assert_eight_colleges(client, meet.id)
    repeated = client.post('/api/v1/sports-teacher/rope/initialize', json={'meet_id': meet.id})
    assert repeated.status_code == 200 and repeated.json()['created_registrations'] == 0


def test_sync_keeps_other_meets_and_event_specific_teams_separate(context):
    db, actor, meet, client = context
    other = SportsMeet(name='其他运动会', edition='2026', start_date=date(2026, 10, 20), end_date=date(2026, 10, 21))
    db.add(other)
    db.flush()
    db.add(CollegeTeam(meet_id=other.id, college='信息工程学院', team_name='其他届次代表队', created_by_id=actor.id))
    event = db.scalar(select(Event).where(Event.meet_id == meet.id))
    db.add(CollegeTeam(meet_id=meet.id, event_id=event.id, college='信息工程学院', team_name='专项队', created_by_id=actor.id))
    db.commit()
    synchronize_rope_colleges(db, meet.id, actor)
    db.commit()
    assert_eight_colleges(client, meet.id)
    assert len(list(db.scalars(select(CollegeTeam).where(CollegeTeam.meet_id == other.id)))) == 1
    assert synchronize_rope_colleges(db, other.id, actor)['created_registrations'] == 0
