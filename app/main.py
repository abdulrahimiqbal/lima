from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .background import CampaignWorker
from .config import Settings
from .db import Database
from .schemas import CampaignControl, CampaignCreate, CampaignUpdateNotes
from .service import CampaignService

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    db = Database(settings.database_path)
    db.init()
    service = CampaignService(db, settings)
    worker = CampaignWorker(service, poll_seconds=settings.worker_poll_seconds)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker.start()
        try:
            yield
        finally:
            worker.stop()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db
    app.state.service = service
    app.state.worker = worker

    def get_service(request: Request) -> CampaignService:
        return request.app.state.service

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        # Check database
        try:
            with db.connect() as conn:
                conn.execute("SELECT 1").fetchone()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database not ready: {e}")
        
        # If strict live Aristotle is enabled, check connectivity
        if settings.strict_live_aristotle:
            status = service.system_status()
            if status.get("executor", {}).get("connectivity", {}).get("status") != "connected":
                raise HTTPException(status_code=503, detail="Aristotle not connected in strict mode")

        return {"status": "ready"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "title": settings.app_name,
                "manager_backend": settings.manager_backend_resolved,
                "executor_backend": settings.executor_backend,
            },
        )

    @app.get("/api/system/interfaces")
    def get_interfaces(service: CampaignService = Depends(get_service)):
        return service.interfaces()

    @app.get("/api/system/status")
    def get_system_status(service: CampaignService = Depends(get_service)):
        return service.system_status()

    @app.post("/api/system/smoke/aristotle")
    def smoke_aristotle(service: CampaignService = Depends(get_service)):
        return service.smoke_aristotle()

    @app.get("/api/campaigns")
    def list_campaigns(service: CampaignService = Depends(get_service)):
        return service.list_campaigns()

    @app.post("/api/campaigns")
    def create_campaign(
        payload: CampaignCreate,
        service: CampaignService = Depends(get_service),
    ):
        return service.create_campaign(payload)

    @app.get("/api/campaigns/{campaign_id}")
    def get_campaign(campaign_id: str, service: CampaignService = Depends(get_service)):
        try:
            return service.get_campaign(campaign_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/campaigns/{campaign_id}/events")
    def get_events(
        campaign_id: str,
        limit: int = Query(default=50, ge=1, le=200),
        service: CampaignService = Depends(get_service),
    ):
        try:
            return service.list_events(campaign_id, limit=limit)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/campaigns/{campaign_id}/manager-context")
    def get_manager_context(
        campaign_id: str,
        service: CampaignService = Depends(get_service),
    ):
        try:
            return service.build_manager_context(campaign_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/campaigns/{campaign_id}/memory-summary")
    def get_memory_summary(
        campaign_id: str,
        service: CampaignService = Depends(get_service),
    ):
        try:
            return service.get_memory_summary(campaign_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/campaigns/{campaign_id}/memory-packet")
    def get_memory_packet(
        campaign_id: str,
        service: CampaignService = Depends(get_service),
    ):
        try:
            return service.get_memory_packet(campaign_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/step")
    def step_campaign(campaign_id: str, service: CampaignService = Depends(get_service)):
        try:
            return service.step_campaign(campaign_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/notes")
    def update_notes(
        campaign_id: str,
        payload: CampaignUpdateNotes,
        service: CampaignService = Depends(get_service),
    ):
        try:
            return service.update_notes(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/control")
    def control_campaign(
        campaign_id: str,
        payload: CampaignControl,
        service: CampaignService = Depends(get_service),
    ):
        try:
            if payload.action == "pause":
                return service.pause_campaign(campaign_id)
            return service.resume_campaign(campaign_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


app = create_app()
