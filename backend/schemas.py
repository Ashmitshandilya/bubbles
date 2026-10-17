"""
Pydantic response schemas for all API endpoints.
These define the actual response structures returned by the backend.
All responses follow the pattern: {"status": "success", "<data_key>": <data>}
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# ============================================================================
# BASE RESPONSE WRAPPER
# ============================================================================

class SuccessResponse(BaseModel):
    """Standard success response wrapper."""
    status: Literal["success"] = "success"


# ============================================================================
# HEALTH EVENTS & EXTRACTION
# ============================================================================

class ExtractedEvent(BaseModel):
    event_type: str
    source_text: str
    confidence: float
    attributes: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: Optional[str] = None
    extraction_status: str = "pending"


class ExtractEventsResponse(SuccessResponse):
    extracted: List[ExtractedEvent] = Field(default_factory=list)


class ExtractedEventsListResponse(SuccessResponse):
    events: List[ExtractedEvent] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


# ============================================================================
# WEEKLY INSIGHTS
# ============================================================================

class InsightItem(BaseModel):
    id: Optional[str] = None  # stable, URL-safe: GET /insights/{id} resolves it
    confidence_label: Optional[str] = None  # "low" | "medium" | "high", the same word the Patterns page shows
    title: str
    description: str
    category: str
    confidence: float
    supporting_events: List[str] = Field(default_factory=list)
    actionable: bool = False
    suggested_action: Optional[str] = None


class WeeklyInsightsData(BaseModel):
    generated_at: str
    period: Dict[str, Any]
    data_quality: Dict[str, Any]
    insights: List[InsightItem] = Field(default_factory=list)
    trend: Optional[Dict[str, Any]] = None  # builder emits {period_days, event_count, top_signals...}
    disclaimer: str


class WeeklyInsightsResponse(SuccessResponse):
    insights: WeeklyInsightsData


# ============================================================================
# NUTRITION INTELLIGENCE
# ============================================================================

class NutritionSummaryData(BaseModel):
    average_daily_calories_logged: Optional[float] = None
    average_daily_protein_g_logged: Optional[float] = None
    average_daily_water_ml_logged: Optional[float] = None
    days_with_nutrition_signals: int
    data_quality: Dict[str, Any]
    safety_note: Optional[str] = None


class NutritionIntelligenceResponse(SuccessResponse):
    nutrition: NutritionSummaryData


# ============================================================================
# CYCLE INTELLIGENCE
# ============================================================================

class CycleData(BaseModel):
    period_start_count: int
    observed_cycle_lengths: List[int] = Field(default_factory=list)
    average_observed_cycle_length: Optional[float] = None
    start_to_start_intervals: List[int] = Field(default_factory=list)
    latest_period_start: Optional[str] = None


class CycleIntelligenceData(BaseModel):
    cycle: CycleData
    symptoms: List[str] = Field(default_factory=list)
    interpretation: str
    data_quality: Dict[str, Any]


class CycleIntelligenceResponse(SuccessResponse):
    cycle: CycleIntelligenceData


# ============================================================================
# INTELLIGENCE OVERVIEW (combines nutrition + cycle)
# ============================================================================

class IntelligenceOverviewResponse(SuccessResponse):
    nutrition: NutritionSummaryData
    cycle: CycleIntelligenceData


# ============================================================================
# HEALTH STATE ENGINE
# ============================================================================

class DeviationDetail(BaseModel):
    current: Optional[float] = None
    baseline: Optional[float] = None
    delta: Optional[float] = None
    percent: Optional[float] = None


class Deviations(BaseModel):
    """Keys mirror health_state_engine metrics (previously mismatched and silently dropped)."""
    sleep_hours: Optional[DeviationDetail] = None
    water_ml: Optional[DeviationDetail] = None
    activity_minutes: Optional[DeviationDetail] = None
    weight_kg: Optional[DeviationDetail] = None
    mood: Optional[DeviationDetail] = None


# Event counts keyed by event_type (sleep, hydration, mood, ...) in the window.
SignalCounts = Dict[str, int]


class DataGaps(BaseModel):
    """List of metric names that have no logged data in the current window."""
    gaps: List[str] = Field(default_factory=list)


class CorrelationItem(BaseModel):
    """A temporal correlation between two event subjects."""
    kind: str
    a: Dict[str, str]
    b: Dict[str, str]
    pair_count: int
    window_days: int
    strength: float
    interpretation: str
    id: Optional[str] = None
    confidence_label: Optional[str] = None
    source_event_ids: List[str] = Field(default_factory=list)


class Correlations(BaseModel):
    """List of temporal correlations detected in the event stream."""
    items: List[CorrelationItem] = Field(default_factory=list)


class HealthStateData(BaseModel):
    window_days: int
    event_count: int
    signal_counts: SignalCounts
    baseline: Dict[str, Any]
    deviations: Deviations
    data_gaps: DataGaps
    correlations: Correlations
    status: str
    interpretation: str


class HealthStateResponse(SuccessResponse):
    state: HealthStateData


# ============================================================================
# LIVING SIGNAL MAP
# ============================================================================

class LivingSignalItem(BaseModel):
    kind: str
    label: str
    direction: Optional[str] = None
    confidence: str = "moderate"
    evidence: str = ""


class LivingSignalMapData(BaseModel):
    status: str
    observed_signal_count: int
    baseline_change_count: int
    data_gap_count: int
    signals: List[LivingSignalItem] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)
    coverage: str = "observed"
    interpretation_policy: str


class LivingSignalMapResponse(SuccessResponse):
    window_days: int
    map: LivingSignalMapData


# ============================================================================
# DAILY COMPANION
# ============================================================================

class FocusItem(BaseModel):
    area: str
    reason: str
    priority: int
    kind: str = "check_in"


class CompanionData(BaseModel):
    generated_at: str
    headline: str
    state_status: str
    focus: List[FocusItem] = Field(default_factory=list)
    learning_signals: int = 0  # number of memory candidates Bubbles is still learning about
    data_gaps: List[str] = Field(default_factory=list)
    safety_note: Optional[str] = None
    disclaimer: str


class DailyCompanionResponse(SuccessResponse):
    companion: CompanionData
    state: Optional[HealthStateData] = None


# ============================================================================
# LEARNING ENGINE / INTELLIGENCE BRIEF
# ============================================================================

class MemoryCandidate(BaseModel):
    key: str
    value: str
    confidence: float
    tier: Literal["L1", "L2", "L3", "L4"] = "L2"
    evidence_count: int = 1


class LearningAnalysis(BaseModel):
    patterns: List[str] = Field(default_factory=list)
    anomalies: List[str] = Field(default_factory=list)
    trends: List[str] = Field(default_factory=list)


class IntelligenceBriefData(BaseModel):
    generated_at: str
    window_days: Optional[int] = None
    event_count: int = 0
    analysis: Optional[LearningAnalysis] = None
    memory_candidates: List[MemoryCandidate] = Field(default_factory=list)
    uncertainty: float = 0.0
    state: Optional[HealthStateData] = None
    learning: Optional[Dict[str, Any]] = None
    companion: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, Any]]] = None


class IntelligenceBriefResponse(SuccessResponse):
    brief: IntelligenceBriefData


# ============================================================================
# CHAT / AI RESPONSE
# ============================================================================

class AIResponseData(BaseModel):
    text: str
    message_id: str
    conversation_id: str
    provider: str
    model: str
    tokens_used: Optional[int] = None
    health_event_ids: List[str] = Field(default_factory=list)
    safety_level: Optional[str] = None


class AIResponse(SuccessResponse):
    response: AIResponseData


# ============================================================================
# CHAT HISTORY
# ============================================================================

class ChatMessage(BaseModel):
    id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    health_event_ids: List[str] = Field(default_factory=[])


class ChatConversation(BaseModel):
    id: str
    title: Optional[str] = None
    created_at: str
    updated_at: str
    message_count: int = 0


class ChatHistoryResponse(SuccessResponse):
    messages: List[ChatMessage] = Field(default_factory=list)
    conversations: List[ChatConversation] = Field(default_factory=list)


# ============================================================================
# AI TELEMETRY
# ============================================================================

class ProviderTelemetry(BaseModel):
    provider: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    total_tokens: int = 0
    last_used: Optional[str] = None


class AITelemetryData(BaseModel):
    providers: List[ProviderTelemetry] = Field(default_factory=list)
    total_requests: int = 0
    fallback_count: int = 0
    circuit_breaker_states: Dict[str, str] = Field(default_factory=dict)


class AITelemetryResponse(SuccessResponse):
    telemetry: AITelemetryData


# ============================================================================
# MEMORY ENDPOINTS
# ============================================================================

class MemoryItem(BaseModel):
    id: str
    user_id: str
    tier: Literal["L1", "L2", "L3", "L4"]
    key: str
    value: str
    confidence: float
    source: str
    verification_status: str
    superseded_by: Optional[str] = None
    review_after: Optional[str] = None
    created_at: str
    updated_at: str


class MemoryListResponse(SuccessResponse):
    memories: List[MemoryItem] = Field(default_factory=list)
    total: int


class MemoryPromoteResponse(SuccessResponse):
    promoted: List[MemoryItem] = Field(default_factory=list)


class MemoryDemoteResponse(SuccessResponse):
    demoted: List[MemoryItem] = Field(default_factory=list)


# ============================================================================
# RAG / SEMANTIC SEARCH
# ============================================================================

class RAGSearchResult(BaseModel):
    id: str
    content: str
    similarity: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGSearchResponse(SuccessResponse):
    results: List[RAGSearchResult] = Field(default_factory=list)
    query: str
    total: int


# ============================================================================
# HEALTH / SYSTEM ENDPOINTS
# ============================================================================

class HealthCheckResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    version: str
    timestamp: str
    services: Dict[str, str] = Field(default_factory=dict)
    # True while the live database denies the backend some tables: Bubbles keeps working in compatibility mode.
    compat_mode: bool = False
    denied_tables: List[str] = Field(default_factory=list)


class VersionResponse(BaseModel):
    version: str
    build_date: str
    git_commit: Optional[str] = None


# ============================================================================
# ERROR RESPONSES (for OpenAPI documentation)
# ============================================================================

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    error: ErrorDetail