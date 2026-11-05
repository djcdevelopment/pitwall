// Pitwall normalized state contract (schema pitwall.v1).
// Mirrors server/pitwall/contract.py by hand; change both together.
// Null never means zero. A value of 0 is a measured zero with status "ok".

export type MeasurementStatus = "ok" | "stale" | "unreachable" | "unknown" | "unused";
export type Scope = "host" | "device" | "job" | "engine_lifetime" | "daemon_lifetime";
export type ActivityState = "active" | "idle" | "stale" | "unreachable" | "unknown";
export type ParticipationState = "active" | "used" | "unused" | "unknown";
export type OutcomeState = "active" | "staged" | "completed" | "recovered" | "failed" | "unknown";
export type StageState = "done" | "working" | "waiting" | "attention" | "failed" | "unknown" | "unused";
export type CheckState = "passed" | "failed" | "unknown";
export type ReviewState = "pending" | "accepted" | "rejected" | "unknown";
export type DeliveryState = "delivered" | "recovered" | "active" | "waiting" | "failed" | "unknown";
export type StepState = "recorded" | "not_recorded" | "unknown";
export type Mode = "live" | "demo";

export interface Measurement {
  value: number | string | boolean | null;
  unit: string;
  observed_at: string | null;
  read_at: string;
  source: string;
  status: MeasurementStatus;
  scope: Scope;
  window: string | null;
  numerator: number | null;
  denominator: number | null;
  note: string;
}

export interface CollectorVersion {
  repo: string;
  commit: string | null;
  dirty: boolean | null;
  changed_files: string[];
  checked_at: string;
  note: string;
}

export interface SourceRecord {
  id: string;
  label: string;
  state: ActivityState;
  path: string;
  observed_at: string | null;
  read_at: string | null;
  age_s: number | null;
  stale_after_s: number;
  last_error: string;
  version: CollectorVersion | null;
}

export interface Host {
  id: string;
  label: string;
  role: string;
  state: ActivityState;
}

export interface Device {
  id: string;
  host_id: string;
  title: string;
  hardware: string;
  mode: string;
  workload: string;
  owner: string;
  state: ActivityState;
  utilization: Measurement;
  memory_used: Measurement;
  memory_total: Measurement;
  power: Measurement;
  power_limit: Measurement;
  temp_core: Measurement;
  temp_mem: Measurement;
  link: string;
}

export interface Seat {
  id: string;
  host_id: string;
  label: string;
  model: string;
  state: ActivityState;
  health: string;
  occupancy: Measurement;
  queued: Measurement;
  generation_rate: Measurement;
  context_tokens: number | null;
  device_ids: string[];
}

export interface InspectionLink {
  label: string;
  url: string;
  service_id: string;
  enabled: boolean;
  reason: string;
}

export interface Service {
  id: string;
  name: string;
  responsibility: string;
  endpoint: string;
  state: ActivityState;
  detail: string;
  source: string;
  age_s: number | null;
  link: InspectionLink | null;
}

export interface SystemException {
  level: "failed" | "unreachable" | "stale" | "service";
  text: string;
  source: string;
}

export interface Stage {
  id: string;
  label: string;
  state: StageState;
}

export interface PathHop {
  component: string;
  label: string;
  state: ParticipationState;
  host_id: string | null;
  summary: string;
  basis: string;
  evidence_record: string | null;
  observed_at: string | null;
}

export interface Outcome {
  state: OutcomeState;
  label: string;
  summary: string;
  finished_at: string | null;
}

export interface Checks {
  state: CheckState;
  detail: string;
  evidence_record: string | null;
}

export interface Review {
  state: ReviewState;
  detail: string;
  evidence_record: string | null;
}

export interface Delivery {
  state: DeliveryState;
  label: string;
  evidence_record: string | null;
}

export interface ScopedDuration {
  label: string;
  seconds: number | null;
  scope_note: string;
}

export interface TokenUse {
  model_calls: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  tokens_reasoning: number | null;
  budget_in: number | null;
  budget_out: number | null;
  budget_calls: number | null;
  emit_repairs: number | null;
}

export interface Routing {
  task_family: string;
  provider: string;
  model: string;
  routed_by: string;
  regime: string;
  job_id: string;
}

export interface Correction {
  field: string;
  displayed_value: string;
  basis_label: string;
  producer_value: string;
  source: string;
  note: string;
}

export interface ContextPack {
  concept: string;
  hearth_input: Measurement;
  selected_pack: Measurement;
  selected_pack_sha256: string;
  required_facts_selected: Measurement;
  required_facts_baseline: Measurement;
  comparison_note: string;
  corrections: Correction[];
}

export interface JobCaches {
  pack_cache: Measurement;
  ast_ram: Measurement;
  model_kv: Measurement;
}

export interface DuckDbSteps {
  source_snapshot_read: StepState;
  source_snapshot_detail: string;
  transition_written: StepState;
  transition_written_detail: string;
  transition_read_back: StepState;
  transition_read_back_detail: string;
  evidence_record: string | null;
}

export interface ArtifactRef {
  name: string;
  sha256: string;
  record_id: string | null;
  note: string;
}

export interface Task {
  id: string;
  title: string;
  short_title: string;
  actor: string;
  host: string;
  stage: string;
  stages: Stage[];
  latest_progress: string;
  latest_progress_at: string | null;
  outcome: Outcome;
  checks: Checks;
  review: Review;
  delivery: Delivery;
  attention: string;
  durations: ScopedDuration[];
  tokens: TokenUse;
  routing: Routing;
  path: PathHop[];
  context: ContextPack;
  caches: JobCaches;
  duckdb: DuckDbSteps;
  artifacts: ArtifactRef[];
  links: InspectionLink[];
  evidence_available: boolean;
}

export interface EngineCache {
  id: string;
  label: string;
  hit: Measurement;
}

export interface NetworkLink {
  id: string;
  label: string;
  latency: Measurement;
}

export interface Overall {
  state: ActivityState;
  headline: string;
  reason: string;
}

export interface Snapshot {
  schema: string;
  seq: number;
  mode: Mode;
  scenario: string | null;
  scenario_note: string;
  generated_at: string;
  overall: Overall;
  exception: SystemException | null;
  sources: SourceRecord[];
  hosts: Host[];
  devices: Device[];
  seats: Seat[];
  services: Service[];
  engine_caches: EngineCache[];
  network: NetworkLink[];
  tasks: Task[];
  default_task_id: string | null;
  coverage_notes: string[];
  history_started_at: string | null;
}

export interface Series {
  key: string;
  label: string;
  unit: string;
  scope: Scope;
  points: [number, number | null][];
}

export interface History {
  window_s: number;
  started_at: string | null;
  now: number;
  series: Series[];
}

export interface EvidenceRecord {
  record_id: string;
  name: string;
  kind: "json" | "jsonl" | "markdown" | "image";
  bytes: number;
  modified_at: string;
}

export interface EvidenceIndex {
  task_id: string;
  records: EvidenceRecord[];
  not_served: string[];
}
