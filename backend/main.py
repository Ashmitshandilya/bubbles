import contextvars
import hashlib
import json
import os
import re
import threading
import time

import env_compat  # noqa: F401  (loads .env and maps legacy COCO_* names to BUBBLES_*; must run before config is read)
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, Header, Query
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from wellness_common import REQUEST_TZ, parse_tz_header
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from auth_errors import (
    unauthorized_response,
    forbidden_response,
    auth_error_response,
    invalid_auth_header_response,
    missing_auth_header_response,
    invalid_token_response,
    invalid_scope_response,
)
from auth_assurance import requires_second_step, token_aal, token_exp
from ttl_cache import TTLCache
from admin_api import build_admin_router
import admin_settings
import ops_telemetry
from request_guard import BodyLimitMiddleware, admin_ids, install_access_log_redaction, require_admin
from memory_retrieval import get_relevant_memories, format_memory_context
from supabase_client import supabase
from bubbles_ai import BubblesAIResponse, ask_bubbles, is_degraded
from memory_promotion import promote_health_event
from rag import hybrid_search, build_evidence_context
from evidence_package import build_package, package_audit, plan_task
from health_event_pipeline import prepare_db_row
from health_logs import build_router as build_health_logs_router
from fitness_api import build_router as build_fitness_router
from data_rights import build_router as build_data_rights_router
from wellness_api import build_router as build_wellness_router
from chat_feedback import build_router as build_chat_feedback_router
from consent_api import build_router as build_consent_router
from onboarding_api import build_router as build_onboarding_router
import chat_cache
from chat_concurrency import settled, submit, submit_io
import chat_concurrency
from consent import consent_needed_reply, has_ai_consent
from import_api import build_router as build_import_router
from cycle_api import build_router as build_cycle_router
from partner_sharing import build_router as build_partner_router
from organ_map_api import build_router as build_organ_map_router
import association_loader
from context_engine import build_user_context, format_user_context
from safety_engine import assess_safety, safety_instruction, urgent_fallback_response
from chat_pipeline import (
    overlay_event_status,
    RateLimiter, ai_failed_reply, analyze_turn, build_rule_events, conversation_block, deterministic_reply,
    evidence_query, find_stored_reply, first_name, load_history, persist_events, reconcile_ai_events, reply_kind,
    safety_payload, semantic_trace, shown_evidence, state_block, stored_metadata,
)
from conversation_correction import apply_correction, contradiction_note
from health_semantics import display_name
from event_filters import DEAD_STATUSES, event_moment
from health_event_confirm import build_router as build_confirm_router
from client_telemetry import build_router as build_client_telemetry_router
from db_access import database_permission_response, is_permission_denied, probe_database, register_db_error_handlers
from weekly_insights import build_weekly_insights, to_response_shape as weekly_insights_response_shape
from pattern_engine import analyze as analyze_patterns
from health_state_engine import build_health_state
from learning_engine import build_learning_snapshot
from companion_engine import build_daily_companion
from memory_knowledge_graph import build_knowledge_graph, memory_candidates
from indian_food_intelligence import lookup_food, search_foods
from advanced_cycle_intelligence import analyze_advanced as analyze_cycle_advanced
from fitness_intelligence import analyze_fitness
from sleep_recovery_intelligence import analyze as analyze_sleep_recovery
from longitudinal_health_analysis import analyze as analyze_longitudinal
from medical_records_intelligence import summarize as summarize_medical_records, extract_questions as medical_questions
from doctor_timeline import build_timeline, prepare_visit
from advanced_escalation import evaluate as evaluate_escalation
from ai_orchestrator import route as route_ai, build_budget, sanitize_for_model
from privacy_security import redact, consent_policy, minimize_payload, security_headers, threat_check
from organ_intelligence import build_body_system_intelligence
from evidence_intelligence import build_grounding_packet, rank_evidence, register_source
from intervention_engine import select_interventions
from interoperability import export_bundle
from evaluation_governance import evaluate_case, release_gate, model_audit
from multimodal_intelligence import inspect_media_metadata, voice_session_policy
from digital_twin import build_digital_twin
from health_agent import plan_agent_actions
from memory_manager import extract_explicit_personal_facts, persist_explicit_facts, memory_diagnostics
from response_formatter import normalize_response, response_style_instruction
from response_quality import lint, scrub_doses, strip_attribution
from metric_names import plain_metric
from personalization_engine import build_personalization
from habit_intelligence import analyze_habits
from mental_wellness_intelligence import assess_wellbeing
from social_wellbeing import analyze_social_context
from living_signal_engine import build_living_signal_map
from state_normalizer import normalize_health_state, normalize_living_signal_map
from womens_health_intelligence import classify_womens_health
from medication_intelligence import medication_overview
from preventive_health import preventive_snapshot
from sharing_architecture import build_share_plan
from provider_integration import to_fhir_resource
from advanced_agent import plan_agent
from knowledge_learning import knowledge_health
from production_hardening import readiness_report
from model_governance import model_contract
from ai_telemetry import snapshot as ai_telemetry_snapshot
from schemas import (
    # Base
    SuccessResponse,
    # Health Events
    ExtractedEvent,
    ExtractEventsResponse,
    ExtractedEventsListResponse,
    # Weekly Insights
    WeeklyInsightsData,
    WeeklyInsightsResponse,
    # Nutrition
    NutritionSummaryData,
    NutritionIntelligenceResponse,
    # Cycle
    CycleData,
    CycleIntelligenceData,
    CycleIntelligenceResponse,
    # Intelligence Overview
    IntelligenceOverviewResponse,
    # Health State
    HealthStateData,
    HealthStateResponse,
    # Living Signal Map
    LivingSignalMapData,
    LivingSignalMapResponse,
    # Daily Companion
    CompanionData,
    DailyCompanionResponse,
    # Learning / Intelligence Brief
    IntelligenceBriefData,
    IntelligenceBriefResponse,
    # Chat
    AIResponseData,
    AIResponse,
    ChatMessage,
    ChatConversation,
    ChatHistoryResponse,
    # AI Telemetry
    ProviderTelemetry,
    AITelemetryData,
    AITelemetryResponse,
    # Memory
    MemoryItem,
    MemoryListResponse,
    MemoryPromoteResponse,
    MemoryDemoteResponse,
    # RAG
    RAGSearchResult,
    RAGSearchResponse,
    # System
    HealthCheckResponse,
    VersionResponse,
    # Error
    ErrorResponse,
)

# The interactive API docs and the machine-readable schema list every route and field: useful while developing, a map for attackers once live.
# On Render (and anywhere BUBBLES_ENABLE_DOCS is not "1") they are switched off.
if os.getenv("RENDER") and not os.getenv("BUBBLES_DOC_SIGNING_KEY"):
    # Signed documents (partner links, plans, settings) fall back to the database service key. Rotating that key would then invalidate all of
    # them at once, so set BUBBLES_DOC_SIGNING_KEY (to the value the service key has TODAY) before rotating anything. See DEPLOY.md.
    import logging as _logging
    _logging.getLogger("bubbles.startup").warning("BUBBLES_DOC_SIGNING_KEY is not set: signed documents use the service key as their signing key.")
install_access_log_redaction()  # share tokens and search terms never reach the server log
_DOCS_ON = os.getenv("BUBBLES_ENABLE_DOCS") == "1" or not os.getenv("RENDER")
app = FastAPI(
    title="Bubbles API",
    docs_url="/docs" if _DOCS_ON else None,
    redoc_url="/redoc" if _DOCS_ON else None,
    openapi_url="/openapi.json" if _DOCS_ON else None,
)
register_db_error_handlers(app)


@app.middleware("http")
async def bubbles_security_headers(request, call_next):
    # This is the innermost middleware. An exception that escapes it is turned into a 500 by Starlette's
    # outermost layer, which sits OUTSIDE CORS: the response then has no CORS headers and the browser reports
    # a network failure ("can't connect to the backend") although the server answered. Catching here keeps the
    # error readable, so the app can tell "server problem" from "server not running".
    tz_token = REQUEST_TZ.set(parse_tz_header(request.headers.get("x-tz-offset-minutes")))
    request_id, *ops_tokens = ops_telemetry.begin_request()   # one id per request: ties AI attempts and log lines together
    started = perf_counter()
    blocked = _guard_request(request)
    if blocked is None and _is_admin_path(request.url.path):
        blocked = await run_in_threadpool(_admin_gate, request)   # before routing, so a non-admin learns nothing (see _admin_gate)
    try:
        response = blocked if blocked is not None else await call_next(request)
    except Exception as error:  # noqa: BLE001
        from logging_util import logger
        # lets a user-reported "something went wrong" be tied to one log line (no health text is logged)
        logger.error(component="API", operation="unhandled_exception", error=error,
                     context={"path": request.url.path, "method": request.method, "error_class": type(error).__name__, "request_id": request_id}, fallback_action="returning_json_500")
        if is_permission_denied(error):  # a permission error wrapped in some other exception type
            response = database_permission_response(error)
        else:
            response = JSONResponse(status_code=500, content={"detail": "Something went wrong on Bubbles' side. Please try again.", "code": "server_error", "request_id": request_id},
                                    headers={"X-Request-Id": request_id})
    REQUEST_TZ.reset(tz_token)
    try:
        _record_api_event(request, response, started)
    except Exception:  # noqa: BLE001 - telemetry never changes the answer
        pass
    finally:
        ops_telemetry.end_request(tuple(ops_tokens))
    if response.status_code == 401 and request.headers.get("authorization") and edge_client_ip(request):
        _auth_fail_limiter.record("ip:" + edge_client_ip(request))
    for key, value in security_headers().items():
        response.headers[key] = value
    response.headers["X-Request-Id"] = request_id
    return response


# --------------------------------------------------
# ADMIN GATE AND REQUEST TELEMETRY
# --------------------------------------------------

def _is_admin_path(path: str) -> bool:
    return path == "/admin" or path.startswith("/admin/")


def _not_found() -> JSONResponse:
    """Byte for byte what FastAPI answers for a path that does not exist."""
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


_admin_denials = {"count": 0, "last_row": float("-inf")}  # not 0.0: monotonic() is uptime, under 60 s on a fresh host
_admin_denials_lock = threading.Lock()


def _admin_denied(reason: str) -> JSONResponse:
    """Counts the refusal; at most one audit row a minute (a flood of junk tokens cannot fill the database). No token, address or id."""
    with _admin_denials_lock:
        _admin_denials["count"] += 1
        write = time.monotonic() - _admin_denials["last_row"] > 60
        if write:
            _admin_denials["last_row"] = time.monotonic()
        count = _admin_denials["count"]
    if write:
        ops_telemetry.record("audit", action="admin_denied", target=reason, outcome=f"refusals_so_far={count}")
    return _not_found()


