import type { EvidenceIndex, History, Mode, Snapshot, Task } from "./contract";

export type View = "desktop" | "strip" | "narrow";
export type WindowS = 60 | 300 | 900;
export interface Scenario { id: string; note: string }
export interface EvidenceState {
  open: boolean; taskId: string | null; index: EvidenceIndex | null; loading: boolean; error: string | null;
  recordId: string | null; text: string | null; imageUrl: string | null; recordError: string | null; returnFid: string | null; focusDrawer: boolean; section: string | null;
}
export interface State {
  snapshot: Snapshot | null; history: History | null; selectedTaskId: string | null; window: WindowS;
  view: View; viewOverride: View | null; mode: Mode; scenario: string | null; scenarios: Scenario[];
  reducedMotion: boolean; connError: string | null; lastOkAt: number | null; recentExpanded: boolean; artifactsExpanded: boolean; evidence: EvidenceState;
}

const LS = "pitwall.prefs.v1";
function lsRead(): Record<string, unknown> { try { return JSON.parse(localStorage.getItem(LS) ?? "{}") as Record<string, unknown>; } catch { return {}; } }
function lsWrite(o: Record<string, unknown>): void { try { localStorage.setItem(LS, JSON.stringify(o)); } catch { /* private mode */ } }

function parseHash(): Record<string, string> {
  const out: Record<string, string> = {};
  const hsh = location.hash.replace(/^#/, "");
  if (!hsh.includes("=")) return out;
  for (const part of hsh.split("&")) { const i = part.indexOf("="); if (i > 0) out[part.slice(0, i)] = decodeURIComponent(part.slice(i + 1)); }
  return out;
}
const isWin = (n: number): n is WindowS => n === 60 || n === 300 || n === 900;
const isView = (v: unknown): v is View => v === "desktop" || v === "strip" || v === "narrow";

const prefs = lsRead();
const hash = parseHash();
const q = new URLSearchParams(location.search);
const qView = q.get("view");
const storedWin = Number(hash.window ?? prefs.window);
const storedMode = (hash.mode ?? prefs.mode) === "demo" ? "demo" : "live";

export const state: State = {
  snapshot: null, history: null,
  selectedTaskId: hash.task ?? (typeof prefs.task === "string" ? prefs.task : null),
  window: isWin(storedWin) ? storedWin : 300,
  view: "desktop",
  viewOverride: isView(qView) ? qView : isView(prefs.view) ? prefs.view : null,
  mode: storedMode,
  scenario: storedMode === "demo" ? (hash.scenario ?? (typeof prefs.scenario === "string" ? prefs.scenario : null)) : null,
  scenarios: [],
  reducedMotion: typeof prefs.reduced === "boolean" ? prefs.reduced : matchMedia("(prefers-reduced-motion: reduce)").matches,
  connError: null, lastOkAt: null, recentExpanded: false, artifactsExpanded: false,
  evidence: { open: false, taskId: null, index: null, loading: false, error: null, recordId: null, text: null, imageUrl: null, recordError: null, returnFid: null, focusDrawer: false, section: null },
};
state.view = autoView();

function autoView(): View { return state.viewOverride ?? (innerWidth < 900 ? "narrow" : "desktop"); }

type Listener = () => void;
const listeners: Listener[] = [];
let queued = false;
export function subscribe(fn: Listener): void { listeners.push(fn); }
export function notify(): void {
  if (queued) return; queued = true;
  queueMicrotask(() => { queued = false; listeners.forEach((l) => l()); });
}

function persist(): void {
  lsWrite({ task: state.selectedTaskId, window: state.window, view: state.viewOverride, mode: state.mode, scenario: state.scenario, reduced: state.reducedMotion });
  const parts = [`mode=${state.mode}`, `window=${state.window}`];
  if (state.selectedTaskId) parts.push(`task=${encodeURIComponent(state.selectedTaskId)}`);
  if (state.scenario) parts.push(`scenario=${encodeURIComponent(state.scenario)}`);
  try { history.replaceState(null, "", `${location.pathname}${location.search}#${parts.join("&")}`); } catch { /* ignore */ }
}

export function selectedTask(): Task | null {
  const sn = state.snapshot; if (!sn) return null;
  return sn.tasks.find((t) => t.id === state.selectedTaskId) ?? sn.tasks.find((t) => t.id === sn.default_task_id) ?? sn.tasks[0] ?? null;
}

// ---- actions
export function selectTask(id: string): void { state.selectedTaskId = id; persist(); notify(); }
export function setWindow(w: WindowS): void { state.window = w; state.history = null; persist(); notify(); void fetchHistory(); }
export function setView(v: View): void { state.viewOverride = v; state.view = v; persist(); notify(); }
export function setReduced(on: boolean): void { state.reducedMotion = on; persist(); notify(); }
export function toggleArtifacts(): void { state.artifactsExpanded = !state.artifactsExpanded; notify(); }
export function toggleRecent(): void { state.recentExpanded = !state.recentExpanded; notify(); }
export function setMode(m: Mode, scenario?: string | null): void {
  state.mode = m;
  state.scenario = m === "demo" ? (scenario ?? state.scenario ?? state.scenarios[0]?.id ?? null) : null;
  // Replace the whole state: live values must never survive on screen in demo, or the reverse.
  state.snapshot = null; state.history = null; state.connError = null; state.lastOkAt = null; closeEvidence(false);
  etag = null; persist(); notify(); void tick(true);
}
export function onResize(): void { const v = autoView(); if (v !== state.view) { state.view = v; notify(); } }

// ---- fetching
let etag: string | null = null;
const qs = () => `mode=${state.mode}${state.mode === "demo" && state.scenario ? `&scenario=${encodeURIComponent(state.scenario)}` : ""}`;
const keyNow = () => `${state.mode}|${state.scenario}`;

async function fetchSnapshot(): Promise<void> {
  const key = keyNow();
  try {
    const r = await fetch(`/api/snapshot?${qs()}`, { headers: etag ? { "If-None-Match": etag } : {}, cache: "no-cache" });
    if (key !== keyNow()) return;
    if (r.status === 304) { if (state.connError) { state.connError = null; notify(); } state.lastOkAt = Date.now(); return; }
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const sn = (await r.json()) as Snapshot;
    if (key !== keyNow()) return;
    etag = r.headers.get("etag");
    const prevSeq = state.snapshot?.seq;
    state.snapshot = sn; state.connError = null; state.lastOkAt = Date.now();
    if (prevSeq !== sn.seq || !state.history) void fetchHistory();
    notify();
  } catch (e) {
    if (key !== keyNow()) return;
    const msg = e instanceof Error ? e.message : String(e);
    if (state.connError !== msg) { state.connError = msg; notify(); }
  }
}
export async function fetchHistory(): Promise<void> {
  const key = keyNow(), win = state.window;
  try {
    const r = await fetch(`/api/history?window=${win}&${qs()}`, { cache: "no-cache" });
    if (!r.ok || key !== keyNow() || win !== state.window) return;
    state.history = (await r.json()) as History; notify();
  } catch { /* keep the previous history; the snapshot error path reports the outage */ }
}
async function fetchScenarios(): Promise<void> {
  try {
    const r = await fetch("/api/scenarios"); if (!r.ok) return;
    state.scenarios = ((await r.json()) as { scenarios: Scenario[] }).scenarios;
    if (state.mode === "demo" && !state.scenario && state.scenarios[0]) { state.scenario = state.scenarios[0].id; etag = null; persist(); void tick(true); }
    notify();
  } catch { /* ignore */ }
}
async function tick(now = false): Promise<void> { void now; await fetchSnapshot(); }

let timer: number | undefined;
export function start(): void {
  void fetchScenarios(); void tick();
  timer = window.setInterval(() => { if (!document.hidden) void tick(); }, 2000);
  window.setInterval(() => { if (!document.hidden && state.snapshot) void fetchHistory(); }, 10000);
  window.addEventListener("resize", onResize);
  window.addEventListener("hashchange", () => {
    const hh = parseHash(); let changed = false;
    if (hh.task && hh.task !== state.selectedTaskId) { state.selectedTaskId = hh.task; changed = true; }
    if (hh.window && isWin(Number(hh.window)) && Number(hh.window) !== state.window) { state.window = Number(hh.window) as WindowS; void fetchHistory(); changed = true; }
    if (changed) notify();
  });
  void timer;
}

// ---- evidence
export function openEvidence(taskId: string | null, recordId: string | null, returnFid: string | null, section: string | null = null): void {
  const e = state.evidence;
  Object.assign(e, { open: true, taskId, index: null, loading: state.mode === "live" && !!taskId, error: null, section, recordId: null, text: null, imageUrl: null, recordError: null, returnFid, focusDrawer: true });
  notify();
  if (state.mode !== "live" || !taskId) return;
  void (async () => {
    try {
      const r = await fetch(`/api/evidence/${encodeURIComponent(taskId)}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const idx = (await r.json()) as EvidenceIndex;
      if (!e.open || e.taskId !== taskId) return;
      e.index = idx; e.loading = false; notify();
      if (recordId) void openRecord(recordId);
    } catch (err) { e.loading = false; e.error = err instanceof Error ? err.message : String(err); notify(); }
  })();
}
export async function openRecord(recordId: string): Promise<void> {
  const e = state.evidence; if (!e.taskId) return;
  const taskId = e.taskId;
  Object.assign(e, { recordId, text: null, imageUrl: null, recordError: null });
  notify();
  const rec = e.index?.records.find((x) => x.record_id === recordId);
  const url = `/api/evidence/${encodeURIComponent(taskId)}/${encodeURIComponent(recordId)}`;
  if (rec?.kind === "image") { e.imageUrl = url; notify(); return; }
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const ct = r.headers.get("content-type") ?? "";
    if (ct.startsWith("image/")) { e.imageUrl = url; } else { e.text = await r.text(); }
    if (e.recordId === recordId) notify();
  } catch (err) { e.recordError = err instanceof Error ? err.message : String(err); notify(); }
}
export function closeEvidence(doNotify = true): void {
  const e = state.evidence; e.open = false; e.focusDrawer = false;
  if (doNotify) notify();
}
