import os
import shutil
import sqlite3
import tempfile
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from alembic.config import Config
from alembic import command
ALEMBIC_INI = PROJECT_ROOT / "backend" / "alembic.ini"

import gc

def safe_unlink(path: Path):
    gc.collect()
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass

def run_alembic_upgrade(db_path: Path):
    cfg = Config(str(ALEMBIC_INI))
    url = f"sqlite:///{db_path.as_posix()}"
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

def check_db(db_path: Path, expected_version="20260901_0009"):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    version = cur.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    integrity = cur.execute("PRAGMA integrity_check").fetchall()
    fk_check = cur.execute("PRAGMA foreign_key_check").fetchall()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    res_cols = [c[1] for c in cur.execute("PRAGMA table_info(results)").fetchall()] if "results" in tables else []
    conn.close()
    
    assert version == expected_version, f"Version mismatch: {version} != {expected_version}"
    assert integrity == [("ok",)], f"Integrity check failed: {integrity}"
    assert fk_check == [], f"Foreign key check failed: {fk_check}"
    return {
        "version": version,
        "integrity": integrity[0][0],
        "fk_violations": len(fk_check),
        "tables_count": len(tables),
        "has_publisher_id": "publisher_id" in res_cols,
        "has_snapshot_status": "published_competition_status" in res_cols,
    }

def test_scenario_a():
    print("\n--- Testing Scenario A: Fresh Database ---")
    tmp = PROJECT_ROOT / "data" / "CODEX_TEST_fresh.db"
    safe_unlink(tmp)
    try:
        run_alembic_upgrade(tmp)
        report = check_db(tmp)
        print("Scenario A PASS:", report)
    finally:
        safe_unlink(tmp)

def test_scenario_b():
    print("\n--- Testing Scenario B: Legacy Database (0001 -> Head) ---")
    backup_file = PROJECT_ROOT / "data" / "backups" / "sports_meet_20260901_102055_codex-crud-test.db"
    assert backup_file.exists(), f"Backup file {backup_file} not found"
    tmp = PROJECT_ROOT / "data" / "CODEX_TEST_legacy_0001.db"
    safe_unlink(tmp)
    try:
        shutil.copyfile(backup_file, tmp)
        # Verify it starts at 20260824_0001
        conn = sqlite3.connect(str(tmp))
        v_before = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        conn.close()
        print(f"Legacy DB starting at version: {v_before}")
        assert v_before == "20260824_0001"
        
        run_alembic_upgrade(tmp)
        report = check_db(tmp)
        print("Scenario B PASS:", report)
    finally:
        safe_unlink(tmp)

def test_scenario_c():
    print("\n--- Testing Scenario C: Schema Ahead, Revision Behind ---")
    # Take a fresh DB, run Base.metadata.create_all(), then stamp as 0001 or 0007, then upgrade head
    tmp = PROJECT_ROOT / "data" / "CODEX_TEST_schema_ahead.db"
    safe_unlink(tmp)
    try:
        from sqlalchemy import create_engine
        from backend.app.database import Base
        from backend.app import models
        
        engine = create_engine(f"sqlite:///{tmp.as_posix()}")
        Base.metadata.create_all(bind=engine)
        engine.dispose()
        
        # Stamp alembic_version table as 20260830_0007
        conn = sqlite3.connect(str(tmp))
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))")
        conn.execute("INSERT INTO alembic_version (version_num) VALUES ('20260830_0007')")
        conn.commit()
        conn.close()
        
        # Now run alembic upgrade head
        run_alembic_upgrade(tmp)
        report = check_db(tmp)
        print("Scenario C PASS:", report)
    finally:
        safe_unlink(tmp)

if __name__ == "__main__":
    test_scenario_a()
    test_scenario_b()
    test_scenario_c()
    print("\nALL 3 ALEMBIC SCENARIOS PASSED SUCCESSFULLY!")
