// Dev-only sample generator. Output files stay in web/dev and never enter dist.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const dir = path.dirname(fileURLToPath(import.meta.url));
const now = Date.now();
const iso = (ms) => new Date(ms).toISOString();
const M = (value, unit, scope = "device", o = {}) => ({
  value, unit, observed_at: value === null && !o.observed ? null : iso(now - (o.age ?? 2) * 1000), read_at: iso(now), source: o.source ?? "sample:fleet-top",
  status: o.status ?? (value === null ? "unknown" : "ok"), scope, window: o.window ?? null, numerator: o.num ?? null, denominator: o.den ?? null, note: o.note ?? "",
});
const dev = (id, host, title, hw, memTotal, o) => ({
  id, host_id: host, title, hardware: hw, mode: o.mode ?? "serving", workload: o.workload ?? "", owner: o.owner ?? "", state: o.state ?? "active",
  utilization: M(o.util ?? null, "%"), memory_used: M(o.mem ?? null, "GiB"), memory_total: M(memTotal, "GiB"),
  power: M(o.pw ?? null, "W"), power_limit: M(o.pl ?? null, "W"), temp_core: M(o.tc ?? null, "C"), temp_mem: M(o.tm ?? null, "C"), link: "",
});
const devices = [
  dev("b70-0", "omen", "B70#0", "Intel Arc Pro B70", 32, { util: 63, mem: 25.3, pw: 148, pl: 230, tc: 61, tm: 66, workload: "qwen3-27b dense seat", owner: "hearth" }),
  dev("b70-1", "omen", "B70#1", "Intel Arc Pro B70", 32, { util: 0, mem: 24.9, pw: 41, pl: 230, tc: 47, tm: 51, workload: "qwen3-27b dense seat (b)", owner: "hearth", state: "idle" }),
  dev("am4-0", "am4", "AM4#0 RTX 5070", "RTX 5070 12G", 12, { util: 88, mem: 10.3, pw: 201, pl: 250, tc: 67, tm: 70, workload: "TP2 seat :18094", owner: "hearth" }),
  dev("am4-1", "am4", "AM4#1 RTX 4070 Ti", "RTX 4070 Ti 12G", 12, { util: 84, mem: 10.1, pw: 176, pl: 285, tc: 64, tm: 0 || null, workload: "TP2 seat :18094", owner: "hearth" }),
  dev("fx99-0", "fx99", "FX99#0 RTX 2070 SUPER", "RTX 2070 SUPER 8G", 8, { util: null, mem: null, pw: null, pl: 215, tc: null, state: "stale", mode: "idle" }),
];
devices[4].utilization = M(7, "%", "device", { status: "stale", age: 34, observed: true });
devices[4].memory_used = M(1.2, "GiB", "device", { status: "stale", age: 34 });
devices[4].power = M(null, "W");
const seat = (id, host, label, model, active, slots, rate, q, devs, state) => ({
  id, host_id: host, label, model, state, health: "healthy", occupancy: M(active, "reqs", "engine_lifetime", { num: active, den: slots, source: "sample:hearth" }),
  queued: M(q, "reqs", "host"), generation_rate: M(rate, "tok/s", "host"), context_tokens: 49152, device_ids: devs,
});
const seats = [
  seat("omen-dense-27b", "omen", "omen-dense-27b", "qwen3-27b GPTQ", 3, 8, 41.6, 0, ["b70-0"], "active"),
  seat("omen-dense-27b-b", "omen", "omen-dense-27b-b", "qwen3-27b GPTQ", 0, 8, 0, 0, ["b70-1"], "idle"),
  seat("fx99-util", "fx99", "fx99-util", "qwen2.5-coder-7b", 0, 4, 0, 0, ["fx99-0"], "idle"),
  seat("am4-vllm", "am4", "am4-vllm (TP2)", "qwen3-27b GPTQ", 2, 8, 96.3, 1, ["am4-0", "am4-1"], "active"),
];
const link = (label, url, svc, en, reason = "") => ({ label, url, service_id: svc, enabled: en, reason });
const services = [
  { id: "aspire", name: "Aspire dashboard", responsibility: "Traces and logs for Service Bus work", endpoint: "127.0.0.1:18888", state: "unreachable", detail: "connection refused", source: "flow-top", age_s: 6, link: link("Aspire trace", "http://127.0.0.1:18888", "aspire", false, "Aspire unreachable now") },
  { id: "sb-explorer", name: "Service Bus Explorer API", responsibility: "Queue inspection", endpoint: "127.0.0.1:5001", state: "stale", detail: "API timing out; / answers 200", source: "flow-top", age_s: 41, link: link("Explorer", "http://127.0.0.1:5001", "sb-explorer", true) },
  { id: "hearth", name: "HEARTH door", responsibility: "Routing and execution", endpoint: "127.0.0.1:8710", state: "active", detail: "healthy", source: "fleet-top", age_s: 3, link: null },
  { id: "jepa", name: "JEPA context slicer (NPU)", responsibility: "Context ranking on the NPU", endpoint: "127.0.0.1:18097", state: "idle", detail: "0 requests in flight", source: "fleet-top", age_s: 3, link: null },
  { id: "ontology", name: "Ontology UI", responsibility: "Concept definitions", endpoint: "127.0.0.1:5173", state: "active", detail: "answers 200", source: "flow-top", age_s: 7, link: link("Ontology UI", "http://127.0.0.1:5173", "ontology", true) },
];
services.push({ id: "otel", name: "OTel collector", responsibility: "Trace ingest", endpoint: "127.0.0.1:4317", state: "active", detail: "accepting spans", source: "flow-top", age_s: 7, link: null },
  { id: "duckdb-ui", name: "DuckDB shell", responsibility: "Read-only inspection", endpoint: "local file", state: "unknown", detail: "no probe", source: "flow-top", age_s: null, link: null });
