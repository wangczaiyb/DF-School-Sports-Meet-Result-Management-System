"""8位学号的所有写入入口、前导零和演示数据转换。"""
from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook
from pydantic import ValidationError
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.api import router
from backend.app.college_policy import DEFAULT_COLLEGES
from backend.app.database import Base, get_db
from backend.app.dependencies import business_admin, developer_only
from backend.app.models import CollegeTeam, Role, StudentRoster, User
from backend.app.schemas import StudentRegisterRequest, StudentRosterCreate
from backend.app.security import hash_password, verify_password
from backend.app.student_maintenance import apply_demo_student_number_plan, demo_student_number_plan


INVALID_NUMBERS = ['1234567', '123456789', '2026001001', 'ABCDEFGH', '1234_678', '１２３４５６７８', '1234567\n']
STUDENT = dict(name='学号测试学生', gender='男', college='信息工程学院', major='测试专业', class_name='测试班')


@pytest.fixture
def context():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        actor = User(username='developer', display_name='开发人员', role=Role.DEVELOPER,
                     password_hash='unused', status='ACTIVE')
        db.add(actor)
        db.commit()
        app = FastAPI()
        app.include_router(router, prefix='/api/v1')
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[business_admin] = lambda: actor
        app.dependency_overrides[developer_only] = lambda: actor
        with TestClient(app) as client:
            yield client, db
    engine.dispose()


@pytest.mark.parametrize('number', INVALID_NUMBERS)
def test_schemas_reject_invalid_student_numbers(number):
    for schema, values in [(StudentRosterCreate, STUDENT), (StudentRegisterRequest, {'name': STUDENT['name']})]:
        with pytest.raises(ValidationError, match='学号必须为8位数字'):
            schema(student_no=number, **values)


def test_leading_zero_student_number_can_be_created_and_updated(context):
    client, db = context
    response = client.post('/api/v1/sports-teacher/students', json={'student_no': '00123456', **STUDENT})
    assert response.status_code == 200, response.text
    student_id = response.json()['id']
    assert response.json()['student_no'] == '00123456'
    invalid = client.put(f'/api/v1/sports-teacher/students/{student_id}', json={'student_no': '123456789', **STUDENT})
    assert invalid.status_code == 422
    assert db.get(StudentRoster, student_id).student_no == '00123456'
    valid = client.put(f'/api/v1/sports-teacher/students/{student_id}', json={'student_no': '00123457', **STUDENT})
    assert valid.status_code == 200 and valid.json()['student_no'] == '00123457'


@pytest.mark.parametrize('number', INVALID_NUMBERS)
def test_student_accounts_cannot_bypass_number_validation(context, number):
    client, db = context
    response = client.post('/api/v1/developer/accounts', json={
        'username': number, 'display_name': '测试学生', 'role': 'STUDENT', 'password': 'Ignored123!',
    })
    assert response.status_code == 422
    db.add(User(username='00123456', display_name='学生', role=Role.STUDENT, password_hash='unused', status='ACTIVE'))
    db.commit()
    user = db.scalar(select(User).where(User.role == Role.STUDENT))
    response = client.put(f'/api/v1/developer/accounts/{user.id}', json={'username': number})
    assert response.status_code == 422
    assert user.username == '00123456'


@pytest.mark.parametrize('endpoint', ['developer', 'sports-teacher'])
@pytest.mark.parametrize('number', INVALID_NUMBERS)
def test_invalid_import_cancels_entire_batch(context, endpoint, number):
    client, db = context
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['学号', '姓名', '性别', '学院', '专业', '班级'])
    for no in ['00123456', number]:
        sheet.append([no, '导入学生', '男', '信息工程学院', '专业', '班级'])
    stream = BytesIO()
    workbook.save(stream)
    response = client.post(f'/api/v1/{endpoint}/students/import', files={'file': ('students.xlsx', stream.getvalue())})
    assert response.status_code == 422, response.text
    assert '8位数字' in response.text
    assert db.scalar(select(StudentRoster.id)) is None
    assert db.scalar(select(User.id).where(User.role == Role.STUDENT)) is None


