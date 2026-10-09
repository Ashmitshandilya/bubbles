import os

import env_compat  # noqa: F401  (loads .env and maps legacy COCO_* names to BUBBLES_*; must run before config is read)
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from time import perf_counter
from uuid import UUID

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from wellness_common import REQUEST_TZ, parse_tz_header
from fastapi.responses import JSONResponse
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
from memory_retrieval import get_relevant_memories, format_memory_context
from supabase_client import supabase
from bubbles_ai import BubblesAIResponse, ask_bubbles, is_degraded
from memory_promotion import promote_health_event
from rag import hybrid_search, build_evidence_context
from evidence_package import build_package, package_audit, plan_task
from health_event_pipeline import prepare_db_row
from health_event_projection import project_confirmed_event
from health_logs import build_router as build_health_logs_router
from fitness_api import build_router as build_fitness_router
from data_rights import build_router as build_data_rights_router
from wellness_api import build_router as build_wellness_router
from import_api import build_router as build_import_router
from cycle_api import build_router as build_cycle_router
from partner_sharing import build_router as build_partner_router
from context_engine import build_user_context, format_user_context
from safety_engine import assess_safety, safety_instruction
from chat_pipeline import (
    RateLimiter, ai_failed_reply, analyze_turn, build_rule_events, conversation_block, deterministic_reply,
    evidence_query, find_stored_reply, first_name, load_history, persist_events, reconcile_ai_events, reply_kind,
    safety_payload, semantic_trace, state_block, stored_metadata,
)
from conversation_correction import apply_correction, contradiction_note
from health_semantics import display_name
from event_filters import DEAD_STATUSES, event_moment
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

app = FastAPI(title="Bubbles API")
register_db_error_handlers(app)


@app.middleware("http")
async def bubbles_security_headers(request, call_next):
    # This is the innermost middleware. An exception that escapes it is turned into a 500 by Starlette's
    # outermost layer, which sits OUTSIDE CORS: the response then has no CORS headers and the browser reports
    # a network failure ("can't connect to the backend") although the server answered. Catching here keeps the
    # error readable, so the app can tell "server problem" from "server not running".
    tz_token = REQUEST_TZ.set(parse_tz_header(request.headers.get("x-tz-offset-minutes")))
    blocked = _guard_request(request)
    try:
        response = blocked if blocked is not None else await call_next(request)
    except Exception as error:  # noqa: BLE001
        from logging_util import logger
        logger.error(component="API", operation="unhandled_exception", error=error,
                     context={"path": request.url.path, "method": request.method, "error_class": type(error).__name__}, fallback_action="returning_json_500")
        if is_permission_denied(error):  # a permission error wrapped in some other exception type
            response = database_permission_response(error)
        else:
            response = JSONResponse(status_code=500, content={"detail": "Something went wrong on Bubbles' side. Please try again.", "code": "server_error"})
    REQUEST_TZ.reset(tz_token)
    for key, value in security_headers().items():
        response.headers[key] = value
    return response


# Coarse protection for the Whole-Health OS routes: a request-size cap and a per-user request budget (the chat has its own limiter).
_GUARDED_PREFIXES = ("/fitness", "/wellness", "/cycle", "/notifications", "/import", "/me/", "/profile/body", "/partner")
_MAX_BODY_BYTES = 1_500_000
_route_limiter = RateLimiter(limit=240, window=60.0)
_public_limiter = RateLimiter(limit=30, window=60.0)    # the unauthenticated partner link: slows token guessing


def _guard_request(request):
    path = request.url.path
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
    key = ("ip:" + (request.client.host if request.client else "?")) if (public or not auth) else "t:" + auth[-32:]
    if not (_public_limiter if public else _route_limiter).allow(key):
        return JSONResponse(status_code=429, content={"detail": "You're going a little fast. Please wait a moment and try again.", "code": "rate_limited"}, headers={"Retry-After": "30"})
    return None


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
    # Any loopback port is allowed too: when port 3000 is busy Next.js starts on 3001, and a browser on a
    # port that is not in the list above blocks every request, which looks exactly like a dead backend.
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d{2,5})?$",
    allow_credentials=True,
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


