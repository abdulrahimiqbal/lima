from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import secrets
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .background import CampaignWorker
from .config import Settings
from .schemas import (
    CampaignControl,
    CampaignCreate,
    CampaignUpdateNotes,
    CandidateRankFamilyRequest,
    CompositeScarcityTheoremWaveRequest,
    CompositeScarcityViabilityWaveRequest,
    CompositionalCertificateFamilyRequest,
    CoverageNormalizationHuntRequest,
    CylinderPressureWaveRequest,
    DynamicAdmissibilityCompassWaveRequest,
    DynamicPressureAutomatonWaveRequest,
    FinalCollatzExperimentRequest,
    FormalProbeBakeRequest,
    FormalProbeDigestRequest,
    GlobalForcingHuntWaveRequest,
    HybridCertificateFamilyRequest,
    InventionBatchCreate,
    PivotPortfolioWaveRequest,
    PressureHeightFrontierCertificateWaveRequest,
    PressureHeightFrontierCompletenessWaveRequest,
    PressureHeightGeneratorBridgeWaveRequest,
    PressureHeightParameterizedCompletenessWaveRequest,
    PressureHeightSccExactnessWaveRequest,
    PressureHeightSurvivorClosureWaveRequest,
    PressureGlobalizationWaveRequest,
    PromoteWorldRequest,
    RankCertificateHuntRequest,
    StructuredRankFamilyRequest,
    WorldEvolutionRunRequest,
)
from .service import CampaignService

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    service = CampaignService(settings)
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
    app.state.service = service
    app.state.worker = worker

    @app.middleware("http")
    async def ensure_csrf_cookie(request: Request, call_next):
        response = await call_next(request)
        if request.method in {"GET", "HEAD"} and not request.cookies.get("csrf_token"):
            response.set_cookie(
                key="csrf_token",
                value=secrets.token_urlsafe(32),
                httponly=False,
                samesite="lax",
                secure=settings.environment == "production",
            )
        return response

    def get_service(request: Request) -> CampaignService:
        return request.app.state.service

    def require_operator_auth(
        x_api_key: str | None = Header(default=None),
    ) -> None:
        if not settings.operator_api_key:
            return
        if x_api_key != settings.operator_api_key:
            raise HTTPException(status_code=401, detail="Unauthorized")

    def require_csrf(
        request: Request,
        x_csrf_token: str | None = Header(default=None),
    ) -> None:
        if settings.operator_api_key:
            return

        expected_origin = f"{request.url.scheme}://{request.url.netloc}"
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        if origin and origin.rstrip("/") != expected_origin:
            raise HTTPException(status_code=403, detail="Cross-site request blocked")
        if referer:
            parsed = urlparse(referer)
            referer_origin = f"{parsed.scheme}://{parsed.netloc}"
            if referer_origin != expected_origin:
                raise HTTPException(status_code=403, detail="Cross-site request blocked")

        # Enforce a token only for browser-originated requests.
        if origin or referer:
            csrf_cookie = request.cookies.get("csrf_token")
            if not csrf_cookie or not x_csrf_token or csrf_cookie != x_csrf_token:
                raise HTTPException(status_code=403, detail="Missing or invalid CSRF token")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        # Check canonical memory store
        try:
            service.ping_store()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Database not ready: {e}")

        # If strict live Aristotle is enabled, require a truthful live probe.
        if settings.strict_live_aristotle:
            if settings.executor_backend not in {"aristotle", "http"}:
                raise HTTPException(
                    status_code=503,
                    detail="STRICT_LIVE_ARISTOTLE requires executor_backend=aristotle",
                )
            connectivity = service.smoke_aristotle(strict_live_probe=True)
            if connectivity.get("status") != "connected":
                raise HTTPException(
                    status_code=503,
                    detail=f"Aristotle strict probe failed: {connectivity}",
                )

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
    def smoke_aristotle(
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        return service.smoke_aristotle()

    @app.post("/api/system/self-improvement/run")
    def run_self_improvement(
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        return service.run_self_improvement()

    @app.get("/api/campaigns")
    def list_campaigns(service: CampaignService = Depends(get_service)):
        return service.list_campaigns()

    @app.post("/api/campaigns")
    def create_campaign(
        payload: CampaignCreate,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
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

    @app.get("/api/campaigns/{campaign_id}/operator-brief")
    def get_operator_brief(
        campaign_id: str,
        service: CampaignService = Depends(get_service),
    ):
        try:
            return service.get_operator_brief(campaign_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/campaigns/{campaign_id}/invention/lab")
    def get_invention_lab(
        campaign_id: str,
        service: CampaignService = Depends(get_service),
    ):
        try:
            return service.get_invention_lab(campaign_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/invention/batches")
    def create_invention_batch(
        campaign_id: str,
        payload: InventionBatchCreate,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.create_invention_batch(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/invention/batches/{batch_id}/distill")
    def distill_invention_batch(
        campaign_id: str,
        batch_id: str,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.distill_invention_batch(campaign_id, batch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/invention/batches/{batch_id}/falsify")
    def falsify_invention_batch(
        campaign_id: str,
        batch_id: str,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.falsify_invention_batch(campaign_id, batch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/invention/worlds/promote")
    def promote_invention_world(
        campaign_id: str,
        payload: PromoteWorldRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.promote_invention_world(campaign_id, payload.distilled_world_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/run")
    def run_world_evolution(
        campaign_id: str,
        payload: WorldEvolutionRunRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_world_evolution(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/bake-probes")
    def bake_world_evolution_probes(
        campaign_id: str,
        payload: FormalProbeBakeRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.bake_formal_probes(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/digest-probe-results")
    def digest_world_evolution_probe_results(
        campaign_id: str,
        payload: FormalProbeDigestRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.digest_formal_probe_results(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/final-collatz-experiment")
    def run_final_collatz_experiment(
        campaign_id: str,
        payload: FinalCollatzExperimentRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_final_collatz_experiment(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/rank-certificate-hunt")
    def run_rank_certificate_hunt(
        campaign_id: str,
        payload: RankCertificateHuntRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_rank_certificate_hunt(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/candidate-rank-families")
    def run_candidate_rank_families(
        campaign_id: str,
        payload: CandidateRankFamilyRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_candidate_rank_families(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/structured-rank-families")
    def run_structured_rank_families(
        campaign_id: str,
        payload: StructuredRankFamilyRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_structured_rank_families(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/hybrid-certificate-families")
    def run_hybrid_certificate_families(
        campaign_id: str,
        payload: HybridCertificateFamilyRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_hybrid_certificate_families(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/compositional-certificate-families")
    def run_compositional_certificate_families(
        campaign_id: str,
        payload: CompositionalCertificateFamilyRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_compositional_certificate_families(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/coverage-normalization-hunt")
    def run_coverage_normalization_hunt(
        campaign_id: str,
        payload: CoverageNormalizationHuntRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_coverage_normalization_hunt(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/cylinder-pressure-wave")
    def run_cylinder_pressure_wave(
        campaign_id: str,
        payload: CylinderPressureWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_cylinder_pressure_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/pressure-globalization-wave")
    def run_pressure_globalization_wave(
        campaign_id: str,
        payload: PressureGlobalizationWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_pressure_globalization_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/pivot-portfolio-wave")
    def run_pivot_portfolio_wave(
        campaign_id: str,
        payload: PivotPortfolioWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_pivot_portfolio_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/composite-scarcity-viability-wave")
    def run_composite_scarcity_viability_wave(
        campaign_id: str,
        payload: CompositeScarcityViabilityWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_composite_scarcity_viability_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/composite-scarcity-theorem-wave")
    def run_composite_scarcity_theorem_wave(
        campaign_id: str,
        payload: CompositeScarcityTheoremWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_composite_scarcity_theorem_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/global-forcing-hunt-wave")
    def run_global_forcing_hunt_wave(
        campaign_id: str,
        payload: GlobalForcingHuntWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_global_forcing_hunt_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/dynamic-admissibility-compass-wave")
    def run_dynamic_admissibility_compass_wave(
        campaign_id: str,
        payload: DynamicAdmissibilityCompassWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_dynamic_admissibility_compass_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/dynamic-pressure-automaton-wave")
    def run_dynamic_pressure_automaton_wave(
        campaign_id: str,
        payload: DynamicPressureAutomatonWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_dynamic_pressure_automaton_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/pressure-height-survivor-closure-wave")
    def run_pressure_height_survivor_closure_wave(
        campaign_id: str,
        payload: PressureHeightSurvivorClosureWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_pressure_height_survivor_closure_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/pressure-height-frontier-certificate-wave")
    def run_pressure_height_frontier_certificate_wave(
        campaign_id: str,
        payload: PressureHeightFrontierCertificateWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_pressure_height_frontier_certificate_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/pressure-height-frontier-completeness-wave")
    def run_pressure_height_frontier_completeness_wave(
        campaign_id: str,
        payload: PressureHeightFrontierCompletenessWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_pressure_height_frontier_completeness_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/pressure-height-parameterized-completeness-wave")
    def run_pressure_height_parameterized_completeness_wave(
        campaign_id: str,
        payload: PressureHeightParameterizedCompletenessWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_pressure_height_parameterized_completeness_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/pressure-height-generator-bridge-wave")
    def run_pressure_height_generator_bridge_wave(
        campaign_id: str,
        payload: PressureHeightGeneratorBridgeWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_pressure_height_generator_bridge_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/world-evolution/pressure-height-scc-exactness-wave")
    def run_pressure_height_scc_exactness_wave(
        campaign_id: str,
        payload: PressureHeightSccExactnessWaveRequest,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.run_pressure_height_scc_exactness_wave(campaign_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/step")
    def step_campaign(
        campaign_id: str,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            return service.step_campaign(campaign_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/campaigns/{campaign_id}/notes")
    def update_notes(
        campaign_id: str,
        payload: CampaignUpdateNotes,
        service: CampaignService = Depends(get_service),
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
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
        _auth: None = Depends(require_operator_auth),
        _csrf: None = Depends(require_csrf),
    ):
        try:
            if payload.action == "pause":
                return service.pause_campaign(campaign_id)
            return service.resume_campaign(campaign_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


app = create_app()
