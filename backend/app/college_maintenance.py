"""七学院参赛范围的数据维护，调用方负责事务。"""
from datetime import datetime, timezone
import json
import sqlite3
from .college_policy import DEFAULT_COLLEGES


def placeholders(values):
    return ','.join('?' for _ in values) or 'NULL'


def synchronize_render_colleges(session):
    """仅目标Render服务调用；配置和关联数据与本地七学院范围一致。"""
    driver = session.connection().connection.driver_connection
    if not isinstance(driver, sqlite3.Connection):
        raise RuntimeError('七学院数据维护要求SQLite数据库')
    old_factory = driver.row_factory
    driver.row_factory = sqlite3.Row
    try:
        driver.execute('BEGIN IMMEDIATE')
        configured = driver.execute("SELECT value FROM system_settings WHERE key='participating_colleges'").fetchone()
        missing = any(not driver.execute('SELECT id FROM college_teams WHERE meet_id=? AND college=? AND event_id IS NULL', (meet[0], college)).fetchone()
                      for meet in driver.execute('SELECT id FROM sports_meets').fetchall() for college in DEFAULT_COLLEGES)
        if configured and json.loads(configured[0]) == list(DEFAULT_COLLEGES) and not targets(driver) and not missing:
            return
        if driver.execute('SELECT count(*) FROM users').fetchone()[0] == 0:
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=' ')
            driver.execute('INSERT INTO system_settings(key,value,updated_at) VALUES (?,?,?) '
                           'ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',
                           ('participating_colleges', json.dumps(list(DEFAULT_COLLEGES), ensure_ascii=False), now))
        else:
            retain_colleges(driver, backed_up=False)
    finally:
        driver.row_factory = old_factory


def targets(db):
    return [dict(row) for row in db.execute(
        f'SELECT * FROM college_teams WHERE trim(college) NOT IN ({placeholders(DEFAULT_COLLEGES)}) ORDER BY id', DEFAULT_COLLEGES)]


def retain_colleges(db, backed_up=True):
    removed = targets(db)
    ids = [row['id'] for row in removed]
    clauses = placeholders(ids)
    registrations = [row[0] for row in db.execute(f'SELECT id FROM registrations WHERE college_team_id IN ({clauses})', ids)]
    registration_clauses = placeholders(registrations)
    results = [row[0] for row in db.execute(f'SELECT id FROM results WHERE registration_id IN ({registration_clauses})', registrations)]
    result_clauses = placeholders(results)
    match_condition = ' OR '.join(f'{column} IN ({clauses})' for column in (
        'home_team_id', 'away_team_id', 'winner_team_id', 'loser_team_id', 'forfeit_team_id'))
    report = {'removed_teams': [{'id': row['id'], 'college': row['college'], 'team_name': row['team_name']} for row in removed],
              'registrations': len(registrations), 'results': len(results),
              'matches': db.execute(f'SELECT count(*) FROM tournament_matches WHERE {match_condition}', ids * 5).fetchone()[0]}
    students_before = db.execute('SELECT count(*) FROM student_roster').fetchone()[0]
    users_before = db.execute('SELECT count(*) FROM users').fetchone()[0]
    retained_query = f'SELECT * FROM results WHERE id NOT IN ({result_clauses}) ORDER BY id' if results else 'SELECT * FROM results ORDER BY id'
    retained_results = [tuple(row) for row in db.execute(retained_query, results)]
    for table in ('rope_result_details', 'result_reviews'):
        db.execute(f'DELETE FROM {table} WHERE result_id IN ({result_clauses})', results)
    db.execute(f'DELETE FROM results WHERE id IN ({result_clauses})', results)
    db.execute(f'DELETE FROM qualification_records WHERE registration_id IN ({registration_clauses})', registrations)
    db.execute(f'DELETE FROM registrations WHERE id IN ({registration_clauses})', registrations)
    db.execute(f'DELETE FROM rope_lineup_members WHERE college_team_id IN ({clauses})', ids)
    db.execute(f'DELETE FROM college_team_members WHERE team_id IN ({clauses})', ids)
    db.execute(f'DELETE FROM tournament_matches WHERE {match_condition}', ids * 5)
    db.execute(f'DELETE FROM college_teams WHERE id IN ({clauses})', ids)
    operator = db.execute("SELECT id FROM users WHERE role IN ('SPORTS_TEACHER','DEVELOPER') ORDER BY CASE WHEN role='SPORTS_TEACHER' THEN 0 ELSE 1 END,id LIMIT 1").fetchone()
    if not operator:
        raise RuntimeError('未找到维护队伍所需的管理账号')
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=' ')
    value = json.dumps(list(DEFAULT_COLLEGES), ensure_ascii=False)
    db.execute('INSERT INTO system_settings(key,value,updated_by_id,updated_at) VALUES (?,?,?,?) '
               'ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_by_id=excluded.updated_by_id,updated_at=excluded.updated_at',
               ('participating_colleges', value, operator[0], now))
    created = 0
    for meet in db.execute('SELECT id FROM sports_meets ORDER BY id').fetchall():
        for college in DEFAULT_COLLEGES:
            if not db.execute('SELECT id FROM college_teams WHERE meet_id=? AND college=? AND event_id IS NULL', (meet[0], college)).fetchone():
                db.execute('INSERT INTO college_teams(meet_id,event_id,college,team_name,created_by_id,created_at) VALUES (?,NULL,?,?,?,?)',
                           (meet[0], college, f'{college}代表队', operator[0], now))
                created += 1
    report['created_missing_teams'] = created
    if targets(db) or db.execute('PRAGMA foreign_key_check').fetchall() or db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise RuntimeError('清理后数据库完整性校验失败')
    if students_before != db.execute('SELECT count(*) FROM student_roster').fetchone()[0] or users_before != db.execute('SELECT count(*) FROM users').fetchone()[0]:
        raise RuntimeError('学生或账号数据意外变化')
    if retained_results != [tuple(row) for row in db.execute('SELECT * FROM results ORDER BY id')]:
        raise RuntimeError('保留的成绩记录发生意外变化')
    report['retained_colleges'] = [row[0] for row in db.execute('SELECT DISTINCT college FROM college_teams ORDER BY college')]
    db.execute('INSERT INTO audit_logs(actor_id,actor_username,action,target_type,target_id,before_data,after_data,reason,created_at) '
               'VALUES (NULL,?,?,?,?,?,?,?,?)', ('codex', 'RETAIN_SEVEN_COLLEGES', 'college_team', 'all',
                                                json.dumps({'removed': removed}, ensure_ascii=False), json.dumps(report, ensure_ascii=False),
                                                '用户明确要求只保留指定七个学院，删除名单外队伍及其关联参赛数据；'
                                                + ('执行前已完整备份' if backed_up else '按用户明确要求不创建备份'), now))
    return report