@app.get("/health", response_model=HealthCheckResponse)
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

def get_authenticated_user(authorization: str | None):

    if not authorization:
        raise missing_auth_header_response()

    if not authorization.startswith("Bearer "):
        raise invalid_auth_header_response()

    token = authorization.replace("Bearer ", "", 1).strip()

    if not token:
        raise invalid_token_response()

    try:
        response = supabase.auth.get_user(token)

        if not response.user:
            raise invalid_token_response()

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
app.include_router(build_import_router(get_authenticated_user, supabase))
# Cycle: calendar, daily log, predictions with ranges, modes, insights, report, partner view.
app.include_router(build_cycle_router(get_authenticated_user, supabase))
app.include_router(build_partner_router(get_authenticated_user, supabase))


# --------------------------------------------------
# IDENTITY + PERSONAL MEMORY
# --------------------------------------------------

_profile_sync_paused_until = 0.0


def sync_profile_from_auth(user):
    """Best-effort sync of explicit auth identity into the existing profiles table."""
    global _profile_sync_paused_until
    metadata = getattr(user, "user_metadata", {}) or {}
    name = (metadata.get("full_name") or metadata.get("name") or "").strip()
    if not name or perf_counter() < _profile_sync_paused_until:
        return
    try:
        existing = (supabase.table("profiles").select("display_name")
                    .eq("id", str(user.id)).limit(1).execute().data or [])
        current = (existing[0].get("display_name") or "").strip() if existing else ""
        if current:
            return
        supabase.table("profiles").upsert(
            {"id": str(user.id), "display_name": name},
            on_conflict="id",
        ).execute()
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
        existing = (supabase.table("chat_messages").select("id,conversation_id,role,content")
                    .eq("user_id", user_id).eq("client_message_id", client_message_id)
                    .limit(1).execute().data or [])
        if existing:
            prior = existing[0]
            if (str(prior.get("conversation_id")) != conversation_id
                    or prior.get("role") != role
                    or prior.get("content") != content):
                raise HTTPException(status_code=409, detail="Chat idempotency key was already used for different content")
            return out(str(prior["id"]), False)
    try:
        saved = supabase.table("chat_messages").insert(payload).select("id").execute()
    except Exception as error:
        # A concurrent retry can win the unique idempotency race. Resolve it by
        # reading the winner rather than creating a second logical message.
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


def _debug_trace_enabled() -> bool:
    return os.getenv("BUBBLES_DEBUG_TRACE", "false").strip().lower() in {"1", "true", "yes"}


def _reasons_text(reasons: list[str]) -> list[str]:
    return [str(r) for r in reasons][:8]