const stages = (s) => ["Submit", "Route", "Generate", "Check", "Review", "Deliver"].map((l, i) => ({ id: l.toLowerCase(), label: l, state: s[i] }));
const hop = (c, l, st, host, sum, basis, rec = null) => ({ component: c, label: l, state: st, host_id: host, summary: sum, basis, evidence_record: rec, observed_at: iso(now - 600000) });
const task = (o) => ({
  id: o.id, title: o.title, short_title: o.short ?? o.title, actor: "claude", host: "omen", stage: o.stage ?? "Deliver",
  stages: o.stages, latest_progress: o.progress, latest_progress_at: iso(now - (o.progAge ?? 540) * 1000),
  outcome: o.outcome, checks: o.checks, review: o.review, delivery: o.delivery, attention: o.attention ?? "",
  durations: o.durations ?? [], tokens: o.tokens, routing: o.routing,
  path: o.path, context: o.context, caches: o.caches, duckdb: o.duckdb, artifacts: o.artifacts ?? [], links: o.links ?? [], evidence_available: o.id === "relpack",
});
const routing = (f, j) => ({ task_family: f, provider: "hearth-local", model: "qwen3-27b", routed_by: "family", regime: "one call, thinking off, 8192", job_id: j });
const mm = (n, d, o = {}) => M(n, "facts", "job", { num: n, den: d, source: "sample:receipts", ...o });
const baseCtx = (extra = {}) => ({ concept: "Solicitation <- Workflow (via repo_slug)", hearth_input: M(8462, "bytes", "job", { source: "sample:hearth-input" }), selected_pack: M(7092, "bytes", "job", { source: "SELECTED-CONTEXT-PACK.json" }), selected_pack_sha256: "bbe0a69d5c1f0a7e44e1d1f2a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d", required_facts_selected: mm(9, 9), required_facts_baseline: mm(4, 9), comparison_note: "Selected coverage 9/9 confirmed. Not a general quality or speed claim.", corrections: [], ...extra });
const relpack = task({
  id: "relpack", title: "help-ontology-relpack-20261104: relationship pack for Solicitation", short: "relpack: Solicitation relationships",
  stages: stages(["done", "done", "done", "done", "done", "done"]), progress: "Parent consumed the delivered pack", progAge: 286,
  outcome: { state: "completed", label: "completed", summary: "Pack delivered and consumed by the parent.", finished_at: iso(now - 1260000) },
  checks: { state: "passed", detail: "9/9 required facts selected; 3 checks passed", evidence_record: "rec-checks" },
  review: { state: "accepted", detail: "Independent review accepted; baseline coverage corrected to 3/9", evidence_record: "rec-review" },
  delivery: { state: "recovered", label: "recovered after one IRC retry", evidence_record: "rec-irc" },
  durations: [{ label: "From first receipt", seconds: 1893, scope_note: "31m 33s, whole task" }, { label: "Broker send to parent consume", seconds: 286, scope_note: "Service Bus leg only" }, { label: "Pack cache, isolated receipt", seconds: 0.02578, scope_note: "25.78 ms vs 1.29 ms warm, one receipt, not an end-to-end speedup" }],
  tokens: { model_calls: 3, tokens_in: 9412, tokens_out: 2210, tokens_reasoning: null, budget_in: 16384, budget_out: 8192, budget_calls: 6, emit_repairs: 0 },
  routing: routing("code_fix", "job_7f3a21"),
  path: [
    hop("servicebus", "Service Bus", "used", "omen", "Broker receipts present", "BROKER-RECEIPTS.jsonl has 12 entries", "rec-broker"),
    hop("hearth", "HEARTH", "used", "omen", "Job succeeded", "job-succeeded.json present", "rec-job"),
    hop("jepa", "JEPA", "unused", "omen", "Not used for HEARTH file packing (desired.packed_files=[])", "execution.json desired.packed_files is empty"),
    hop("maf", "Steppewise/MAF", "unknown", "omen", "No lookup receipt", "LOOKUP-MEASURE.json absent; absence alone is not evidence of non-use"),
    hop("ontology", "Ontology", "used", "omen", "Definition delivered", "CONTEXT-DELIVERY.json present", "rec-ctx"),
    hop("ast", "AST/RAM cache", "unknown", "omen", "No attributed receipt", "no job receipt attributes the AST cache"),
    hop("duckdb", "DuckDB", "used", "omen", "Transition written and read back", "DUCKDB-RECEIPT.json present", "rec-duck"),
    hop("irc", "IRC", "used", "fx99", "Delivered after retry", "IRC-RECEIPTS.jsonl present", "rec-irc"),
    hop("parent", "Parent", "used", "omen", "Consumed", "consumption.json present", "rec-parent"),
  ],
  context: baseCtx({ corrections: [{ field: "required_facts_baseline", displayed_value: "3/9", producer_value: "4/9", source: "Pitwall brief, 2026-11-04. No review receipt holding 3/9 found in the run directory.", note: "Selected coverage 9/9 confirmed; no general quality claim." }] }),
  caches: { pack_cache: M(25.78, "ms", "job", { source: "pack-cache receipt", note: "isolated receipt, miss path" }), ast_ram: M(null, "%", "job", { note: "no attributed job receipt" }), model_kv: M(null, "%", "job", { note: "UNKNOWN: producer does not report model KV per job" }) },
  duckdb: { source_snapshot_read: "recorded", source_snapshot_detail: "snapshot #14 read", transition_written: "recorded", transition_written_detail: "1 transition row", transition_read_back: "recorded", transition_read_back_detail: "row count matched", evidence_record: "rec-duck" },
  artifacts: [{ name: "SELECTED-CONTEXT-PACK.json", sha256: "bbe0a69d5c1f0a7e44e1d1f2a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d", record_id: "rec-ctx", note: "7,092 bytes" }, { name: "feature.patch", sha256: "91ac03de7710c4aa22b4d0a0f5e6b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f708", record_id: null, note: "not served, hash from receipt" }, { name: "screen.png", sha256: "c0ffee00112233445566778899aabbccddeeff00112233445566778899aabbcc", record_id: "rec-png", note: "" }],
  links: [link("Aspire trace", "http://127.0.0.1:18888/traces", "aspire", false, "Aspire unreachable now"), link("Ontology UI", "http://127.0.0.1:5173", "ontology", true), link("External doc", "https://example.com/x", "x", true)],
});
const orland = task({
  id: "orland", title: "Orland three-feature batch", short: "Orland batch (3 features)", stages: stages(["done", "done", "done", "done", "done", "done"]), progress: "Batch finished", progAge: 4800,
  outcome: { state: "completed", label: "completed", summary: "Three features delivered in one batch.", finished_at: iso(now - 5400000) },
  checks: { state: "passed", detail: "3/3 feature checks", evidence_record: null }, review: { state: "pending", detail: "Awaiting review", evidence_record: null },
  delivery: { state: "delivered", label: "delivered", evidence_record: null },
  durations: [{ label: "Batch", seconds: 755, scope_note: "12m 35s for the whole three-feature batch" }],
  tokens: { model_calls: 9, tokens_in: 41200, tokens_out: 9980, tokens_reasoning: null, budget_in: 65536, budget_out: 16384, budget_calls: 12, emit_repairs: 1 }, routing: routing("code_fix", "job_21bb90"),
  path: [hop("hearth", "HEARTH", "used", "omen", "Job succeeded", "execution.json present"), hop("duckdb", "DuckDB", "unknown", "omen", "Source snapshot use unknown", "DUCKDB-RECEIPT.json absent"), hop("ontology", "Ontology", "unknown", "omen", "Unknown", "receipts absent"), hop("maf", "Steppewise/MAF", "unknown", "omen", "Unknown", "receipts absent")],
  context: baseCtx({ required_facts_selected: mm(null, null), required_facts_baseline: mm(null, null), concept: "" }), caches: { pack_cache: M(null, "%", "job"), ast_ram: M(null, "%", "job"), model_kv: M(null, "%", "job", { note: "producer gap" }) },
  duckdb: { source_snapshot_read: "unknown", source_snapshot_detail: "no receipt", transition_written: "unknown", transition_written_detail: "", transition_read_back: "unknown", transition_read_back_detail: "", evidence_record: null },
});
const helploop = task({
  id: "help-loop", title: "help-loop-20261104T2114Z", short: "help-loop 21:14Z", stages: stages(["done", "done", "done", "attention", "waiting", "unknown"]), stage: "Check", progress: "Check needs a rerun", progAge: 90,
  outcome: { state: "active", label: "active", summary: "Work in progress.", finished_at: null }, checks: { state: "unknown", detail: "not yet run", evidence_record: null }, review: { state: "unknown", detail: "", evidence_record: null },
  delivery: { state: "waiting", label: "waiting", evidence_record: null }, attention: "Check rerun requested",
  tokens: { model_calls: 1, tokens_in: 3100, tokens_out: null, tokens_reasoning: null, budget_in: 16384, budget_out: null, budget_calls: 4, emit_repairs: null }, routing: routing("code_review", "job_c0ffee"),
  path: [hop("servicebus", "Service Bus", "unknown", "omen", "No broker files; direct submission not recorded", "no field states direct submission"), hop("hearth", "HEARTH", "active", "omen", "Running", "execution.json present")],
  context: baseCtx({ concept: "", required_facts_selected: mm(null, null), required_facts_baseline: mm(null, null) }), caches: { pack_cache: M(0, "%", "job", { num: 0, den: 0, note: "no pack lookups" }), ast_ram: M(null, "%", "job"), model_kv: M(null, "%", "job") },
  duckdb: { source_snapshot_read: "not_recorded", source_snapshot_detail: "", transition_written: "unknown", transition_written_detail: "", transition_read_back: "unknown", transition_read_back_detail: "", evidence_record: null },
});
const markup = task({
  id: "markup", title: '<img src=x onerror=alert(1)> <b>bold</b> & "quoted"', short: "<script>alert(2)</script> task", stages: stages(["done", "done", "done", "done", "failed", "unknown"]), progress: "<i>failed</i> in review", progAge: 3000,
  outcome: { state: "failed", label: "failed", summary: "<b>markup</b> in data stays inert", finished_at: iso(now - 9000000) }, checks: { state: "failed", detail: "check failed", evidence_record: null }, review: { state: "rejected", detail: "rejected", evidence_record: null },
  delivery: { state: "failed", label: "not delivered", evidence_record: null },
  tokens: { model_calls: 2, tokens_in: 1000, tokens_out: 500, tokens_reasoning: 0, budget_in: 4096, budget_out: 2048, budget_calls: 3, emit_repairs: 0 }, routing: routing("code_fix", "job_bad001"),
  path: [hop("hearth", "<b>HEARTH</b>", "used", "omen", "ok", "x")], context: baseCtx({ concept: "", required_facts_selected: mm(null, null), required_facts_baseline: mm(null, null) }), caches: { pack_cache: M(null, "%", "job"), ast_ram: M(null, "%", "job"), model_kv: M(null, "%", "job") },
  duckdb: { source_snapshot_read: "unknown", source_snapshot_detail: "", transition_written: "unknown", transition_written_detail: "", transition_read_back: "unknown", transition_read_back_detail: "", evidence_record: null },
});
const mkSnap = (mode) => ({
  schema: "pitwall.v1", seq: 42, mode, scenario: mode === "demo" ? "active" : null, scenario_note: mode === "demo" ? "synthetic pairing of two independent fixtures" : "", generated_at: iso(now),
  overall: { state: "active", headline: "serving, work active", reason: "2 seats occupied" },
  exception: { level: "service", text: "Aspire unreachable now (task history unaffected)", source: "flow-top" },
  sources: [
    { id: "fleet", label: "fleet-top", state: "active", path: "/dev/shm/fleet-top-snapshot.json", observed_at: iso(now - 3000), read_at: iso(now), age_s: 3, stale_after_s: 6, last_error: "" },
    { id: "flow", label: "flow-top", state: "active", path: "/dev/shm/flow-top-snapshot.json", observed_at: iso(now - 5000), read_at: iso(now), age_s: 5, stale_after_s: 10, last_error: "" },
  ],
  hosts: [{ id: "omen", label: "OMEN", role: "2x B70 32G", state: "active" }, { id: "am4", label: "AM4", role: "TP2 seat", state: "active" }, { id: "fx99", label: "FX99", role: "RTX 2070 SUPER", state: "stale" }],
  devices, seats, services,
  engine_caches: [{ id: "am4-vllm", label: "am4-vllm prefix", hit: M(0, "%", "engine_lifetime", { num: 0, den: 0, source: "vllm counters", note: "counters since engine start" }) }, { id: "omen-dense-b", label: "omen-dense-27b-b prefix", hit: M(null, "%", "engine_lifetime", { source: "vllm counters", note: "counters unreadable" }) }, { id: "omen-dense", label: "omen-dense-27b prefix", hit: M(94.2, "%", "engine_lifetime", { num: 18840, den: 20000, source: "vllm counters" }) }],
  network: [{ id: "omen-am4", label: "OMEN-AM4 Network latency", latency: M(null, "ms", "host", { note: "unmeasured: fleet-top lists no probe and Pitwall does not invent one" }) }],
  tasks: [relpack, orland, helploop, markup, { ...orland, id: "t5", short_title: "older task 5", title: "older task 5" }],
  default_task_id: "relpack", coverage_notes: ["flow-top returns at most 10 tasks and has no limit option.", "Model KV per job is not reported by the producer."], history_started_at: iso(now - 180000),
});
fs.writeFileSync(path.join(dir, "sample-snapshot.json"), JSON.stringify(mkSnap("live"), null, 2));
fs.writeFileSync(path.join(dir, "sample-demo.json"), JSON.stringify(mkSnap("demo"), null, 2));
fs.writeFileSync(path.join(dir, "sample-evidence-index.json"), JSON.stringify({ task_id: "relpack", records: [
  { record_id: "rec-ctx", name: "SELECTED-CONTEXT-PACK.json", kind: "json", bytes: 7092, modified_at: iso(now - 1300000) },
  { record_id: "rec-job", name: "job-succeeded.json", kind: "json", bytes: 1820, modified_at: iso(now - 1300000) },
  { record_id: "rec-broker", name: "BROKER-RECEIPTS.jsonl", kind: "jsonl", bytes: 5230, modified_at: iso(now - 1300000) },
  { record_id: "rec-png", name: "screen.png", kind: "image", bytes: 20310, modified_at: iso(now - 1300000) } ], not_served: ["feature.patch", "helper-result.txt", "run.log"] }, null, 2));
