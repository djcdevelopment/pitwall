"""Pitwall normalized state contract (schema pitwall.v1).

One snapshot feeds all three presentations. web/src/contract.ts mirrors this file by hand;
change both together.

Independent axes, never derived from each other:
  Service.state          what a service is doing now
  Task.participation     whether the selected task used a component (from its receipts)
  Task.outcome           what the task's recorded result was
  Task.checks            whether its checks passed
  Task.review            independent review or adoption state

Null never means zero. A value of 0 is a measured zero with status "ok".
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

SCHEMA = "pitwall.v1"

# How current a single reading is. Not a statement about work.
MeasurementStatus = Literal["ok", "stale", "unreachable", "unknown", "unused"]
Scope = Literal["host", "device", "job", "engine_lifetime", "daemon_lifetime"]
# Current state of a service, device, seat, collector or the system as a whole.
# reachable: an endpoint answered; says nothing about whether work is happening there.
ActivityState = Literal["active", "idle", "reachable", "stale", "unreachable", "unknown"]
ParticipationState = Literal["active", "used", "unused", "unknown"]
OutcomeState = Literal["active", "staged", "completed", "recovered", "failed", "unknown"]
StageState = Literal["done", "working", "waiting", "attention", "failed", "unknown", "unused"]
CheckState = Literal["passed", "failed", "unknown"]
ReviewState = Literal["pending", "accepted", "rejected", "unknown"]
DeliveryState = Literal["delivered", "recovered", "active", "waiting", "failed", "unknown"]
StepState = Literal["recorded", "not_recorded", "unknown"]
Mode = Literal["live", "demo"]


class Measurement(BaseModel):
    value: Union[float, int, str, bool, None] = None
    unit: str = ""
    observed_at: Optional[str] = None  # when the source observed it (ISO 8601 UTC)
    read_at: str = ""  # when Pitwall read the record holding it
    source: str = ""
    status: MeasurementStatus = "unknown"
    scope: Scope = "host"
    window: Optional[str] = None  # e.g. "engine uptime", "daemon uptime", "per job"
    numerator: Optional[float] = None
    denominator: Optional[float] = None
    note: str = ""


class CollectorVersion(BaseModel):
    """State of an external collector's checkout. Pitwall's own commit does not pin it."""

    repo: str
    commit: Optional[str] = None
    dirty: Optional[bool] = None  # null means unknown
    changed_files: list[str] = Field(default_factory=list)
    checked_at: str = ""
    note: str = ""


class SourceRecord(BaseModel):
    id: str  # fleet | flow | receipts
    label: str
    state: ActivityState  # idle = healthy, nothing wrong; stale and unreachable as defined
    path: str  # tui_cache | self_refresh | run_directories | fixture
    observed_at: Optional[str] = None
    read_at: Optional[str] = None
    age_s: Optional[float] = None
    stale_after_s: float
    last_error: str = ""
    version: Optional[CollectorVersion] = None


class Host(BaseModel):
    id: str  # omen | am4 | fx99
    label: str
    role: str
    state: ActivityState


class Device(BaseModel):
    id: str
    host_id: str
    title: str
    hardware: str
    mode: str  # fleet-top's device mode, verbatim
    workload: str
    owner: str
    state: ActivityState
    utilization: Measurement  # percent
    memory_used: Measurement  # GiB, measured, per device. Never summed across devices.
    memory_total: Measurement  # GiB
    power: Measurement  # W
    power_limit: Measurement  # W
    temp_core: Measurement  # C
    temp_mem: Measurement  # C
    link: str = ""


class Seat(BaseModel):
    id: str
    host_id: str
    label: str
    model: str
    state: ActivityState
    health: str
    occupancy: Measurement  # numerator active reqs, denominator capacity slots; unit "reqs"
    queued: Measurement
    generation_rate: Measurement  # tok/s
    context_tokens: Optional[int] = None
    device_ids: list[str] = Field(default_factory=list)


class InspectionLink(BaseModel):
    label: str
    url: str  # loopback only
    service_id: str = ""
    enabled: bool = True
    reason: str = ""  # shown when disabled
    annotation: str = ""  # shown when enabled but its backend has a problem


class Service(BaseModel):
    id: str
    name: str
    responsibility: str
    endpoint: str
    state: ActivityState
    detail: str
    source: str
    age_s: Optional[float] = None
    link: Optional[InspectionLink] = None
    backlog: Optional[Measurement] = None  # null value is unknown, never zero


class Exception_(BaseModel):
    """The highest-priority supported exception. Never utilization or occupancy."""

    level: Literal["failed", "unreachable", "stale", "service"]
    text: str
    source: str


class Stage(BaseModel):
    id: str  # request | helper | parent_work | checks | result
    label: str
    state: StageState


class PathHop(BaseModel):
    component: str  # service_bus | hearth | steppewise | ontology | jepa | ast_cache | duckdb | irc | parent
    label: str
    state: ParticipationState
    host_id: Optional[str] = None
    summary: str
    basis: str  # the field or receipt that establishes state, or why it is unknown
    evidence_record: Optional[str] = None
    observed_at: Optional[str] = None


class Outcome(BaseModel):
    state: OutcomeState
    label: str
    summary: str  # useful result, one sentence
    finished_at: Optional[str] = None


class Checks(BaseModel):
    state: CheckState
    detail: str
    evidence_record: Optional[str] = None


class Review(BaseModel):
    state: ReviewState
    detail: str
    evidence_record: Optional[str] = None


class Delivery(BaseModel):
    state: DeliveryState
    label: str
    evidence_record: Optional[str] = None


class ScopedDuration(BaseModel):
    label: str
    seconds: Optional[float]
    scope_note: str


class TokenUse(BaseModel):
    model_calls: Optional[int] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    tokens_reasoning: Optional[int] = None
    budget_in: Optional[int] = None  # the task's own frozen budget. Consumption is not progress.
    budget_out: Optional[int] = None
    budget_calls: Optional[int] = None
    emit_repairs: Optional[int] = None


class Routing(BaseModel):
    """HEARTH's model-family routing. Separate from context packing."""

    task_family: str = ""
    provider: str = ""
    model: str = ""
    routed_by: str = ""
    regime: str = ""
    job_id: str = ""