@app.post("/chat")
def chat(
    request: ChatRequest,
    authorization: str | None = Header(default=None)
):
    user = get_authenticated_user(authorization)
    user_id = str(user.id)
    if not _chat_limiter.allow(user_id):
        raise HTTPException(status_code=429, detail="You're sending messages very quickly. Please wait a moment and try again.")

    sync_profile_from_auth(user)
    user_message = request.message.strip()
    conversation_id = _ensure_conversation(user_id, request.conversation_id, user_message or "Bubbles conversation")

    if not user_message:
        response_text = "I'm here 💗 Tell me what's on your mind."
        empty_safety = {"level": "GREEN", "state": "NO_REDFLAG", "reasons": [], "retracted": False}
        bubbles_message_id = _persist_chat_message(
            user_id=user_id, conversation_id=conversation_id, role="bubbles", content=response_text,
            metadata={"source": "bubbles_api", "kind": "reply", "safety": empty_safety},
        )
        _touch_conversation(conversation_id, user_id)
        return {
            "response": response_text,
            "sentiment": "neutral",
            "kind": "reply",
            "safety": empty_safety,
            "health_events": [],
            "health_event_ids": [],
            "message_id": bubbles_message_id,
            "conversation_id": conversation_id,
            "user_message_id": None,
            "user_id": user.id,
        }

    # Recent turns of THIS conversation (owner-scoped) give the message its antecedent: "I said no chest pain?"
    # is meaningless without what was said before. Read before saving the new message.
    history = load_history(supabase, user_id, conversation_id)
    user_message_id, created = _persist_chat_message(
        user_id=user_id, conversation_id=conversation_id, role="user", content=user_message,
        metadata={"source": "user_input"}, client_message_id=request.message_id, return_created=True,
    )
    if not created:
        # A retry of a message we already answered: return the stored answer instead of re-running the model
        # and duplicating events.
        replay = find_stored_reply(supabase, user_id, conversation_id, user_message_id)
        if replay:
            replay["user_id"] = user.id
            return replay
    # Keep health content out of application logs; operational telemetry records only safe metadata.

    explicit_facts = extract_explicit_personal_facts(user_message)
    memory_saved = persist_explicit_facts(user_id, user_message_id, explicit_facts)

    # ---- 1. understand: facts (negation, tense, who, severity), safety state, correction, contradictions, daily log
    turn = analyze_turn(user_message, history)
    safety = turn.safety
    name = first_name(user)
    timings = dict(turn.timings_ms)
    rule_events = [] if turn.route == "correction" else build_rule_events(turn, user_message_id)
    if turn.pause_strict_plan:   # restriction language arrived with an urgent/uncertain safety state: the safety reply wins, the plan still pauses
        try:
            from fitness_chat import pause_active_plan
            pause_active_plan(supabase, user_id)
        except Exception:  # noqa: BLE001
            pass

    # ---- 2. respond
    ai_events: list = []
    evidence_results: list[dict] = []
    package_audit_meta: dict | None = None
    sentiment = "neutral"
    persisted: list[dict] = []
    if turn.route in {"emergency", "correction", "clarification", "daily_log", "fitness_support", "fitness_answer"}:
        # Deterministic copy: RED is a hard gate, so neither the message nor health context reaches a provider.
        t0 = perf_counter()
        persisted = persist_events(supabase, user_id, user_message_id, rule_events)
        timings["events_ms"] = round((perf_counter() - t0) * 1000, 1)
        response_text = deterministic_reply(turn, name=name, saved_events=sum(1 for e in persisted if e["id"]))
        if turn.route in {"fitness_support", "fitness_answer"}:
            response_text = _fitness_text(user_id, user_message)
    else:
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

        # Evidence is retrieved only after the safety gate, and only for topics the user actually raised
        # (never for denied or other people's symptoms).
        query = evidence_query(turn.facts, user_message)
        t0 = perf_counter()
        if query:
            try:
                evidence_results = hybrid_search(query=query, user_id=user_id, limit=6)
            except Exception as error:
                from logging_util import logger
                logger.error(component="RAG", operation="hybrid_search", error=error, user_id=user_id,
                             context={"query_length": len(query)}, fallback_action="using_empty_evidence")
                evidence_results = []
        timings["rag_ms"] = round((perf_counter() - t0) * 1000, 1)
        evidence_context = build_evidence_context(evidence_results)
        try:  # audit trail only for now: the model still receives the same context blocks
            package_audit_meta = package_audit(build_package(
                plan=plan_task(user_message, has_health_topic=bool(query)), safety=safety_payload(safety),
                personal_facts=[f.to_dict() for f in turn.facts if f.experiencer == "self"], evidence=evidence_results))
        except Exception as error:  # noqa: BLE001 - never let the audit trail break a reply
            from logging_util import logger
            logger.warning(component="CHAT", operation="evidence_package", error=error, fallback_action="no_audit_trail")

        recent_block = conversation_block(history)
        conversation_context = "\n\n".join(filter(None, [
            ("RECENT CONVERSATION (oldest first):\n" + recent_block) if recent_block else "",
            state_block(turn.facts, turn.history_facts),
        ]))
        t0 = perf_counter()
        ai_result = ask_bubbles(
            user_message,
            memory_context=memory_context,
            evidence_context=evidence_context,
            safety_context=safety_instruction(safety) + "\n\n" + response_style_instruction(),
            conversation_context=conversation_context,
        )
        timings["ai_ms"] = round((perf_counter() - t0) * 1000, 1)
        if is_degraded(ai_result):
            ai_events = []
        else:
            ai_events = ai_result.health_events
            sentiment = ai_result.sentiment

        # The model only PROPOSES events; the backend keeps those the user really asserted about themselves.
        t0 = perf_counter()
        reconciled = reconcile_ai_events(ai_events, turn, rule_events, user_message_id)
        persisted = persist_events(supabase, user_id, user_message_id, rule_events + reconciled)
        timings["events_ms"] = round((perf_counter() - t0) * 1000, 1)
        if is_degraded(ai_result):
            response_text = ai_failed_reply(turn, name=name, saved_events=sum(1 for e in persisted if e["id"]))
        else:
            response_text = normalize_response(ai_result.response)
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
    bubbles_message_id = _persist_chat_message(
        user_id=user_id, conversation_id=conversation_id, role="bubbles", content=response_text, metadata=metadata,
    )
    if turn.route == "correction":
        outcome = apply_correction(supabase, user_id=user_id, conversation_id=conversation_id, correction=turn.correction,
                                   correction_message_id=bubbles_message_id, history=history)
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
    _touch_conversation(conversation_id, user_id)

    from logging_util import logger
    logger.info(component="CHAT", operation="turn", user_id=user_id, context={
        "route": turn.route, "state": safety.state, "events": len(persisted), "timings_ms": timings,
        "concepts": list(safety.concepts)[:6],
    })

    payload = {
        "response": response_text,
        "memory_saved": memory_saved,
        "sentiment": sentiment,
        "kind": kind,
        "safety": safety_dict,
        "health_events": persisted,
        "health_event_ids": [e["id"] for e in persisted],
        "conflicts": turn.conflicts[:5],
        "message_id": bubbles_message_id,
        "user_message_id": user_message_id,
        "conversation_id": conversation_id,
        "user_id": user.id,
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
            for row in evidence_results
        ],
    }
    if _debug_trace_enabled():
        payload["debug"] = {"route": turn.route, "timings_ms": timings, "trace": semantic_trace(turn),
                            "facts": [f.to_dict(include_text=True) for f in turn.facts][:40]}
    return payload


