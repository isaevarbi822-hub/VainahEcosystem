"""Vainah Ecosystem: single sign-in and eleven modular applications."""
from pathlib import Path
import os
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text as sql_text
from sqlalchemy.exc import SQLAlchemyError
from . import models  # noqa: F401; register SQLAlchemy models before create_all
from .auth import router as auth_router
from .database import create_session_factory
from .notes import router as notes_router
from .suite import router as suite_router
from .integrations import router as integrations_router
from .messenger import router as messenger_v2_router
from .groups import router as messenger_groups_router
from .security import ensure_safe_environment
from .realtime import router as realtime_router, LiveHub
from .verification import router as verification_router
from .community import router as community_router
from .handles import router as people_router

APP_NAMES = {"ai":"AI", "messenger":"Messenger", "browser":"Browser", "music":"Music",
             "weather":"Weather", "maps":"Maps", "notes":"Notes", "translate":"Translate",
             "study":"Study", "photos":"Photos", "calendar":"Calendar"}
ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "apps" / "web"


def create_app(database_url: str | None = None) -> FastAPI:
    ensure_safe_environment()
    app = FastAPI(title="Vainah Ecosystem API", version="0.8.1", docs_url="/api/docs")
    engine, factory = create_session_factory(database_url)
    app.state.engine = engine
    app.state.session_factory = factory
    app.state.live_hub = LiveHub()
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        # WebSocket signalling is limited to the same host, not arbitrary third parties.
        configured_origin = os.getenv("APP_ORIGIN", "").strip()
        if configured_origin.startswith("https://"):
            live_origin = "wss://" + urlsplit(configured_origin).netloc
        else:
            ws_scheme = "wss" if request.url.scheme == "https" else "ws"
            live_origin = f"{ws_scheme}://{request.url.netloc}"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://accounts.google.com/gsi/client; style-src 'self' https://accounts.google.com/gsi/style; "
            "img-src 'self' data: https://*.googleusercontent.com; connect-src 'self' https://accounts.google.com/gsi/ " + live_origin + "; object-src 'none'; "
            "base-uri 'self'; frame-src https://www.openstreetmap.org https://accounts.google.com/gsi/; frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(auth_router)
    app.include_router(notes_router)
    app.include_router(suite_router)
    app.include_router(messenger_v2_router)
    app.include_router(messenger_groups_router)
    app.include_router(realtime_router)
    app.include_router(verification_router)
    app.include_router(community_router)
    app.include_router(people_router)
    app.include_router(integrations_router)

    @app.get("/api/health")
    def health():
        try:
            with app.state.engine.connect() as conn:
                conn.execute(sql_text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse({"status": "degraded", "database": "unavailable", "version": "0.8.1"}, status_code=503)
        return {"status": "ok", "database": "connected", "product": "Vainah Ecosystem", "version": "0.8.1"}

    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def web_manifest():
        return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json")

    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        return FileResponse(WEB / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @app.get("/manifests/{app_name}.webmanifest", include_in_schema=False)
    def app_manifest(app_name: str):
        if app_name not in APP_NAMES:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Unknown app")
        return JSONResponse({
            "name": f"Vainah {APP_NAMES[app_name]}", "short_name": APP_NAMES[app_name],
            "id": f"/app/{app_name}", "start_url": f"/app/{app_name}",
            "scope": "/", "display": "standalone", "background_color": "#0b101b",
            "theme_color": "#0b101b", "icons": [
                {"src": f"/assets/app-icons/{app_name}-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": f"/assets/app-icons/{app_name}-512.png", "sizes": "512x512", "type": "image/png"},
            ]}, media_type="application/manifest+json")

    @app.get("/app/{app_name}", include_in_schema=False)
    def app_entry(app_name: str):
        if app_name not in APP_NAMES:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Unknown app")
        content = (WEB / ("messenger-home.html" if app_name == "messenger" else "index.html")).read_text(encoding="utf-8")
        content = content.replace('href="/manifest.webmanifest"',
                                  f'href="/manifests/{app_name}.webmanifest"')
        content = content.replace('<title>Vainah — твоя цифровая экосистема</title>',
                                  f'<title>Vainah {APP_NAMES[app_name]}</title>')
        return HTMLResponse(content)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(WEB / "messenger-home.html")

    return app


app = create_app()