def _admin_gate(request) -> JSONResponse | None:
    """Every /admin/* request: a fresh (never cached) sign-in check, a two-step (aal2) token and an id on BUBBLES_ADMIN_USER_IDS.

    Anything else gets the same 404 as an unknown path, before routing, so a wrong method or a malformed body cannot reveal that a
    route exists. A bad token still counts toward the address's bad-token limit, so /admin is no place to guess tokens."""
    authorization = request.headers.get("authorization")
    if not admin_ids():
        return _admin_denied("no_admins_configured")
    if not authorization:
        return _admin_denied("no_token")
    try:
        user = get_authenticated_user(authorization, fresh=True)
    except Exception:  # noqa: BLE001 - every failure looks the same from outside
        if edge_client_ip(request):
            _auth_fail_limiter.record("ip:" + edge_client_ip(request))
        return _admin_denied("sign_in_failed")
    if token_aal(_bearer_token(authorization)) != "aal2":
        return _admin_denied("two_step_required")
    if str(getattr(user, "id", "")) not in admin_ids():
        return _admin_denied("not_admin")
    request.state.admin_user_id = str(user.id)
    return None


_KNOWN_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})
_STATUS_ERROR = {401: "auth", 403: "authorization", 409: "validation", 413: "validation", 422: "validation", 429: "rate_limit", 503: "database"}


def _record_api_event(request, response, started: float) -> None:
    """One metadata-only event per request: method, route TEMPLATE (never the raw path or query), status, time, and the chat note."""
    path = request.url.path
    if request.method == "OPTIONS" or _is_admin_path(path):   # the portal's own polling is not traffic
        return
    route = getattr(request.scope.get("route"), "path", None) or "unmatched"
    latency = round((perf_counter() - started) * 1000, 1)
    method = request.method if request.method in _KNOWN_METHODS else "OTHER"   # the method is client text: only known names are kept
    ops_telemetry.record("api", method=method, route=route, status=response.status_code, latency_ms=latency,
                         **ops_telemetry.current_note())
    status = response.status_code
    if status >= 400 and status != 404:
        category = _STATUS_ERROR.get(status, "internal" if status >= 500 else "validation")
        if status != 500:   # an unhandled 500 already recorded its error through the logger
            ops_telemetry.record("error", category=category, component="API", route=route, error_class=f"HTTP {status}",
                                 severity="error" if status >= 500 else "info")


# Coarse protection for the Whole-Health OS routes: a request-size cap and a per-user request budget (the chat has its own limiter).
_GUARDED_PREFIXES = ("/onboarding", "/experience", "/fitness", "/wellness", "/cycle", "/notifications", "/import", "/me/", "/profile/body", "/partner", "/chat/feedback")
_MAX_BODY_BYTES = 1_500_000
_route_limiter = RateLimiter(limit=240, window=60.0)
_public_limiter = RateLimiter(limit=30, window=60.0)    # the unauthenticated partner link: slows token guessing
# In front of EVERY route (before any sign-in check): one address cannot flood the API, and an address that keeps sending bad tokens is
# stopped before each request costs a call to the sign-in service. The limits are generous for real people and are env-tunable.
_ip_limiter = RateLimiter(limit=int(os.getenv("BUBBLES_IP_RATE_LIMIT", "900")), window=60.0)
_auth_fail_limiter = RateLimiter(limit=int(os.getenv("BUBBLES_AUTH_FAIL_LIMIT", "30")), window=60.0)
_connect_limiter = RateLimiter(limit=int(os.getenv("BUBBLES_CONNECT_RATE_LIMIT", "20")), window=3600.0)  # partner invite codes: slows guessing across accounts
_TOO_FAST = {"detail": "You're going a little fast. Please wait a moment and try again.", "code": "rate_limited"}


def client_ip(request) -> str:
    """Caller address for rate limits. Behind Render/Cloudflare X-Forwarded-For can carry client-supplied hops on its left, so
    trust CF-Connecting-IP (set by Cloudflare) first, then only the rightmost hop (added by the nearest proxy)."""
    cf = (request.headers.get("cf-connecting-ip") or "").strip()
    if cf:
        return cf
    hops = [h.strip() for h in (request.headers.get("x-forwarded-for") or "").split(",") if h.strip()]
    if hops:
        return hops[-1]
    return request.client.host if request.client else "?"


def edge_client_ip(request) -> str | None:
    """The visitor's own address as Cloudflare saw it, or None when the request did not come through Cloudflare.

    The address limits below use ONLY this header. Without it the only candidate is a proxy hop that could be shared by everyone, and one
    shared bucket would let a single bad actor lock every real user out, so in that case these limits stand aside (the per-user and
    per-route limits still apply)."""
    return (request.headers.get("cf-connecting-ip") or "").strip() or None


def _guard_request(request):
    path = request.url.path
    ip = edge_client_ip(request)
    if ip is not None and path != "/health":  # the host's own health checks must always get through
        if not _ip_limiter.allow("ip:" + ip):
            return JSONResponse(status_code=429, content=_TOO_FAST, headers={"Retry-After": "30"})
        if request.headers.get("authorization") and _auth_fail_limiter.over("ip:" + ip):
            return JSONResponse(status_code=429, content=_TOO_FAST, headers={"Retry-After": "60"})
    if ip is not None and path == "/partner-sharing/connect" and not _connect_limiter.allow("ip:" + ip):
        return JSONResponse(status_code=429, content=_TOO_FAST, headers={"Retry-After": "600"})
    if not path.startswith(_GUARDED_PREFIXES):
        return None
    try:
        size = int(request.headers.get("content-length") or 0)
    except ValueError:
        size = 0
    if size > _MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "That request is too large.", "code": "too_large"})
    auth = request.headers.get("authorization")
    public = path.startswith(("/cycle/partner/", "/partner/"))
    key = ("ip:" + client_ip(request)) if (public or not auth) else "t:" + auth[-32:]
    if not (_public_limiter if public else _route_limiter).allow(key):
        return JSONResponse(status_code=429, content={"detail": "You're going a little fast. Please wait a moment and try again.", "code": "rate_limited"}, headers={"Retry-After": "30"})
    return None


# Request bodies are capped everywhere, including chunked ones with no Content-Length (the guarded prefixes above keep a lower cap).
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "BUBBLES_FRONTEND_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,https://heybubbles.in,https://www.heybubbles.in",
        ).split(",")
        if origin.strip()
    ],
    # Any loopback port is allowed too (not on Render): when port 3000 is busy Next.js starts on 3001, and a browser on a
    # port that is not in the list above blocks every request, which looks exactly like a dead backend.
    allow_origin_regex=None if os.getenv("RENDER") else r"^http://(localhost|127\.0\.0\.1)(:\d{2,5})?$",
    allow_credentials=False,       # Bearer tokens in a header, no cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tz-Offset-Minutes"],
)


# --------------------------------------------------
# HEALTH
# --------------------------------------------------

_probe_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="db-probe")
_probe_future = None


def _database_report(timeout: float = 2.0) -> dict:
    """The cached database probe, but never slower than `timeout`: /health must always answer quickly, or a
    running backend would look dead whenever Supabase is slow."""
    global _probe_future
    if _probe_future is None or _probe_future.done():
        _probe_future = _probe_pool.submit(probe_database, supabase)
    try:
        return _probe_future.result(timeout=timeout)
    except Exception:  # noqa: BLE001 - still running, or the probe itself failed
        return {"database": "unknown", "denied": [], "accessible": [], "compat_mode": False}


@app.on_event("startup")
def _warm_database_probe() -> None:
    """Start the database probe at launch so the first /health already reports the real state (not 'unknown')."""
    try:
        _database_report(timeout=0.01)
    except Exception:  # noqa: BLE001 - startup must never fail because of a diagnostic
        pass
    threading.Thread(target=lambda: analyze_turn("hello", []), name="bubbles-warm-analyze", daemon=True).start()   # the first message after a deploy no longer pays the one-off start-up cost
    if ops_telemetry._persist_enabled():   # saved admin settings (provider pauses, retention): read once, in the background
        import threading
        threading.Thread(target=admin_settings.load, name="bubbles-settings-load", daemon=True).start()


# HEAD is allowed too: uptime monitors (UptimeRobot, Render, load balancers) often probe with HEAD and would otherwise see 405 and report "down"
@app.api_route("/health", methods=["GET", "HEAD"], response_model=HealthCheckResponse)
def health_check():
    """Unauthenticated liveness plus a row-free database report (cached 30 s): ok | permission_denied | unreachable."""
    probe = _database_report()
    status = "healthy" if probe["database"] in {"ok", "permission_denied", "unknown"} else "degraded"
    return HealthCheckResponse(
        status=status,
        version="0.1.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        services={"api": "healthy", "database": probe["database"]},
        compat_mode=bool(probe["compat_mode"]),
        denied_tables=list(probe["denied"]),
    )


# --------------------------------------------------
# CHAT REQUEST
# --------------------------------------------------

def build_deterministic_red_response(assessment):
    """Return urgent guidance without delegating RED routing to an LLM."""
    reasons = list(assessment.reasons)
    reason_text = ", ".join(reasons) if reasons else "a potentially serious symptom"
    return (
        "### Please get urgent medical help\n\n"
        f"Bubbles detected {reason_text} in what you described. "
        "If this is happening now or feels severe, contact your local emergency service "
        "or go to the nearest emergency department now.\n\n"
        "### While getting help\n"
        "- Do not drive yourself if you feel faint, confused, severely unwell, or unsafe to travel.\n"
        "- If someone is nearby, tell them what is happening and ask them to stay with you.\n"
        "- Bubbles cannot safely determine the cause of a red-flag symptom from chat alone."
    )


class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=8000)
    message_id: str | None = Field(default=None, min_length=16, max_length=128)
    conversation_id: str | None = Field(default=None, max_length=64)


# --------------------------------------------------
# MEMORY PROMOTION REQUEST
# --------------------------------------------------

class MemoryPromotionRequest(BaseModel):
    event_id: str
    event_type: str
    extracted_data: dict
    confidence: float
    user_confirmed: bool = False


# --------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------

# Verified sign-ins are remembered for at most 30 s (never past the token's own expiry), so a burst of API calls costs one round trip
# to the sign-in service instead of one each. Only successes are kept; the key is a hash of the token and is never logged or shown.
# Trade-off accepted in review (docs/admin/DESIGN.md): a token that was just signed out keeps working for up to 30 s. /admin never uses it.
_sign_in_cache = TTLCache("sign_in", ttl_s=30, max_entries=2000)


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise missing_auth_header_response()

    if not authorization.startswith("Bearer "):
        raise invalid_auth_header_response()

    token = authorization.replace("Bearer ", "", 1).strip()

    if not token:
        raise invalid_token_response()
    return token


def get_authenticated_user(authorization: str | None, *, fresh: bool = False):
    token = _bearer_token(authorization)
    if fresh:
        return _verify_token(token)
    return _sign_in_cache.get_or_compute(
        hashlib.sha256(token.encode("utf-8")).hexdigest(), lambda: _verify_token(token),
        ttl_for=lambda _user: (token_exp(token) or 0) - time.time(),
    )