# --------------------------------------------------
# PERSONAL MEMORY / PROFILE DIAGNOSTICS
# --------------------------------------------------

@app.get("/memory/diagnostics")
def memory_diagnostics_api(authorization: str | None = Header(default=None)):
    user = get_authenticated_user(authorization)
    return {"status":"success","memory":memory_diagnostics(str(user.id))}

@app.get("/chat/history")
def chat_history_api(authorization: str | None = Header(default=None), limit: int = Query(10, ge=1, le=50)):
    user = get_authenticated_user(authorization)
    user_id = str(user.id)
    try:
        # Get conversations with message count
        conversations = (supabase.table("chat_conversations")
                        .select("id,title,created_at,updated_at")
                        .eq("user_id", user_id)
                        .order("updated_at", desc=True)
                        .limit(limit)
                        .execute().data or [])

        # Get message count for each conversation
        for conv in conversations:
            msg_count = (supabase.table("chat_messages")
                        .select("id", count="exact")
                        .eq("conversation_id", conv["id"])
                        .execute().count or 0)
            conv["message_count"] = msg_count

        return {"conversations": conversations}
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
        return {"conversations": [], "degraded": True}

@app.get("/chat/conversations/{conversation_id}/messages")
def chat_conversation_messages_api(
    conversation_id: str,
    authorization: str | None = Header(default=None),
    limit: int = Query(100, ge=1, le=200),
):
    """Owner-scoped read of one conversation's latest messages, oldest first."""
    user = get_authenticated_user(authorization)
    user_id = str(user.id)
    # Same ownership gate as /chat: 400 for a malformed id, 404 for anyone else's conversation.
    _ensure_conversation(user_id, conversation_id, "")
    rows = (supabase.table("chat_messages")
            .select("id,role,content,created_at,metadata")
            .eq("conversation_id", conversation_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute().data or [])
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
        return out

    return {
        "status": "success",
        "conversation_id": conversation_id,
        "messages": [_message(row) for row in reversed(rows)],
    }

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
    get_authenticated_user(authorization)
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
    get_authenticated_user(authorization)
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

class HealthEventConfirmationRequest(BaseModel):
    confirmed: bool


@app.patch("/health-events/{event_id}/confirmation")
def confirm_health_event(
    event_id: str,
    request: HealthEventConfirmationRequest,
    authorization: str | None = Header(default=None),
):
    user = get_authenticated_user(authorization)
    if request.confirmed:
        # A rejected/retracted/superseded event (e.g. withdrawn by a correction) must not come back to life.
        current = (supabase.table("extracted_health_events").select("id, extraction_status")
                   .eq("id", event_id).eq("user_id", str(user.id)).limit(1).execute().data or [])
        if current and (current[0].get("extraction_status") or "pending") in DEAD_STATUSES:
            raise HTTPException(status_code=409, detail="This item was withdrawn and can no longer be saved.")
    try:
        result = (
            supabase.table("extracted_health_events")
            .update({
                "user_confirmed": request.confirmed,
                "extraction_status": "confirmed" if request.confirmed else "rejected",
            })
            .eq("id", event_id)
            .eq("user_id", str(user.id))
            .select("id, message_id, event_type, extracted_data, confidence, user_confirmed, extraction_status")
            .execute()
        )
    except Exception as error:
        from logging_util import logger
        logger.error(
            component="HEALTH_EVENT",
            operation="confirm_health_event",
            error=error,
            user_id=str(user.id),
            context={"event_id": event_id, "confirmed": request.confirmed},
            fallback_action="raising_http_exception",
        )
        raise HTTPException(status_code=500, detail="Unable to update health event") from error
    if not result.data:
        raise HTTPException(status_code=404, detail="Health event not found")

    event = result.data[0]
    projection = None
    if request.confirmed:
        try:
            projection = project_confirmed_event(
                db=supabase,
                user_id=str(user.id),
                event_id=str(event["id"]),
                event_type=str(event["event_type"]),
                extracted_data=event.get("extracted_data") or {},
                confidence=float(event.get("confidence") or 0),
                message_id=event.get("message_id"),
            )
        except Exception as error:
            if is_permission_denied(error):
                # The canonical tables are not writable yet (database permissions not applied). The confirmation is
                # stored on the event itself, and every analytics reader uses that table, so nothing is lost; say
                # plainly that the canonical copy is pending instead of failing the user's click.
                return {"status": "success", "event": event,
                        "projection": {"status": "compat", "domain_table": None, "reason": "database_permission_denied"}}
            # Keep the staging confirmation intact, but surface that canonical
            # projection needs retry rather than silently claiming it succeeded.
            from logging_util import logger
            logger.error(
                component="HEALTH_EVENT",
                operation="project_confirmed_event",
                error=error,
                user_id=str(user.id),
                context={"event_id": str(event["id"]), "event_type": str(event["event_type"])},
                fallback_action="raising_http_exception",
            )
            raise HTTPException(status_code=500, detail="Event confirmed but canonical projection failed") from error

    return {"status": "success", "event": event, "projection": projection}

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
                f"Review {str(metric).replace('_', ' ')}",
                "Bubbles observed a change relative to the available personal baseline; inspect the underlying observations.",
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
                    f"Review {str(metric).replace('_', ' ')}",
                    "Bubbles observed a change relative to your available personal baseline; review the underlying observations before drawing conclusions.",
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
    get_authenticated_user(authorization)
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
    get_authenticated_user(authorization)
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
