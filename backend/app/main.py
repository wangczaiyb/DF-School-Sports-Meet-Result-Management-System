from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .ai.router import router as ai_router
from .rope_io import router as rope_io_router
from .config import get_settings
from sqlalchemy import text

from .database import Base, SessionLocal, engine, ensure_sqlite_team_registration_schema, upgrade_database_to_head
from .seed import seed_database
from .services import sync_event_rounds
from .college_maintenance import synchronize_render_colleges
from .rope_college_sync import synchronize_existing_rope_meets


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    upgrade_database_to_head()
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_team_registration_schema()
    with SessionLocal() as db:
        if settings.auto_seed:
            seed_database(db)
        sync_event_rounds(db)
        db.commit()
        if os.environ.get('RENDER') == 'true' and os.environ.get('RENDER_EXTERNAL_HOSTNAME') == 'df-school-sports-meet.onrender.com':
            synchronize_render_colleges(db)
            db.commit()
        synchronize_existing_rope_meets(db)
        db.commit()
        if settings.database_url.startswith("sqlite"):
            db.execute(text("PRAGMA optimize"))
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.3.1",
    description="校园运动会赛事、赛程、成绩审核、计分和发布 API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.include_router(router, prefix=settings.api_prefix)
app.include_router(ai_router, prefix=settings.api_prefix)
app.include_router(rope_io_router, prefix=settings.api_prefix)


import os
import sys
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


@app.get("/health")
def health():
    return {
        "status": "ok",
        "api_version": "1.3.1",
        "deploy_commit": os.environ.get('RENDER_GIT_COMMIT'),
        "features": [
            "manual-student-roster",
            "college-team-roster",
            "per-event-registration",
            "student-password-optional",
            "basketball-workbench",
            "volleyball-workbench",
            "table-tennis-workbench",
            "rope-skipping-workbench",
            "rope-registration-tables",
            "configured-college-team-scope",
            "college-roster-render-sync",
            "rope-college-registration-sync",
            "immutable-published-results",
            "ai-copilot-platform",
        ],
    }


def _resolve_dist_dir():
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            embedded_dist = os.path.join(sys._MEIPASS, "frontend_dist")
            if os.path.exists(embedded_dist):
                return embedded_dist
        internal_dist = os.path.join(os.path.dirname(sys.executable), "_internal", "frontend_dist")
        if os.path.exists(internal_dist):
            return internal_dist
        exe_dist = os.path.join(os.path.dirname(sys.executable), "frontend_dist")
        if os.path.exists(exe_dist):
            return exe_dist
    local_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
    if os.path.exists(local_dist):
        return local_dist
    return None


_dist_dir = _resolve_dist_dir()
if _dist_dir and os.path.exists(_dist_dir):
    _assets_dir = os.path.join(_dist_dir, "assets")
    if os.path.exists(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path in ["docs", "redoc", "openapi.json", "health"]:
            return None
        candidate = os.path.join(_dist_dir, full_path)
        if full_path and os.path.isfile(candidate):
            if os.path.basename(candidate).lower() == "index.html":
                return FileResponse(candidate, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})
            return FileResponse(candidate)
        # 入口页不允许浏览器沿用旧缓存，确保每次启动都加载本次打包的最新哈希资源。
        return FileResponse(
            os.path.join(_dist_dir, "index.html"),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )
