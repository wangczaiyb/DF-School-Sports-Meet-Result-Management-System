"""集中设置源码路径和独立测试数据，避免触碰正式数据库。"""
import os
import sys
import tempfile
import gc
from pathlib import Path

import pytest

TEST_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TEST_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)
runtime_root = TEST_ROOT / ".runtime"
runtime_root.mkdir(exist_ok=True)
_runtime = tempfile.TemporaryDirectory(prefix="backend-", dir=runtime_root)
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_runtime.name).as_posix()}/test.db"
os.environ["EXPORT_DIR"] = str(Path(_runtime.name) / "exports")
os.environ["AUTO_SEED"] = "true"


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    from backend.app.database import Base, SessionLocal, engine
    from backend.app.seed import seed_database

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)
    yield
    from sqlalchemy.orm import close_all_sessions
    close_all_sessions()
    gc.collect()
    engine.dispose()
    _runtime.cleanup()