class Correction(BaseModel):
    field: str
    displayed_value: str
    basis_label: str = ""  # how the displayed value is known, e.g. "review-reported correction"
    producer_value: str
    source: str
    note: str = ""


class ContextPack(BaseModel):
    """Context preparation. hearth_input and selected_pack are different objects."""

    concept: str = ""
    hearth_input: Measurement  # bytes of HEARTH's input artifact
    selected_pack: Measurement  # bytes of the selected ontology context pack; null if none recorded
    selected_pack_sha256: str = ""
    required_facts_selected: Measurement  # numerator/denominator
    required_facts_baseline: Measurement  # numerator/denominator, after corrections
    comparison_note: str = ""
    corrections: list[Correction] = Field(default_factory=list)


class JobCaches(BaseModel):
    """Per-job only. Engine and daemon counters live in Snapshot.engine_caches."""

    pack_cache: Measurement
    ast_ram: Measurement
    model_kv: Measurement


class DuckDbSteps(BaseModel):
    """Three separate claims. One does not imply another."""

    source_snapshot_read: StepState
    source_snapshot_detail: str
    transition_written: StepState
    transition_written_detail: str
    transition_read_back: StepState
    transition_read_back_detail: str
    evidence_record: Optional[str] = None


class ArtifactRef(BaseModel):
    name: str
    sha256: str = ""
    record_id: Optional[str] = None  # null when not served; shown by name and hash only
    note: str = ""


class Task(BaseModel):
    id: str
    title: str
    short_title: str
    actor: str
    host: str
    stage: str
    stages: list[Stage]
    latest_progress: str
    latest_progress_at: Optional[str] = None
    outcome: Outcome
    checks: Checks
    review: Review
    delivery: Delivery
    attention: str = ""
    durations: list[ScopedDuration] = Field(default_factory=list)
    tokens: TokenUse
    routing: Routing
    path: list[PathHop]
    context: ContextPack
    caches: JobCaches
    duckdb: DuckDbSteps
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    links: list[InspectionLink] = Field(default_factory=list)
    evidence_available: bool = False


class EngineCache(BaseModel):
    """Lifetime counters. Never attributable to a job."""

    id: str
    label: str
    hit: Measurement  # numerator hits, denominator queries; value is percent or null


class NetworkLink(BaseModel):
    id: str
    label: str
    latency: Measurement


class Overall(BaseModel):
    state: ActivityState
    headline: str
    reason: str


class Snapshot(BaseModel):
    schema_: str = Field(default=SCHEMA, alias="schema")
    seq: int
    mode: Mode
    scenario: Optional[str] = None
    scenario_note: str = ""
    generated_at: str
    overall: Overall
    exception: Optional[Exception_] = None
    sources: list[SourceRecord]
    hosts: list[Host]
    devices: list[Device]
    seats: list[Seat]
    services: list[Service]
    engine_caches: list[EngineCache]
    network: list[NetworkLink]
    tasks: list[Task]
    default_task_id: Optional[str] = None
    coverage_notes: list[str] = Field(default_factory=list)
    history_started_at: Optional[str] = None

    model_config = {"populate_by_name": True}


class Series(BaseModel):
    key: str  # device.<id>.utilization | .memory_used | .power | .temp_core ; seat.<id>.generation_rate | .occupancy
    label: str
    unit: str
    scope: Scope
    points: list[tuple[float, Optional[float]]]  # (source observation epoch seconds, value). None is a gap.


class History(BaseModel):
    window_s: int
    started_at: Optional[str]
    now: float
    series: list[Series]


class EvidenceRecord(BaseModel):
    record_id: str
    name: str
    kind: Literal["json", "jsonl", "markdown", "image"]
    bytes: int
    modified_at: str


class EvidenceIndex(BaseModel):
    task_id: str
    records: list[EvidenceRecord]
    not_served: list[str] = Field(default_factory=list)