def _verify_token(token: str):
    try:
        response = supabase.auth.get_user(token)

        if not response.user:
            raise invalid_token_response()

        # Two-step sign-in is enforced here, not only in the browser: a password-only session cannot use the API once the account turned it on.
        if requires_second_step(response.user, token):
            raise unauthorized_response("Two-step sign-in is required. Please sign in again and enter your authenticator code.")

        return response.user

    except HTTPException:
        raise

    except Exception as error:
        from logging_util import logger
        error_str = str(error)
        # Surface misconfiguration separately from token failures
        if "Invalid API key" in error_str or "api_key" in error_str.lower():
            logger.error(
                component="AUTH",
                operation="get_authenticated_user",
                error=error,
                detail="Backend SUPABASE_SECRET_KEY may be invalid or still set to placeholder value",
                fallback_action="raising_401_config_error",
            )
        else:
            logger.error(
                component="AUTH",
                operation="get_authenticated_user",
                error=error,
                fallback_action="raising_unauthorized",
            )

        raise invalid_token_response()


# User-entered tracker endpoints (/health/<domain>, /health/summary, suggestions).
app.include_router(build_health_logs_router(get_authenticated_user, supabase))
# Fitness: body profile, food log, diet / workout planners, strict Transformation mode.
app.include_router(build_fitness_router(get_authenticated_user, supabase))
app.include_router(build_data_rights_router(get_authenticated_user, supabase))
# Sleep, hydration, medications, mind check-ins and notifications.
app.include_router(build_wellness_router(get_authenticated_user, supabase))
app.include_router(build_chat_feedback_router(get_authenticated_user, supabase))
app.include_router(build_consent_router(get_authenticated_user, supabase))
app.include_router(build_client_telemetry_router())   # POST /telemetry/client: a fixed problem code, nothing else
app.include_router(build_confirm_router(get_authenticated_user, supabase))   # POST /health-events/confirmation (batch) + the old single PATCH
app.include_router(build_onboarding_router(get_authenticated_user, supabase))
app.include_router(build_import_router(get_authenticated_user, supabase))
# Cycle: calendar, daily log, predictions with ranges, modes, insights, report, partner view.
app.include_router(build_cycle_router(get_authenticated_user, supabase))
app.include_router(build_partner_router(get_authenticated_user, supabase))
app.include_router(build_organ_map_router(get_authenticated_user, supabase))
app.include_router(build_admin_router(lambda: _database_report()))   # /admin/*: gated in the middleware (_admin_gate)


# --------------------------------------------------
# IDENTITY + PERSONAL MEMORY
# --------------------------------------------------

_profile_sync_paused_until = 0.0
_profile_synced = TTLCache("profile_sync", ttl_s=3600, max_entries=20000)   # only "this person's name is already stored", nothing else


def sync_profile_from_auth(user):
    """Best-effort sync of explicit auth identity into the existing profiles table."""
    global _profile_sync_paused_until
    metadata = getattr(user, "user_metadata", {}) or {}
    name = (metadata.get("full_name") or metadata.get("name") or "").strip()
    if not name or perf_counter() < _profile_sync_paused_until:
        return
    if _profile_synced.peek(str(user.id)):   # stored already (seen in the last hour): no database read at all
        return
    try:
        existing = (supabase.table("profiles").select("display_name")
                    .eq("id", str(user.id)).limit(1).execute().data or [])
        current = (existing[0].get("display_name") or "").strip() if existing else ""
        if current:
            _profile_synced.put(str(user.id), True)
            return
        supabase.table("profiles").upsert(
            {"id": str(user.id), "display_name": name},
            on_conflict="id",
        ).execute()
        chat_cache.forget_user(str(user.id))   # the next reply sees the new name
        _profile_synced.put(str(user.id), True)
    except Exception as error:
        if is_permission_denied(error):
            # profiles is not writable yet: stop paying two failing round trips on every chat message for 5 minutes.
            _profile_sync_paused_until = perf_counter() + 300
        from logging_util import logger
        logger.error(
            component="PROFILE",
            operation="sync_profile_from_auth",
            error=error,
            user_id=str(user.id) if user else None,
            fallback_action="profile_sync_skipped",
        )


