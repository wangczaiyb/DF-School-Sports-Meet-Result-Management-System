from datetime import datetime
from pathlib import Path
import sqlite3
import sys

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


settings = get_settings()
sqlite_db_path: Path | None = None
if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.removeprefix("sqlite:///")
    sqlite_db_path = Path(db_path)
    sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False, "timeout": 30}
else:
    connect_args = {"charset": "utf8mb4"}

engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)

if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ensure_sqlite_team_registration_schema() -> None:
    """Upgrade local registrations, tournament matches, and college team members schema."""
    if sqlite_db_path is None or not sqlite_db_path.exists():
        return
    with sqlite3.connect(sqlite_db_path, timeout=30) as check_connection:
        check_connection.execute("PRAGMA foreign_keys=OFF")

        # 1. 确保 tournament_matches 具备 sets_detail、forfeit_team_id 及单打/团体新字段
        tm_exists = check_connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tournament_matches'").fetchone()
        if tm_exists:
            tm_columns = {row[1]: row for row in check_connection.execute("PRAGMA table_info(tournament_matches)")}
            if "sets_detail" not in tm_columns:
                check_connection.execute("ALTER TABLE tournament_matches ADD COLUMN sets_detail JSON")
            if "forfeit_team_id" not in tm_columns:
                check_connection.execute("ALTER TABLE tournament_matches ADD COLUMN forfeit_team_id INTEGER REFERENCES college_teams(id)")
            if "home_student_id" not in tm_columns:
                check_connection.execute("ALTER TABLE tournament_matches ADD COLUMN home_student_id INTEGER REFERENCES student_roster(id)")
            if "away_student_id" not in tm_columns:
                check_connection.execute("ALTER TABLE tournament_matches ADD COLUMN away_student_id INTEGER REFERENCES student_roster(id)")
            if "winner_student_id" not in tm_columns:
                check_connection.execute("ALTER TABLE tournament_matches ADD COLUMN winner_student_id INTEGER REFERENCES student_roster(id)")
            if "loser_student_id" not in tm_columns:
                check_connection.execute("ALTER TABLE tournament_matches ADD COLUMN loser_student_id INTEGER REFERENCES student_roster(id)")
            if "best_of" not in tm_columns:
                check_connection.execute("ALTER TABLE tournament_matches ADD COLUMN best_of INTEGER DEFAULT 3")
            if "team_rubber_detail" not in tm_columns:
                check_connection.execute("ALTER TABLE tournament_matches ADD COLUMN team_rubber_detail JSON")

        # 1.5 确保 college_teams 具备 event_id 字段
        ct_exists = check_connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='college_teams'").fetchone()
        if ct_exists:
            ct_columns = {row[1]: row for row in check_connection.execute("PRAGMA table_info(college_teams)")}
            if "event_id" not in ct_columns:
                check_connection.execute("ALTER TABLE college_teams ADD COLUMN event_id INTEGER REFERENCES events(id)")
                check_connection.execute("CREATE INDEX IF NOT EXISTS ix_college_teams_event_id ON college_teams (event_id)")

        # 2. 确保 college_team_members 表存在
        check_connection.execute(
            """
            CREATE TABLE IF NOT EXISTS college_team_members (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL REFERENCES college_teams(id) ON DELETE CASCADE,
                student_id INTEGER NOT NULL REFERENCES student_roster(id) ON DELETE CASCADE,
                role_title VARCHAR(64),
                is_starter BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_college_team_member UNIQUE (team_id, student_id)
            )
            """
        )
        check_connection.execute("CREATE INDEX IF NOT EXISTS ix_college_team_members_team_id ON college_team_members (team_id)")
        check_connection.execute("CREATE INDEX IF NOT EXISTS ix_college_team_members_student_id ON college_team_members (student_id)")

        # 3. 检查 registrations 表
        table_exists = check_connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='registrations'"
        ).fetchone()
        if not table_exists:
            check_connection.commit()
            return
        columns = {row[1]: row for row in check_connection.execute("PRAGMA table_info(registrations)")}
        if "group_tag" not in columns:
            check_connection.execute("ALTER TABLE registrations ADD COLUMN group_tag VARCHAR(16)")
        check_connection.commit()
        if "college_team_id" in columns and "round_id" in columns and columns["student_id"][3] == 0:
            return

    backup_root = sqlite_db_path.parent / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / f"sports_meet_{datetime.now():%Y%m%d_%H%M%S}_before_round_registration.db"
    with sqlite3.connect(sqlite_db_path, timeout=30) as source, sqlite3.connect(backup_path) as destination:
        source.backup(destination)

    connection = sqlite3.connect(sqlite_db_path, timeout=30)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO event_rounds (event_id, name, stage, sequence, qualification_count)
            SELECT e.id,
                   CASE e.stage WHEN 'HEAT' THEN '初赛' WHEN 'SEMIFINAL' THEN '晋级赛' ELSE '决赛' END,
                   e.stage, 1, e.qualification_count
            FROM events e
            WHERE NOT EXISTS (SELECT 1 FROM event_rounds r WHERE r.event_id = e.id)
            """
        )
        connection.execute("DROP TABLE IF EXISTS registrations_v3")
        connection.execute(
            """
            CREATE TABLE registrations_v3 (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL REFERENCES events(id),
                round_id INTEGER NOT NULL REFERENCES event_rounds(id),
                student_id INTEGER REFERENCES student_roster(id),
                college_team_id INTEGER REFERENCES college_teams(id),
                bib_no VARCHAR(32),
                heat VARCHAR(32),
                lane VARCHAR(16),
                status VARCHAR(24) NOT NULL,
                CONSTRAINT uq_registration_round_student UNIQUE (event_id, round_id, student_id),
                CONSTRAINT uq_registration_round_college_team UNIQUE (event_id, round_id, college_team_id),
                CONSTRAINT ck_registration_exactly_one_participant CHECK (
                    (student_id IS NOT NULL AND college_team_id IS NULL)
                    OR (student_id IS NULL AND college_team_id IS NOT NULL)
                )
            )
            """
        )
        source_columns = {row[1] for row in connection.execute("PRAGMA table_info(registrations)")}
        college_expression = "college_team_id" if "college_team_id" in source_columns else "NULL"
        round_expression = "round_id" if "round_id" in source_columns else "(SELECT id FROM event_rounds r WHERE r.event_id = registrations.event_id ORDER BY r.sequence, r.id LIMIT 1)"
        connection.execute(
            f"""
            INSERT INTO registrations_v3
                (id, event_id, round_id, student_id, college_team_id, bib_no, heat, lane, status)
            SELECT id, event_id, {round_expression}, student_id, {college_expression}, bib_no, heat, lane, status
            FROM registrations
            """
        )
        connection.execute("DROP TABLE registrations")
        connection.execute("ALTER TABLE registrations_v3 RENAME TO registrations")
        connection.execute("CREATE INDEX ix_registrations_event_id ON registrations (event_id)")
        connection.execute("CREATE INDEX ix_registrations_round_id ON registrations (round_id)")
        connection.execute("CREATE INDEX ix_registrations_student_id ON registrations (student_id)")
        connection.execute("CREATE INDEX ix_registrations_college_team_id ON registrations (college_team_id)")
        connection.commit()
        connection.execute("PRAGMA foreign_keys=ON")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"SQLite 外键检查失败，已保留迁移前备份：{backup_path}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _resolve_alembic_ini() -> Path | None:
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidate = Path(sys._MEIPASS) / "backend" / "alembic.ini"
            if candidate.exists():
                return candidate
        exe_dir = Path(sys.executable).resolve().parent
        candidate = exe_dir / "_internal" / "backend" / "alembic.ini"
        if candidate.exists():
            return candidate
        candidate = exe_dir / "backend" / "alembic.ini"
        if candidate.exists():
            return candidate
    local_p = Path(__file__).resolve().parents[1] / "alembic.ini"
    if local_p.exists():
        return local_p
    return None


def upgrade_database_to_head() -> bool:
    """Apply the checked-in Alembic chain before the application starts."""
    try:
        config_path = _resolve_alembic_ini()
        if not config_path or not config_path.exists():
            return False
        from alembic import command
        from alembic.config import Config

        config = Config(str(config_path))
        config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
        command.upgrade(config, "head")
        return True
    except Exception as e:
        print(f"[*] 数据库结构检查/升级完成 (Alembic: {e})")
        return False


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