def test_demo_renumbering_handles_collisions_and_preserves_custom_passwords(context):
    _, db = context
    default = User(username='2026001001', display_name='学生甲', role=Role.STUDENT,
                   password_hash=hash_password('DF2026001001'), status='ACTIVE')
    custom = User(username='202601001', display_name='学生乙', role=Role.STUDENT,
                  password_hash=hash_password('Changed123!'), status='ACTIVE')
    db.add_all([default, custom])
    db.flush()
    for user in [default, custom]:
        db.add(StudentRoster(student_no=user.username, user_id=user.id, activated=True, **STUDENT))
    db.commit()
    before = {row.id: row.user_id for row in db.scalars(select(StudentRoster))}
    custom_hash = custom.password_hash
    plan = demo_student_number_plan(db)
    assert len(plan) == 2 and len({item['student_no'] for item in plan}) == 2
    assert all(item['student_no'].startswith('26') for item in plan)
    report = apply_demo_student_number_plan(db, plan)
    assert report == {'students_updated': 2, 'accounts_updated': 2, 'default_passwords_updated': 1}
    assert verify_password(f'DF{default.username}', default.password_hash)
    assert custom.password_hash == custom_hash
    assert {row.id: row.user_id for row in db.scalars(select(StudentRoster))} == before
    assert all(row.student_no == db.get(User, row.user_id).username for row in db.scalars(select(StudentRoster)))
    assert demo_student_number_plan(db) == []


def test_valid_grade_prefix_is_preserved_without_explicit_demo_grade(context):
    _, db = context
    for no in ['20000001', '24000001', '26000001']:
        db.add(StudentRoster(student_no=no, **STUDENT))
    db.commit()
    assert demo_student_number_plan(db) == []


def test_explicit_demo_grade_repairs_previous_year_prefix_and_is_idempotent(context):
    _, db = context
    user = User(username='20261001', display_name=STUDENT['name'], role=Role.STUDENT,
                password_hash=hash_password('DF20261001'), status='ACTIVE')
    db.add(user)
    db.flush()
    row = StudentRoster(student_no=user.username, user_id=user.id, activated=True, **STUDENT)
    db.add(row)
    db.commit()
    plan = demo_student_number_plan(db, grade='26')
    assert plan[0]['student_no'] == '26001001'
    report = apply_demo_student_number_plan(db, plan, grade='26')
    assert report['students_updated'] == report['accounts_updated'] == 1
    assert row.student_no == user.username == '26001001'
    assert verify_password('DF26001001', user.password_hash)
    assert demo_student_number_plan(db, grade='26') == []


@pytest.mark.parametrize('grade', ['2', '2024', 'AB', '２４'])
def test_demo_grade_requires_two_ascii_digits(context, grade):
    _, db = context
    with pytest.raises(ValueError, match='两位数字'):
        demo_student_number_plan(db, grade=grade)


def test_editing_student_number_keeps_roster_account_and_default_password_in_sync(context):
    client, db = context
    user = User(username='00123456', display_name=STUDENT['name'], role=Role.STUDENT,
                password_hash=hash_password('DF00123456'), status='ACTIVE')
    db.add(user)
    db.flush()
    row = StudentRoster(student_no=user.username, user_id=user.id, activated=True, **STUDENT)
    db.add(row)
    db.commit()
    response = client.put(f'/api/v1/developer/accounts/{user.id}', json={'username': '00123457'})
    assert response.status_code == 200, response.text
    db.refresh(row)
    assert row.student_no == user.username == '00123457'
    assert verify_password('DF00123457', user.password_hash)
    response = client.put(f'/api/v1/sports-teacher/students/{row.id}', json={'student_no': '00123458', **STUDENT})
    assert response.status_code == 200, response.text
    assert row.student_no == user.username == '00123458'
    assert verify_password('DF00123458', user.password_hash)


def test_team_generation_uses_eight_colleges_when_no_setting_exists(context):
    client, db = context
    db.add(StudentRoster(student_no='00123456', **{**STUDENT, 'college': '旧学院'}))
    db.commit()
    meet = client.post('/api/v1/sports-teacher/meets', json={
        'name': '八学院验证运动会', 'edition': '2026', 'start_date': '2026-10-20', 'end_date': '2026-10-21',
    })
    assert meet.status_code == 200, meet.text
    meet_id = meet.json()['id']
    response = client.post('/api/v1/sports-teacher/college-teams/generate', json={'meet_id': meet_id})
    assert response.status_code == 200 and response.json()['created'] == 8
    assert set(db.scalars(select(CollegeTeam.college).where(CollegeTeam.meet_id == meet_id))) == set(DEFAULT_COLLEGES)
    assert client.post('/api/v1/sports-teacher/college-teams/generate', json={'meet_id': meet_id}).json()['created'] == 0