def _ensure_conversation(user_id: str, conversation_id: str | None, title: str) -> str:
    """Resolve/create a conversation owned by the authenticated user."""
    if conversation_id:
        try:
            UUID(conversation_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid conversation id") from exc
        existing = (supabase.table("chat_conversations")
                    .select("id")
                    .eq("id", conversation_id)
                    .eq("user_id", user_id)
                    .limit(1).execute().data or [])
        if not existing:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation_id

    created = (supabase.table("chat_conversations")
               .insert({"user_id": user_id, "title": title[:120]})
               .select("id").execute())
    if not created.data or len(created.data) == 0 or not created.data[0].get("id"):
        raise HTTPException(status_code=500, detail="Unable to create conversation")
    return str(created.data[0]["id"])


def _persist_chat_message(*, user_id: str, conversation_id: str, role: str, content: str,
                          metadata: dict | None = None, client_message_id: str | None = None,
                          return_created: bool = False):
    """Single backend-owned persistence path for chat messages.

    Returns the message id, or (id, created) when ``return_created`` is set; ``created`` is False when an
    idempotent retry matched an existing message.
    """
    if role not in {"user", "bubbles"}:
        raise ValueError("Unsupported chat role")
    out = (lambda message_id, created: (message_id, created)) if return_created else (lambda message_id, created: message_id)
    payload = {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "metadata": metadata or {},
    }
    if client_message_id:
        payload["client_message_id"] = client_message_id
    try:
        # Insert first: the unique index (uq_chat_messages_user_client_message) refuses a repeated key, so the common case (a new message)
        # costs one round trip, not a read and then a write.
        saved = supabase.table("chat_messages").insert(payload).select("id").execute()
    except Exception as error:
        # A concurrent retry can win the unique idempotency race (a plain repeat hits the same index). Resolve it by reading the winner
        # rather than creating a second logical message.
        if client_message_id:
            winner = (supabase.table("chat_messages")
                      .select("id,conversation_id,role,content")
                      .eq("user_id", user_id)
                      .eq("client_message_id", client_message_id)
                      .limit(1).execute().data or [])
            if winner:
                prior = winner[0]
                if (str(prior.get("conversation_id")) != conversation_id
                        or prior.get("role") != role
                        or prior.get("content") != content):
                    raise HTTPException(status_code=409, detail="Chat idempotency key was already used for different content")
                return out(str(prior["id"]), False)
        raise RuntimeError("Chat message persistence failed") from error
    if not saved.data or len(saved.data) == 0 or not saved.data[0].get("id"):
        raise RuntimeError("Chat message persistence failed")
    return out(str(saved.data[0]["id"]), True)


def _touch_conversation(conversation_id: str, user_id: str) -> None:
    try:
        (supabase.table("chat_conversations").update({"updated_at": datetime.now(timezone.utc).isoformat()})
         .eq("id", conversation_id).eq("user_id", user_id).execute())
    except Exception as error:
        from logging_util import logger
        logger.warning(
            component="CHAT",
            operation="touch_conversation",
            message="conversation timestamp update skipped",
            context={"conversation_id": conversation_id, "error_type": type(error).__name__},
        )

# --------------------------------------------------
# CHAT
# --------------------------------------------------

_chat_limiter = RateLimiter(limit=int(os.getenv("BUBBLES_CHAT_RATE_LIMIT", "30")), window=60.0)

# Optional enrichers are time-boxed: a slow evidence lookup is dropped (the reply says no outside evidence was found), a slow read of
# the person's own context is waited for longer and logged, never dropped quietly.
RAG_BUDGET_S = max(0.5, float(os.getenv("CHAT_RAG_BUDGET_S", "2.0")))
CONTEXT_BUDGET_S = max(2.0, float(os.getenv("CHAT_CONTEXT_BUDGET_S", "8.0")))
_DETERMINISTIC_ROUTES = {"emergency", "correction", "clarification", "daily_log", "fitness_support", "fitness_answer", "small_talk", "safety_followup"}


def _debug_trace_enabled() -> bool:
    # The trace puts fact text in /chat responses: never on the live server, whatever the setting says.
    return not os.getenv("RENDER") and os.getenv("BUBBLES_DEBUG_TRACE", "false").strip().lower() in {"1", "true", "yes"}


def _reasons_text(reasons: list[str]) -> list[str]:
    return [str(r) for r in reasons][:8]


def _ms(since: float) -> float:
    return round((perf_counter() - since) * 1000, 1)


@dataclass
class _ChatState:
    """What the first half of a chat turn (sign-in to the safety gate) found out; the second half (the reply) works from it."""
    user: Any
    user_id: str
    user_message: str
    conversation_id: str
    started: float
    history: list = field(default_factory=list)
    user_message_id: str | None = None
    memory_saved: Any = None
    turn: Any = None
    name: str = ""
    rule_events: list = field(default_factory=list)
    consent_required: bool = False
    fresh: bool = False   # the user message was just created (not a retry), so none of its events exist yet
    timings: dict = field(default_factory=dict)
    early: dict | None = None   # a finished answer (empty message, replay of a retry): nothing more to compute

    @property
    def deterministic(self) -> bool:
        return self.turn is not None and (self.turn.route in _DETERMINISTIC_ROUTES or self.consent_required)

    def meta(self) -> dict:
        """What is known as soon as the safety gate is: shown by the stream before any reply text exists."""
        if self.early is not None:
            return {"conversation_id": self.conversation_id, "user_message_id": self.early.get("user_message_id"),
                    "safety": self.early.get("safety"), "kind": self.early.get("kind", "reply"),
                    "consent_required": bool(self.early.get("consent_required"))}
        return {"conversation_id": self.conversation_id, "user_message_id": self.user_message_id, "safety": safety_payload(self.turn.safety),
                "kind": reply_kind(self.turn.route), "consent_required": self.consent_required}


def _chat_gate(user, request) -> str:
    """Rate limit and profile sync for one chat request. Returns the user id."""
    user_id = str(user.id)
    if not _chat_limiter.allow(user_id):
        raise HTTPException(status_code=429, detail="You're sending messages very quickly. Please wait a moment and try again.")
    sync_profile_from_auth(user)
    return user_id


def _chat_prepare(user, user_id: str, request: ChatRequest) -> _ChatState:
    """Sign-in to the safety gate: find or make the conversation (with its recent turns, read side by side), save the message, understand
    it, decide which kind of reply it gets. Nothing here calls an AI model."""
    started = perf_counter()
    user_message = request.message.strip()
    history: list = []
    if not user_message:
        conversation_id = _ensure_conversation(user_id, request.conversation_id, "Bubbles conversation")
        response_text = "I'm here 💗 Tell me what's on your mind."
        ops_telemetry.note(route_kind="empty", safety_level="GREEN", ai_called=False)
        empty_safety = {"level": "GREEN", "state": "NO_REDFLAG", "reasons": [], "retracted": False}
        bubbles_message_id = _persist_chat_message(
            user_id=user_id, conversation_id=conversation_id, role="bubbles", content=response_text,
            metadata={"source": "bubbles_api", "kind": "reply", "safety": empty_safety},
        )
        _touch_conversation(conversation_id, user_id)
        state = _ChatState(user, user_id, user_message, conversation_id, started)
        state.early = {
            "response": response_text, "sentiment": "neutral", "kind": "reply", "safety": empty_safety, "health_events": [],
            "health_event_ids": [], "message_id": bubbles_message_id, "conversation_id": conversation_id, "user_message_id": None, "user_id": user.id,
        }
        return state

    # Recent turns of THIS conversation (owner-scoped) give the message its antecedent: "I said no chest pain?" is meaningless without
    # what was said before. Read before saving the new message, at the same time as the ownership check. A new chat has none to read.
    if request.conversation_id:
        history_job = submit_io(settled, load_history, supabase, user_id, request.conversation_id)
        conversation_id = _ensure_conversation(user_id, request.conversation_id, user_message)
        history = history_job.result()[0] or []
    else:
        conversation_id = _ensure_conversation(user_id, None, user_message)
    state = _ChatState(user, user_id, user_message, conversation_id, started, history=history)
    state.user_message_id, created = _persist_chat_message(
        user_id=user_id, conversation_id=conversation_id, role="user", content=user_message,
        metadata={"source": "user_input"}, client_message_id=request.message_id, return_created=True,
    )
    state.fresh = created
    if not created:
        # A retry of a message we already answered: return the stored answer instead of re-running the model
        # and duplicating events.
        replay = find_stored_reply(supabase, user_id, conversation_id, state.user_message_id)
        if replay:
            replay["user_id"] = user.id
            state.early = replay
            return state
    # Keep health content out of application logs; operational telemetry records only safe metadata.

    explicit_facts = extract_explicit_personal_facts(user_message)
    state.memory_saved = persist_explicit_facts(user_id, state.user_message_id, explicit_facts)

    # ---- 1. understand: facts (negation, tense, who, severity), safety state, correction, contradictions, daily log
    turn = analyze_turn(user_message, history)
    state.turn = turn
    state.name = first_name(user)
    state.timings = dict(turn.timings_ms)
    state.rule_events = [] if turn.route == "correction" else build_rule_events(turn, state.user_message_id)
    if turn.pause_strict_plan:   # restriction language arrived with an urgent/uncertain safety state: the safety reply wins, the plan still pauses
        try:
            from fitness_chat import pause_active_plan
            pause_active_plan(supabase, user_id)
        except Exception:  # noqa: BLE001
            pass
    # Only open-ended replies go to an outside AI model, and only after a clear yes (consent.py). Everything else, including every
    # emergency, is answered here and never depends on it.
    state.consent_required = turn.route not in _DETERMINISTIC_ROUTES and not has_ai_consent(supabase, user_id)
    # Technical facts only, from fixed lists (ops_telemetry.NOTE_VALUES): which kind of reply, the safety level, whether a model was asked.
    try:
        ops_telemetry.note(route_kind="consent_needed" if state.consent_required else turn.route, safety_level=turn.safety.level,
                           ai_called=not state.deterministic, stage_pre_ms=_ms(started))
    except Exception:  # noqa: BLE001 - telemetry never interrupts a reply
        pass
    return state


def _context_stage(user_id: str, user_message: str) -> tuple[str, float]:
    """The person's own context as prompt text (profile, memory, recent events, trends, patterns in their logs)."""
    t0 = perf_counter()
    user_context = build_user_context(user_id=user_id, query=user_message)
    memory_context = format_user_context(user_context)

    # Concrete metrics from stored events (best effort)
    try:
        recent_events = user_context.get("recent_events", [])
        health_state = build_health_state(recent_events, days=14)
        if health_state.get("baseline") or health_state.get("deviations"):
            health_metrics = "\n\nRECENT HEALTH METRICS:\n"
            if health_state.get("baseline"):
                health_metrics += "Baseline (past 14 days):\n"
                for metric, value in health_state["baseline"].items():
                    health_metrics += f"- {metric}: {value}\n"
            if health_state.get("deviations"):
                health_metrics += "\nCurrent trends (last 14 days vs baseline):\n"
                for metric, data in health_state["deviations"].items():
                    health_metrics += f"- {metric}: {data.get('current')} (baseline: {data.get('baseline')}, change: {data.get('percent')}%)\n"
            memory_context += health_metrics
    except Exception as error:
        from logging_util import logger
        logger.warning(component="CHAT", operation="health_state_retrieval", error=error, user_id=user_id,
                       fallback_action="continuing_without_metrics")

    try:  # the user's own log patterns (cached; never waits on a computation)
        memory_context += association_loader.chat_block(supabase, user_id)
    except Exception as error:  # noqa: BLE001
        from logging_util import logger
        logger.warning(component="CHAT", operation="association_block", error=error, fallback_action="continuing_without_patterns")
    return memory_context, _ms(t0)


def _evidence_stage(user_id: str, query: str) -> tuple[list[dict], float]:
    t0 = perf_counter()
    try:
        results = hybrid_search(query=query, user_id=user_id, limit=6)
    except Exception as error:
        from logging_util import logger
        logger.error(component="RAG", operation="hybrid_search", error=error, user_id=user_id,
                     context={"query_length": len(query)}, fallback_action="using_empty_evidence")
        results = []
    return results, _ms(t0)


def _after_turn(conversation_id: str, user_id: str, route: str, state_name: str, event_count: int, timings: dict) -> None:
    """Housekeeping that needs nothing from the person's screen: runs after the reply has been sent."""
    _touch_conversation(conversation_id, user_id)
    from logging_util import logger
    logger.info(component="CHAT", operation="turn", user_id=user_id, context={
        "route": route, "state": state_name, "events": event_count, "timings_ms": timings,
    })  # no symptom concepts here: a log line tied to a user id must not say what they reported


def _chat_respond(state: _ChatState, defer) -> dict:
    """The second half of a chat turn: the reply text (deterministic copy, or the model's after the output guards), saving, the payload.
    ``defer(fn, *args)`` runs housekeeping after the answer is out."""
    if state.early is not None:
        return state.early
    user_id, user_message, turn, safety = state.user_id, state.user_message, state.turn, state.turn.safety
    user_message_id, name, timings = state.user_message_id, state.name, state.timings
    ai_events: list = []
    evidence_results: list[dict] = []
    package_audit_meta: dict | None = None
    sentiment = "neutral"
    persisted: list[dict] = []
    stage = {"ctx": 0.0, "rag": 0.0, "ai": 0.0}
    post_started = perf_counter()
    if turn.route in _DETERMINISTIC_ROUTES or state.consent_required:
        # Deterministic copy: RED is a hard gate, so neither the message nor health context reaches a provider.
        t0 = perf_counter()
        # While waiting for the yes nothing is saved: the same message is asked again after it and saved once then (saving both would count a symptom twice).
        persisted = [] if state.consent_required else persist_events(supabase, user_id, user_message_id, state.rule_events, fresh=state.fresh)
        timings["events_ms"] = _ms(t0)
        if state.consent_required:
            # An urgent message still gets the fixed urgent text, not a question about AI models.
            response_text = urgent_fallback_response(safety) if safety.state == "URGENT" else consent_needed_reply(name)
        else:
            response_text = deterministic_reply(turn, name=name, saved_events=sum(1 for e in persisted if e["id"]))
        if turn.route in {"fitness_support", "fitness_answer"}:
            response_text = _fitness_text(user_id, user_message)
    else:
        # The person's own context, the evidence lookup and the tone settings do not depend on each other: started together, after the
        # safety gate (evidence is never fetched before it, and only for topics the person actually raised, never for denied or other
        # people's symptoms).
        query = evidence_query(turn.facts, user_message)
        ctx_job = submit(_context_stage, user_id, user_message)
        rag_job = submit(_evidence_stage, user_id, query) if query else None
        style_job = submit_io(settled, chat_cache.style_block, supabase, user_id)
        try:
            memory_context, stage["ctx"] = ctx_job.result(timeout=CONTEXT_BUDGET_S)
        except Exception as error:  # noqa: BLE001 - never a silent loss: the reply still goes out and the miss is logged
            from logging_util import logger
            logger.warning(component="CHAT", operation="context_stage", error=error, user_id=user_id, fallback_action="replying_without_personal_context")
            memory_context, stage["ctx"] = "", CONTEXT_BUDGET_S * 1000
        if rag_job is not None:
            try:
                evidence_results, stage["rag"] = rag_job.result(timeout=RAG_BUDGET_S)
            except Exception as error:  # noqa: BLE001 - optional enrichment: the reply says no outside evidence was found
                from logging_util import logger
                logger.warning(component="RAG", operation="hybrid_search_budget", error=error, user_id=user_id, fallback_action="using_empty_evidence")
                evidence_results, stage["rag"] = [], RAG_BUDGET_S * 1000
        timings["rag_ms"] = stage["rag"]
        # The model gets the same three sources the screen shows, each trimmed: more only slows the answer.
        evidence_context = build_evidence_context(shown_evidence(evidence_results), max_chars=1200)
        try:  # audit trail only for now: the model still receives the same context blocks
            package_audit_meta = package_audit(build_package(
                plan=plan_task(user_message, has_health_topic=bool(query)), safety=safety_payload(safety),
                personal_facts=[f.to_dict() for f in turn.facts if f.experiencer == "self"], evidence=evidence_results))
        except Exception as error:  # noqa: BLE001 - never let the audit trail break a reply
            from logging_util import logger
            logger.warning(component="CHAT", operation="evidence_package", error=error, fallback_action="no_audit_trail")

        recent_block = conversation_block(state.history)
        conversation_context = "\n\n".join(filter(None, [
            ("RECENT CONVERSATION (oldest first):\n" + recent_block) if recent_block else "",
            state_block(turn.facts, turn.history_facts),
        ]))
        style = style_job.result()[0] or ""
        # What the person said about themselves is saved while the model thinks (the model only PROPOSES more events afterwards).
        rule_job = submit_io(settled, persist_events, supabase, user_id, user_message_id, state.rule_events, fresh=state.fresh) if state.rule_events else None
        t0 = perf_counter()
        ai_result = ask_bubbles(
            user_message,
            memory_context=memory_context,
            evidence_context=evidence_context,
            safety_context=safety_instruction(safety) + "\n\n" + response_style_instruction() + (("\n\n" + style) if style else ""),
            conversation_context=conversation_context,
        )
        stage["ai"] = _ms(t0)
        timings["ai_ms"] = stage["ai"]
        post_started = perf_counter()
        if is_degraded(ai_result):
            ai_events = []
        else:
            ai_events = ai_result.health_events
            sentiment = ai_result.sentiment

        t0 = perf_counter()
        reconciled = reconcile_ai_events(ai_events, turn, state.rule_events, user_message_id)
        proposed_saved = persist_events(supabase, user_id, user_message_id, reconciled, fresh=state.fresh)
        rule_saved = (rule_job.result()[0] or []) if rule_job is not None else []
        persisted = rule_saved + proposed_saved
        timings["events_ms"] = _ms(t0)
        if is_degraded(ai_result):
            response_text = ai_failed_reply(turn, name=name, saved_events=sum(1 for e in persisted if e["id"]))
        else:
            response_text = strip_attribution(normalize_response(ai_result.response))
            # Output guard: a medicine amount or schedule never reaches the user, whatever the model wrote (the no-dosing rule).
            response_text, _dose_removed = scrub_doses(response_text)
            _issues = lint(response_text, user_message=user_message, has_evidence=bool(evidence_results)) + (["dose_removed"] if _dose_removed else [])
            if _issues:
                from logging_util import logger
                logger.warning(component="CHAT", operation="reply_lint", error=None, user_id=user_id, context={"issues": _issues},
                               fallback_action="reply_sent")
            if safety.state == "URGENT" and not re.search(r"today|doctor|clinician|urgent[- ]care|emergency", response_text, re.I):
                response_text += "\n\nPlease speak to a clinician or an urgent-care service today."   # a soft tone can never drop the call to action
            note = contradiction_note(turn.conflicts)
            if note:
                response_text += "\n\n" + note

    # ---- 3. save the reply (+ retract a wrong warning when the user corrected us)
    correction_payload = None
    safety_dict = safety_payload(safety)
    kind = reply_kind(turn.route)
    evidence_ids = [row.get("chunk_id") for row in evidence_results if row.get("chunk_id")]
    metadata = stored_metadata(kind=kind, user_message_id=user_message_id, safety=safety_dict, events=persisted,
                               evidence_ids=evidence_ids, conflicts=turn.conflicts, trace=semantic_trace(turn), package=package_audit_meta)
    if state.consent_required:
        metadata["consent_required"] = True   # so the card survives a replay and a reload
    bubbles_message_id = _persist_chat_message(
        user_id=user_id, conversation_id=state.conversation_id, role="bubbles", content=response_text, metadata=metadata,
    )
    if turn.route == "correction":
        outcome = apply_correction(supabase, user_id=user_id, conversation_id=state.conversation_id, correction=turn.correction,
                                   correction_message_id=bubbles_message_id, history=state.history)
        rejected_ids, kept_ids = [], []
        try:
            rows = (supabase.table("extracted_health_events").select("id,extraction_status")
                    .eq("user_id", user_id).eq("message_id", turn.correction.reject_user_message_id or "").execute().data or [])
            rejected_ids = [str(r["id"]) for r in rows if r.get("extraction_status") == "rejected"]
            kept_ids = [str(r["id"]) for r in rows if r.get("extraction_status") != "rejected"]
        except Exception:
            pass
        correction_payload = {
            "retracted_message_id": turn.correction.retract_message_id if outcome.get("retracted_message") else None,
            "concepts": [display_name(c) for c in turn.correction.concepts],
            "retracted_event_ids": rejected_ids, "kept_event_ids": kept_ids,
        }
        safety_dict = safety_payload(safety, correction=correction_payload if correction_payload["retracted_message_id"] else None)
    defer(_after_turn, state.conversation_id, user_id, turn.route, safety.state, len(persisted), timings)
    try:
        ops_telemetry.note(stage_ctx_ms=stage["ctx"], stage_rag_ms=stage["rag"], stage_ai_ms=stage["ai"], stage_post_ms=_ms(post_started))
    except Exception:  # noqa: BLE001 - telemetry never interrupts a reply
        pass

    payload = {
        "response": response_text,
        "memory_saved": state.memory_saved,
        "sentiment": sentiment,
        "kind": kind,
        "safety": safety_dict,
        "health_events": persisted,
        "health_event_ids": [e["id"] for e in persisted],
        "conflicts": turn.conflicts[:5],
        "message_id": bubbles_message_id,
        "user_message_id": user_message_id,
        "consent_required": state.consent_required,
        "conversation_id": state.conversation_id,
        "user_id": state.user.id,
        "evidence": [
            {
                "chunk_id": row.get("chunk_id"),
                "title": row.get("title"),
                "source_name": row.get("source_name"),
                "source_url": row.get("source_url"),
                "publisher": row.get("publisher"),
                "evidence_level": row.get("evidence_level"),
                "fused_score": row.get("fused_score"),
                "source_type": "external_knowledge",
            }
            for row in shown_evidence(evidence_results)
        ],
    }
    if _debug_trace_enabled():
        payload["debug"] = {"route": turn.route, "timings_ms": timings, "trace": semantic_trace(turn),
                            "facts": [f.to_dict(include_text=True) for f in turn.facts][:40]}
    return payload


@app.post("/chat")
def chat(
    request: ChatRequest,
    background: BackgroundTasks,
    authorization: str | None = Header(default=None)
):
    user = get_authenticated_user(authorization)
    user_id = _chat_gate(user, request)
    state = _chat_prepare(user, user_id, request)
    return _chat_respond(state, background.add_task)


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


_SENTENCE_PIECE = re.compile(r"[^.!?\n]*[.!?]*\s*")


def _delta_chunks(text: str) -> list[str]:
    """The finished (already scrubbed and checked) reply cut after each sentence, so that joining the pieces gives the reply back exactly."""
    return [piece for piece in _SENTENCE_PIECE.findall(text or "") if piece]


@app.post("/chat/stream")
def chat_stream(request: ChatRequest, authorization: str | None = Header(default=None)):
    """POST /chat as server-sent events: ``meta`` the moment the safety gate is known, ``delta`` pieces of the finished reply, ``done`` (the
    same JSON /chat returns) or ``error``. Sign-in, rate limit and the gate run before the stream opens, so their errors are ordinary
    HTTP errors. Text is streamed only after the whole reply passed the dose scrubber and the other output checks: no raw model output
    is ever sent. Deterministic routes (emergency, daily log, consent card...) send ``meta`` and ``done`` only."""
    user = get_authenticated_user(authorization)
    user_id = _chat_gate(user, request)
    state = _chat_prepare(user, user_id, request)
    ctx = contextvars.copy_context()
    result: dict[str, Any] = {}
    finished = threading.Event()

    def work() -> None:
        try:
            result["payload"] = _chat_respond(state, lambda fn, *args: chat_concurrency.submit_io(fn, *args))
        except HTTPException as error:
            result["error"] = {"status": error.status_code, "detail": error.detail}
        except Exception as error:  # noqa: BLE001
            from logging_util import logger
            logger.error(component="CHAT", operation="stream_reply", error=error, user_id=user_id, fallback_action="error_event")
            result["error"] = {"status": 500, "detail": "Something went wrong. Please try again."}
        finally:
            finished.set()

    def events():
        threading.Thread(target=ctx.run, args=(work,), name="chat-stream", daemon=True).start()   # started first: a person who closes the tab still gets the reply saved
        yield _sse("meta", state.meta())
        while not finished.wait(timeout=10):
            yield ": ping\n\n"   # keeps proxies from closing a quiet connection while the model thinks
        if "error" in result:
            yield _sse("error", result["error"])
            return
        payload = result["payload"]
        if not state.deterministic and state.early is None:
            for piece in _delta_chunks(payload["response"]):
                yield _sse("delta", {"text": piece})
        yield _sse("done", payload)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


# --------------------------------------------------
# PERSONAL MEMORY / PROFILE DIAGNOSTICS
# --------------------------------------------------

@app.get("/memory/diagnostics")
def memory_diagnostics_api(authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    return {"status":"success","memory":memory_diagnostics(str(user.id))}

@app.get("/chat/history")
def chat_history_api(authorization: str | None = Header(default=None), limit: int = Query(10, ge=1, le=50),
                     before: str | None = Query(None, max_length=40)):
    """Recent conversations, newest first. ``before`` (an ISO time, the oldest ``updated_at`` already shown) pages to older ones."""
    user = get_authenticated_user(authorization)
    user_id = str(user.id)
    if before:
        try:
            datetime.fromisoformat(before.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="before must be an ISO date and time")
    try:
        # Get conversations with message count
        query = (supabase.table("chat_conversations")
                 .select("id,title,created_at,updated_at")
                 .eq("user_id", user_id))
        if before:
            query = query.lt("updated_at", before)
        conversations = query.order("updated_at", desc=True).limit(limit + 1).execute().data or []
        has_more = len(conversations) > limit
        conversations = conversations[:limit]

        # Message count for each conversation, asked at the same time: one after another this was up to 50 round trips
        # to the database before the chat screen could show anything.
        def _count(conv: dict) -> int:
            return (supabase.table("chat_messages")
                    .select("id", count="exact", head=True)
                    .eq("conversation_id", conv["id"])
                    .execute().count or 0)
        with ThreadPoolExecutor(max_workers=8, thread_name_prefix="history-count") as pool:
            for conv, msg_count in zip(conversations, pool.map(_count, conversations)):
                conv["message_count"] = msg_count

        return {"conversations": conversations, "has_more": has_more}
    except Exception as e:
        from logging_util import logger
        logger.error(
            component="CHAT",
            operation="history",
            error=e,
            user_id=user_id,
            context={"limit": limit},
            fallback_action="returning_empty_list",
        )
        # `degraded` lets the UI say "history is unavailable" instead of pretending the user has no conversations
        return {"conversations": [], "has_more": False, "degraded": True}

@app.get("/chat/conversations/{conversation_id}/messages")
def chat_conversation_messages_api(
    conversation_id: str,
    authorization: str | None = Header(default=None),
    limit: int = Query(100, ge=1, le=200),
    before: str | None = Query(None, max_length=40),
):
    """Owner-scoped read of one conversation's latest messages, oldest first. `before` (an ISO time) pages to older ones."""
    user = get_authenticated_user(authorization)
    user_id = str(user.id)
    # Same ownership gate as /chat: 400 for a malformed id, 404 for anyone else's conversation.
    _ensure_conversation(user_id, conversation_id, "")
    return _conversation_messages(user_id, conversation_id, limit, before)


def _conversation_messages(user_id: str, conversation_id: str, limit: int, before: str | None = None) -> dict:
    query = (supabase.table("chat_messages")
             .select("id,role,content,created_at,metadata")
             .eq("conversation_id", conversation_id)
             .eq("user_id", user_id))
    if before:
        try:
            datetime.fromisoformat(before.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="before must be an ISO date and time")
        query = query.lt("created_at", before)
    rows = query.order("created_at", desc=True).limit(limit + 1).execute().data or []
    has_more = len(rows) > limit
    rows = rows[:limit]
    overlay_event_status(supabase, user_id, [r["metadata"]["health_events"] for r in rows
                                             if isinstance(r.get("metadata"), dict) and isinstance(r["metadata"].get("health_events"), list)])
    def _message(row: dict) -> dict:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        safety = meta.get("safety") if isinstance(meta.get("safety"), dict) else {}
        out = {
            "id": str(row.get("id")),
            "role": row.get("role"),
            "content": row.get("content") or "",
            "created_at": row.get("created_at"),
            "safety_level": safety.get("level"),
        }
        if safety:
            # The persisted safety object keeps the original level and text for audit; `retracted` tells the UI to
            # render a withdrawn warning calmly after a reload.
            out["safety"] = {
                "level": safety.get("level"), "state": safety.get("state"), "reasons": safety.get("reasons") or [],
                "retracted": safety.get("retracted") is True, "retracted_at": safety.get("retracted_at"),
                "retracted_by_message_id": safety.get("retracted_by"),
            }
        if meta.get("kind"):
            out["kind"] = meta.get("kind")
        if isinstance(meta.get("health_events"), list):
            out["health_events"] = meta["health_events"]
            if isinstance(meta.get("health_events_more"), int):
                out["health_events_more"] = meta["health_events_more"]   # cards beyond the stored cap: the UI says "N more"
        if meta.get("consent_required") is True:
            out["consent_required"] = True
        return out

    return {
        "status": "success",
        "conversation_id": conversation_id,
        "messages": [_message(row) for row in reversed(rows)],
        "has_more": has_more,
    }


@app.get("/chat/latest")
def chat_latest_api(authorization: str | None = Header(default=None), limit: int = Query(100, ge=1, le=200)):
    """The conversation with the newest message, with its latest messages: what Talk opens on. One owner-scoped read of the newest message first."""
    user = get_authenticated_user(authorization)
    user_id = str(user.id)
    try:
        newest = (supabase.table("chat_messages").select("conversation_id").eq("user_id", user_id)
                  .order("created_at", desc=True).limit(1).execute().data or [])
        if not newest:
            return {"status": "success", "conversation": None, "messages": [], "has_more": False}
        conversation_id = str(newest[0]["conversation_id"])
        conv = (supabase.table("chat_conversations").select("id,title,created_at,updated_at")
                .eq("id", conversation_id).eq("user_id", user_id).limit(1).execute().data or [])
    except Exception as error:  # noqa: BLE001
        from logging_util import logger
        logger.error(component="CHAT", operation="chat_latest", error=error, user_id=user_id, fallback_action="degraded")
        return {"status": "success", "conversation": None, "messages": [], "has_more": False, "degraded": True}
    payload = _conversation_messages(user_id, conversation_id, limit)
    payload["conversation"] = conv[0] if conv else {"id": conversation_id, "title": None}
    payload.pop("conversation_id", None)
    return payload

@app.get("/profile")
def profile_api(authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    sync_profile_from_auth(user)
    try:
        rows = supabase.table("profiles").select("*").eq("id", str(user.id)).limit(1).execute().data or []
    except Exception:
        rows=[]
    meta = getattr(user, "user_metadata", {}) or {}
    return {"profile": rows[0] if rows else {"id":str(user.id), "display_name": meta.get("display_name") or meta.get("full_name") or meta.get("name")}}

@app.post("/personalization/overview")
def personalization_api(authorization: str | None = Header(default=None)):
    user=get_authenticated_user(authorization)
    context=build_user_context(str(user.id),"personalization")
    return build_personalization(context.get("profile"),context.get("preferences"),context.get("recent_events"))

# --------------------------------------------------
# BATCHES 34–45 INTELLIGENCE SURFACES
# --------------------------------------------------

@app.post("/intelligence/all", response_model=SuccessResponse)
def intelligence_all(authorization: str | None = Header(default=None), days: int = Query(30, ge=1, le=365)):
    user=get_authenticated_user(authorization)
    events=_get_user_health_events(str(user.id), days)
    context=build_user_context(str(user.id),"health overview")
    profile=context.get("profile") or {}
    return {"status":"success",
        "personalization":build_personalization(profile,context.get("preferences"),events),
        "habits":analyze_habits(events,days),
        "mental_wellness":assess_wellbeing(events),
        "social":analyze_social_context(events),
        "womens_health":classify_womens_health(events),
        "medications":medication_overview(events),
        "preventive":preventive_snapshot(profile,events),
    }

@app.post("/sharing/plan")
def sharing_plan(request: dict, authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization)
    return build_share_plan(request.get("scopes") or [], request.get("consent") or {})

@app.get("/production/readiness")
def production_readiness(authorization: str | None = Header(default=None)):
    require_admin(get_authenticated_user(authorization))  # operational data: administrators only (BUBBLES_ADMIN_USER_IDS)
    return readiness_report()

@app.get("/knowledge/health")
def knowledge_health_api(authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization)
    try:
        rows=supabase.table("rag_documents").select("publication_date,retrieved_at,source_name").limit(500).execute().data or []
    except Exception:
        rows=[]
    return knowledge_health(rows)

@app.post("/interop/fhir/event")
def interop_fhir(request: dict, authorization: str | None = Header(default=None)):
    user=get_authenticated_user(authorization)
    event=dict(request.get("event") or {})
    event["user_id"]=str(user.id)
    return to_fhir_resource(event)

@app.get("/models/registry")
def models_registry(authorization: str | None = Header(default=None)):
    require_admin(get_authenticated_user(authorization))  # operational data: administrators only (BUBBLES_ADMIN_USER_IDS)
    from ai_orchestrator import PRICES
    return {
        "providers": sorted({price.provider for price in PRICES.values()} | {"NVIDIA"}),
        "routing":"policy-driven",
        "health_data_keyless_default":False,
        "paid_models_default":False,
        "contract":model_contract("reasoning","configured_secure_provider","configured"),
        "pricing": [
            {"provider":p.provider,"model":p.model,"input_per_million":p.input_per_million,
             "output_per_million":p.output_per_million,"cached_input_per_million":p.cached_input_per_million,
             "effective_date":p.effective_date,"source":p.source}
            for p in sorted(PRICES.values(), key=lambda x:(x.provider,x.model))
        ],
        "model_selection_note":"configured provider policy decides runtime model; safety paths remain deterministic; unknown provider pricing is represented as unknown rather than zero."
    }

# --------------------------------------------------
# LONGITUDINAL PATTERNS + WEEKLY INSIGHTS
# --------------------------------------------------

class PatternAnalysisRequest(BaseModel):
    days: int = 30
@app.post("/security/validate-token")
def validate_token(authorization: str | None = Header(default=None)):
    """Validate that a provided token is valid and return user info."""
    user = get_authenticated_user(authorization)
    return {"status": "success", "user_id": str(user.id), "email": user.email or ""}
@app.get("/security/scopes")
def security_scopes(authorization: str | None = Header(default=None)):
    """Return security-related scopes for the authenticated user."""
    user = get_authenticated_user(authorization)
    return {"status": "success", "user_id": str(user.id), "scopes": []}


def _fitness_text(user_id: str, message: str) -> str:
    """Deterministic Fitness answer for chat (no model). Never raises."""
    try:
        from fitness_chat import reply as fitness_reply
        return fitness_reply(supabase, user_id, message)
    except Exception as error:  # noqa: BLE001
        from logging_util import logger
        logger.warning(component="FITNESS_CHAT", operation="reply", error=error, fallback_action="generic_reply")
        return "I couldn't look that up right now. You can find it under Fitness in the menu."


def _get_user_health_events(user_id: str, days: int = 30) -> list[dict]:
    days = max(1, min(days, 730))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        result = (
            supabase
            .table("extracted_health_events")
            .select("id, event_type, extracted_data, confidence, created_at, user_confirmed, extraction_status")
            .eq("user_id", user_id)
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(1000)
            .execute()
        )
        rows = list(result.data or [])
        # Analytics date events by created_at (when they were recorded). A log written about yesterday carries its own
        # date, so use that as the event's moment and keep the recording time as ingested_at.
        for row in rows:
            try:
                moment = event_moment(row)
                if moment and row.get("created_at") and moment.isoformat() != row["created_at"]:
                    row["ingested_at"] = row["created_at"]
                    row["created_at"] = moment.isoformat()
            except Exception:
                continue
        return rows
    except Exception as error:
        from logging_util import logger
        logger.error(
            component="HEALTH_EVENT",
            operation="get_user_health_events",
            error=error,
            user_id=user_id,
            context={"days": days, "cutoff": cutoff},
            fallback_action="returning_empty_events",
        )
        return []


@app.get("/insights/weekly", response_model=WeeklyInsightsResponse)
def weekly_insights(
    authorization: str | None = Header(default=None),
):
    user = get_authenticated_user(authorization)
    events = _get_user_health_events(str(user.id), days=30)
    insights_data = build_weekly_insights(events)
    return WeeklyInsightsResponse(insights=WeeklyInsightsData(**weekly_insights_response_shape(insights_data)))


@app.post("/patterns/analyze")
def pattern_analysis(
    request: PatternAnalysisRequest,
    authorization: str | None = Header(default=None),
):
    user = get_authenticated_user(authorization)
    days = max(1, min(request.days, 365))
    events = _get_user_health_events(str(user.id), days=days)
    return {
        "status": "success",
        "analysis": analyze_patterns(events, days=days),
    }


# --------------------------------------------------
# RAG SEARCH
# --------------------------------------------------

class RAGSearchRequest(BaseModel):
    query: str
    topic: str | None = None
    country: str | None = None
    limit: int = 8


@app.post("/rag/search")
def rag_search(
    request: RAGSearchRequest,
    authorization: str | None = Header(default=None),
):
    user = get_authenticated_user(authorization)
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    results = hybrid_search(
        query=request.query,
        user_id=str(user.id),
        topic=request.topic,
        country=request.country,
        limit=request.limit,
    )
    return {"status": "success", "results": results}


# --------------------------------------------------
# HEALTH EVENT CONFIRMATION
# --------------------------------------------------

# --------------------------------------------------
# MEMORY PROMOTION
# --------------------------------------------------

@app.post("/memory/promote")
def promote_memory(
    request: MemoryPromotionRequest,
    authorization: str | None = Header(default=None)
):

    user = get_authenticated_user(authorization)

    from logging_util import logger
    logger.info(
        component="MEMORY",
        operation="memory_promote_request",
        user_id=user.id,
        context={"event_id": request.event_id},
    )

    # Verify that this event actually belongs to this user.
    event_result = (
        supabase
        .table("extracted_health_events")
        .select(
            "id, user_id, event_type, extracted_data, "
            "confidence, user_confirmed, extraction_status"
        )
        .eq("id", request.event_id)
        .eq("user_id", user.id)
        .limit(1)
        .execute()
    )

    if not event_result.data:
        raise HTTPException(
            status_code=404,
            detail="Health event not found"
        )

    event = event_result.data[0]
    if (event.get("extraction_status") or "pending") in DEAD_STATUSES:
        raise HTTPException(status_code=409, detail="This event was rejected or retracted and cannot be promoted")

    result = promote_health_event(
        user_id=str(user.id),
        event_id=str(event["id"]),
        event_type=event["event_type"],
        extracted_data=event["extracted_data"] or {},
        confidence=float(event["confidence"] or 0),
        user_confirmed=bool(event["user_confirmed"]),
        extraction_status=event.get("extraction_status"),
    )

    return {
        "status": "success",
        "promotion": result
    }

# --------------------------------------------------
# RL / PERSONALIZATION
# --------------------------------------------------

class RLRecommendationRequest(BaseModel):
    safety_level: str = "GREEN"
    context: dict[str, float] | None = None


class RLFeedbackRequest(BaseModel):
    interaction_id: str
    feedback: str
    reward: float | None = None


@app.post("/rl/recommendation")
def rl_recommendation(
    request: RLRecommendationRequest,
    authorization: str | None = Header(default=None),
):
    user = get_authenticated_user(authorization)

    from rl.service import choose_recommendation

    result = choose_recommendation(
        user_id=str(user.id),
        safety_level=request.safety_level.upper(),
        context=request.context,
    )
    return {
        "status": "success",
        "recommendation": result,
    }


@app.post("/rl/feedback")
def rl_feedback(
    request: RLFeedbackRequest,
    authorization: str | None = Header(default=None),
):
    user = get_authenticated_user(authorization)

    from rl.service import record_feedback

    try:
        result = record_feedback(
            user_id=str(user.id),
            interaction_id=request.interaction_id,
            feedback=request.feedback,
            reward=request.reward,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "status": "success",
        "feedback": result,
    }

# --------------------------------------------------
# NUTRITION + MENSTRUAL INTELLIGENCE
# --------------------------------------------------
from nutrition_intelligence import analyze as analyze_nutrition, analyze_flat as analyze_nutrition_flat
from cycle_intelligence import analyze as _analyze_cycle_raw


def analyze_cycle(events):
    """Adapt analyzer output to CycleIntelligenceData (symptoms list, data_quality dict)."""
    out = _analyze_cycle_raw(events)
    out["symptoms"] = out["symptoms"]["recent_unique"]
    out["data_quality"] = {"note": out["data_quality"], "period_starts_logged": out["cycle"]["period_start_count"]}
    return out


class IntelligenceRequest(BaseModel):
    days: int = 90

class CompanionRequest(BaseModel):
    days: int = 14

class LearningRequest(BaseModel):
    days: int = 90


def _bounded_events(user_id: str, days: int) -> list[dict]:
    # Keep retrieval bounded and deterministic; the source table remains the existing event store.
    result = _get_user_health_events(user_id, days=max(1, min(days, 365)))
    # Defensive: ensure result is always list[dict], never string or other type
    if not isinstance(result, list):
        from logging_util import logger
        logger.warning(
            component="INTELLIGENCE",
            operation="bounded_events",
            user_id=user_id,
            message=f"Returned non-list type: {type(result)}, value: {str(result)[:100]}",
            context={"received_type": type(result).__name__, "input_days": days},
            fallback_action="returning_empty_list",
        )
        return []
    return result


@app.get("/intelligence/nutrition", response_model=NutritionIntelligenceResponse)
def nutrition_intelligence(authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    return NutritionIntelligenceResponse(nutrition=NutritionSummaryData(**analyze_nutrition_flat(_bounded_events(str(user.id), 30))))


@app.get("/intelligence/cycle", response_model=CycleIntelligenceResponse)
def cycle_intelligence(authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    return CycleIntelligenceResponse(cycle=CycleIntelligenceData(**analyze_cycle(_bounded_events(str(user.id), 365))))


@app.post("/intelligence/overview", response_model=IntelligenceOverviewResponse)
def intelligence_overview(request: IntelligenceRequest, authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    events = _bounded_events(str(user.id), request.days)
    return IntelligenceOverviewResponse(
        nutrition=NutritionSummaryData(**analyze_nutrition_flat(events)),
        cycle=CycleIntelligenceData(**analyze_cycle(events)),
    )


@app.post("/intelligence/state", response_model=HealthStateResponse)
def intelligence_state(request: IntelligenceRequest, authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    days = max(1, min(request.days, 90))
    events = _bounded_events(str(user.id), days * 2)
    state = build_health_state(events, days=days)
    normalized = normalize_health_state(state)
    return HealthStateResponse(state=HealthStateData(**normalized))



class InteractionRequest(BaseModel):
    days: int = Field(default=14, ge=1, le=90)


@app.post("/intelligence/brief", response_model=IntelligenceBriefResponse)
def intelligence_brief(
    request: InteractionRequest,
    authorization: str | None = Header(default=None),
):
    """Single bounded read model for the dashboard command layer.

    It combines state, learning, companion context and adaptive actions so the
    frontend does not fan out into several overlapping intelligence requests.
    """
    user = get_authenticated_user(authorization)
    days = max(1, min(request.days, 90))
    user_id = str(user.id)
    events = _bounded_events(user_id, days * 2)
    state = build_health_state(events, days=days)
    learning = build_learning_snapshot(events, days=min(days * 3, 90))
    companion = build_daily_companion(state, learning)

    normalized_state = normalize_health_state(state)

    gaps = list(normalized_state.get("data_gaps", {}).get("gaps", []))
    actions = []
    seen = set()

    def add(action_id: str, title: str, detail: str, target: str, priority: str = "normal"):
        if action_id not in seen:
            seen.add(action_id)
            actions.append({
                "id": action_id,
                "title": title,
                "detail": detail,
                "target": target,
                "priority": priority,
            })

    gap_text = " ".join(gaps).lower()
    if not events:
        add("start-signal", "Give Bubbles one signal", "Log one sleep, hydration, mood, movement, or symptom observation.", "companion", "high")
    else:
        if "sleep" in gap_text:
            add("log-sleep", "Log last night's sleep", "Build recovery context from an observed sleep entry.", "activity")
        if "hydration" in gap_text or "water" in gap_text:
            add("log-hydration", "Log hydration", "Improve hydration coverage instead of making assumptions.", "dashboard")
        if "activity" in gap_text or "exercise" in gap_text:
            add("log-movement", "Log movement", "Connect today's movement with recovery and fitness context.", "activity")
        if "cycle" in gap_text or "menstrual" in gap_text:
            add("log-cycle", "Add cycle context", "A cycle observation can improve women's-health context.", "health")

    for metric, deviation in list((normalized_state.get("deviations") or {}).items())[:2]:
        if isinstance(deviation, dict) and isinstance(deviation.get("delta"), (int, float)):
            add(
                f"review-{metric}",
                f"Review {plain_metric(metric)}",
                f"Your {plain_metric(metric)} moved compared with your usual. Open it to see the entries behind it.",
                "intelligence",
                "high",
            )

    add("ask-bubbles", "Ask Bubbles what changed", "Review recent evidence, uncertainty, and the next useful tracking step.", "companion")
    return IntelligenceBriefResponse(
        brief=IntelligenceBriefData(
            generated_at=datetime.now(timezone.utc).isoformat(),
            window_days=days,
            state=normalized_state,
            learning=learning,
            companion=companion,
            actions=actions[:6],
        )
    )


@app.get("/intelligence/living-map", response_model=LivingSignalMapResponse)
def living_signal_map(authorization: str | None = Header(default=None), days: int = Query(default=14, ge=1, le=90)):
    user = get_authenticated_user(authorization)
    events = _bounded_events(str(user.id), days * 2)
    state_payload = build_health_state(events, days=days)
    analysis = analyze_longitudinal(events, days=days)
    correlations = analysis.get("correlations", []) if isinstance(analysis, dict) else []
    map_data = build_living_signal_map(state_payload, correlations=correlations)
    normalized_map = normalize_living_signal_map(map_data)
    return LivingSignalMapResponse(window_days=days, map=LivingSignalMapData(**normalized_map))


@app.post("/intelligence/next-actions", response_model=SuccessResponse)
def intelligence_next_actions(
    request: InteractionRequest,
    authorization: str | None = Header(default=None),
):
    """Resolve the smallest useful next actions from observed state.

    This is deterministic orchestration: it does not diagnose or invent missing
    health data. Actions are based only on observed event coverage and gaps.
    """
    user = get_authenticated_user(authorization)
    days = max(1, min(request.days, 90))
    events = _bounded_events(str(user.id), days * 2)
    state = build_health_state(events, days=days)
    gaps = list(state.get("data_gaps") or [])
    deviations = state.get("deviations") or {}

    actions: list[dict] = []
    seen: set[str] = set()

    def add(action_id: str, title: str, detail: str, target: str, priority: str = "normal"):
        if action_id in seen:
            return
        seen.add(action_id)
        actions.append({
            "id": action_id,
            "title": title,
            "detail": detail,
            "target": target,
            "priority": priority,
        })

    gap_text = " ".join(gaps).lower()
    if not events:
        add("start-signal", "Give Bubbles one signal", "Log sleep, hydration, mood, movement, or a symptom to establish your first personal baseline.", "companion", "high")
    else:
        if "sleep" in gap_text:
            add("log-sleep", "Log last night's sleep", "A single sleep observation helps Bubbles build recovery context.", "activity")
        if "hydration" in gap_text or "water" in gap_text:
            add("log-hydration", "Log hydration", "Hydration coverage is currently sparse, so Bubbles will avoid guessing about it.", "dashboard")
        if "activity" in gap_text or "exercise" in gap_text:
            add("log-movement", "Log movement", "Add today's movement or exercise so recovery and fitness context can connect.", "activity")
        if "cycle" in gap_text or "menstrual" in gap_text:
            add("log-cycle", "Add cycle context", "A period start or cycle observation can improve women's-health context.", "health")

    for metric, deviation in list(deviations.items())[:2]:
        if isinstance(deviation, dict):
            delta = deviation.get("delta")
            if isinstance(delta, (int, float)) and abs(delta) > 0:
                add(
                    f"review-{metric}",
                    f"Review {plain_metric(metric)}",
                    f"Your {plain_metric(metric)} moved compared with your usual. Look at the entries behind it before drawing any conclusion.",
                    "intelligence",
                    "high" if abs(delta) >= 1 else "normal",
                )

    add("ask-bubbles", "Ask Bubbles what changed", "Bubbles can explain the recent evidence, uncertainty, and useful next tracking step.", "companion")
    return {"status": "success", "window_days": days, "actions": actions[:6], "state": state}


@app.post("/intelligence/learning", response_model=IntelligenceBriefResponse)
def intelligence_learning(request: LearningRequest, authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    days = max(1, min(request.days, 365))
    events = _bounded_events(str(user.id), days)
    learning_data = build_learning_snapshot(events, days=days)
    return IntelligenceBriefResponse(
        brief=IntelligenceBriefData(
            generated_at=datetime.now(timezone.utc).isoformat(),
            window_days=days,
            learning=learning_data,
        )
    )

@app.post("/companion/daily", response_model=DailyCompanionResponse)
def companion_daily(request: CompanionRequest, authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    days = max(1, min(request.days, 30))
    events = _bounded_events(str(user.id), days * 2)
    state = build_health_state(events, days=days)
    normalized_state = normalize_health_state(state)
    learning = build_learning_snapshot(events, days=min(days * 3, 90))
    companion = build_daily_companion(normalized_state, learning)
    return DailyCompanionResponse(companion=CompanionData(**companion), state=HealthStateData(**normalized_state))



# BUBBLES INTELLIGENCE — BATCHES 15-18
class FoodSearchRequest(BaseModel):
    query: str
    limit: int = 10
class IntelligenceWindowRequest(BaseModel):
    days: int = 30

@app.post("/memory/knowledge-graph")
def memory_knowledge_graph(request: IntelligenceWindowRequest, authorization: str | None = Header(default=None)):
    user=get_authenticated_user(authorization); days=max(1,min(request.days,365)); events=_bounded_events(str(user.id),days)
    return {"status":"success","graph":build_knowledge_graph(events,days=days),"memory_candidates":memory_candidates(events)}

@app.post("/nutrition/food-search")
def nutrition_food_search(request: FoodSearchRequest, authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization); return {"status":"success","results":search_foods(request.query,request.limit)}

@app.post("/nutrition/food-lookup")
def nutrition_food_lookup(request: FoodSearchRequest, authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization); return {"status":"success","food":lookup_food(request.query)}

@app.post("/cycle/advanced")
def cycle_advanced(request: IntelligenceWindowRequest, authorization: str | None = Header(default=None)):
    user=get_authenticated_user(authorization); days=max(1,min(request.days,3650)); return {"status":"success","analysis":analyze_cycle_advanced(_bounded_events(str(user.id),days))}

@app.post("/fitness/analysis")
def fitness_analysis(request: IntelligenceWindowRequest, authorization: str | None = Header(default=None)):
    user=get_authenticated_user(authorization); days=max(1,min(request.days,365)); return {"status":"success","analysis":analyze_fitness(_bounded_events(str(user.id),days),days=days)}

@app.post("/bubbles/intelligence")
def bubbles_intelligence(request: IntelligenceWindowRequest, authorization: str | None = Header(default=None)):
    user=get_authenticated_user(authorization); days=max(1,min(request.days,365)); events=_bounded_events(str(user.id),days)
    return {"status":"success","state":build_health_state(events,days=min(days,90)),"learning":build_learning_snapshot(events,days=days),
            "memory_graph":build_knowledge_graph(events,days=days),"memory_candidates":memory_candidates(events),
            "cycle":analyze_cycle_advanced(events),"fitness":analyze_fitness(events,days=days)}


# ============================================================
# BATCHES 19-25 — DEEP HEALTH INTELLIGENCE
# ============================================================

class WindowRequest(BaseModel):
    days: int = 90

class VisitRequest(BaseModel):
    days: int = 365
    concern: str | None = None

class MedicalSummaryRequest(BaseModel):
    days: int = 365

class EscalationRequest(BaseModel):
    message: str
    context: dict | None = None

class AIRouteRequest(BaseModel):
    task: str = "chat"
    sensitivity: str = "health"
    safety_level: str = "GREEN"
    input_tokens: int = 0
    output_tokens: int = 0
    budget_remaining_usd: float | None = None
    model: str | None = None

class RedactionRequest(BaseModel):
    text: str

class ConsentRequest(BaseModel):
    purpose: str
    consent: dict = Field(default_factory=dict)

@app.get("/intelligence/sleep-recovery")
def sleep_recovery_intelligence(days: int = Query(default=30, ge=7, le=365), authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    days = max(7, min(days, 365))
    return {"status":"success","analysis":analyze_sleep_recovery(_bounded_events(str(user.id), days), days=days)}

@app.post("/intelligence/longitudinal")
def longitudinal_intelligence(request: WindowRequest, authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    days = max(7, min(request.days, 730))
    return {"status":"success","analysis":analyze_longitudinal(_bounded_events(str(user.id), days), days=days)}

def _safe_table_rows(table: str, user_id: str, limit: int = 200) -> list[dict]:
    try:
        result = (supabase.table(table).select("*").eq("user_id", user_id)
                  .order("created_at", desc=True).limit(max(1,min(limit,500))).execute())
        return list(result.data or [])
    except Exception as error:
        from logging_util import logger
        logger.warning(
            component="MEDICAL",
            operation="table_retrieval",
            message=f"{table} retrieval failed",
            user_id=user_id,
            context={"table": table, "error_type": type(error).__name__},
        )
        return []

@app.post("/medical/summary")
def medical_summary(request: MedicalSummaryRequest, authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    uid = str(user.id)
    records = _safe_table_rows("medical_reports", uid)
    labs = _safe_table_rows("lab_results", uid)
    reports = records
    return {"status":"success","summary":summarize_medical_records(records,labs,reports),"questions":medical_questions(records,labs)}

@app.post("/doctor/timeline")
def doctor_health_timeline(request: VisitRequest, authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    return {"status":"success","timeline":build_timeline(_bounded_events(str(user.id), max(7,min(request.days,730))))}

@app.post("/doctor/prepare")
def doctor_visit_prepare(request: VisitRequest, authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    events = _bounded_events(str(user.id), max(7,min(request.days,730)))
    return {"status":"success","visit":prepare_visit(events, request.concern)}

@app.post("/safety/escalate")
def safety_escalate(request: EscalationRequest, authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization)
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    return {"status":"success","safety":evaluate_escalation(request.message,request.context)}

@app.get("/ai/telemetry", response_model=AITelemetryResponse)
def ai_telemetry(authorization: str | None = Header(default=None)):
    require_admin(get_authenticated_user(authorization))  # operational data: administrators only (BUBBLES_ADMIN_USER_IDS)
    telemetry_data = ai_telemetry_snapshot()
    return AITelemetryResponse(telemetry=AITelemetryData(**telemetry_data))

@app.post("/ai/route")
def ai_route(request: AIRouteRequest, authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization)
    route = route_ai(request.safety_level, request.sensitivity, request.task, request.budget_remaining_usd)
    budget = build_budget(request.input_tokens,request.output_tokens,route.provider, request.model or "configured")
    return {"status":"success","route":route.__dict__,"budget":budget}

@app.post("/privacy/redact")
def privacy_redact(request: RedactionRequest, authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization)
    return {"status":"success","redacted":redact(request.text)}

@app.post("/privacy/consent/check")
def privacy_consent(request: ConsentRequest, authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization)
    return {"status":"success","policy":consent_policy(request.consent,request.purpose)}

@app.get("/privacy/security-baseline")
def privacy_security_baseline(authorization: str | None = Header(default=None)):
    require_admin(get_authenticated_user(authorization))  # operational data: administrators only (BUBBLES_ADMIN_USER_IDS)
    return {"status":"success","security":threat_check()}

class MediaMetadataRequest(BaseModel):
    media_type: str
    filename: str | None = None
    size_bytes: int | None = None

class EvidenceRequest(BaseModel):
    question: str
    evidence: list[dict] = Field(default_factory=list)

class InterventionRequest(BaseModel):
    safety_level: str = "GREEN"
    history: list[dict] = Field(default_factory=list)

class EvaluationRequest(BaseModel):
    case: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)

class TwinRequest(BaseModel):
    days: int = 90

class AgentRequest(BaseModel):
    days: int = 90
    safety_level: str = "GREEN"
    autonomy: str = "suggest"

@app.get("/intelligence/body-systems")
def body_system_intelligence(days: int = Query(default=90, ge=7, le=730), authorization: str | None = Header(default=None)):
    user=get_authenticated_user(authorization)
    return {"status":"success","intelligence":build_body_system_intelligence(_bounded_events(str(user.id),max(7,min(days,730))))}

@app.post("/evidence/grounding")
def evidence_grounding(request: EvidenceRequest, authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization)
    return {"status":"success","packet":build_grounding_packet(request.question, request.evidence)}

@app.post("/interventions/select")
def intervention_select(request: InterventionRequest, authorization: str | None = Header(default=None)):
    user=get_authenticated_user(authorization)
    state=build_health_state(_bounded_events(str(user.id),14),days=14)
    return {"status":"success","plan":select_interventions(state,request.safety_level,request.history)}

@app.post("/interoperability/fhir-bundle")
def fhir_bundle(request: WindowRequest, authorization: str | None = Header(default=None)):
    user=get_authenticated_user(authorization)
    events=_bounded_events(str(user.id),max(7,min(request.days,730)))
    return {"status":"success","bundle":export_bundle(events)}

@app.post("/evaluation/case")
def evaluation_case(request: EvaluationRequest, authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization)
    return {"status":"success","evaluation":evaluate_case(request.case,request.result)}

@app.get("/evaluation/baseline")
def evaluation_baseline(authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization)
    return {"status":"success","release_gate":release_gate([]),"example_audit":model_audit("configured","unknown")}

@app.post("/multimodal/metadata")
def multimodal_metadata(request: MediaMetadataRequest, authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization)
    return {"status":"success","media":inspect_media_metadata(request.media_type,request.filename,request.size_bytes)}

@app.get("/multimodal/voice-policy")
def multimodal_voice_policy(authorization: str | None = Header(default=None)):
    get_authenticated_user(authorization)
    return {"status":"success","policy":voice_session_policy()}

@app.post("/intelligence/digital-twin")
def digital_twin(request: TwinRequest, authorization: str | None = Header(default=None)):
    user=get_authenticated_user(authorization); days=max(7,min(request.days,730)); events=_bounded_events(str(user.id),days)
    state=build_health_state(events,days=min(days,90)); longitudinal=analyze_longitudinal(events,days=days)
    return {"status":"success","twin":build_digital_twin(state,longitudinal)}

@app.post("/agent/plan")
def agent_plan(request: AgentRequest, authorization: str | None = Header(default=None)):
    user=get_authenticated_user(authorization); days=max(7,min(request.days,730)); events=_bounded_events(str(user.id),days)
    state=build_health_state(events,days=min(days,90)); longitudinal=analyze_longitudinal(events,days=days)
    twin=build_digital_twin(state,longitudinal)
    return {"status":"success","agent":plan_agent_actions(twin,request.safety_level,request.autonomy)}

@app.get("/intelligence/deep")
def deep_intelligence(days: int = Query(default=90, ge=7, le=730), authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    days=max(7,min(days,730))
    events=_bounded_events(str(user.id),days)
    sleep=analyze_sleep_recovery(events,days=min(days,365))
    longitudinal=analyze_longitudinal(events,days=days)
    cycle=analyze_cycle_advanced(events)
    fitness=analyze_fitness(events,days=min(days,365))
    state=build_health_state(events,days=min(days,90))
    body=build_body_system_intelligence(events)
    twin=build_digital_twin(state,longitudinal)
    interventions=select_interventions(state,"GREEN")
    agent=plan_agent_actions(twin,"GREEN","suggest")
    return {"status":"success","window_days":days,"state":state,"sleep_recovery":sleep,
            "longitudinal":longitudinal,"cycle":cycle,"fitness":fitness,"body_systems":body,
            "digital_twin":twin,"interventions":interventions,"agent":agent,
            "safety":{"policy":"deterministic safety engine remains authoritative"}}