// history: 3 minutes of 2 s samples, with a gap
const pts = (f, gap) => { const out = []; for (let i = 90; i >= 0; i--) { const t = (now - i * 2000) / 1000; out.push([t, gap && i > 40 && i < 52 ? null : f(i)]); } return out; };
const series = [
  ...devices.slice(0, 4).map((d, k) => ({ key: `device.${d.id}.utilization`, label: `${d.title} utilization`, unit: "%", scope: "device", points: pts((i) => Math.max(0, Math.min(100, (d.utilization.value ?? 0) + 18 * Math.sin(i / 7 + k) + 6 * Math.cos(i / 3))), k === 2) })),
  { key: "device.fx99-0.utilization", label: "FX99 utilization", unit: "%", scope: "device", points: pts((i) => (i % 9 === 0 ? 14 : 5), true) },
  { key: "seat.omen-dense-27b.generation_rate", label: "rate", unit: "tok/s", scope: "host", points: pts((i) => 40 + 6 * Math.sin(i / 5)) },
  { key: "seat.am4-vllm.generation_rate", label: "rate", unit: "tok/s", scope: "host", points: pts((i) => 94 + 9 * Math.sin(i / 4)) },
];
fs.writeFileSync(path.join(dir, "sample-history.json"), JSON.stringify({ window_s: 300, started_at: iso(now - 180000), now: now / 1000, series }, null, 2));
console.log("sample written");
