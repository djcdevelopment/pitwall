import { h } from "../dom";
import type { Device, Snapshot, Task } from "../contract";
import { badge, fromActivity, fromOutcome, type Kind } from "../components/badge";
import { reading } from "../components/metric";
import { topology } from "../components/topology";
import { ribbon } from "../components/ribbon";
import type { Ctx } from "../components/channels";
import { ageSince, clock, fmtAge, fmtDur } from "../format";
import * as store from "../store";
import { state, selectedTask, type View } from "../store";

export function ctxOf(): Ctx | null {
  if (!state.snapshot) return null;
  const task = selectedTask();
  return { sn: state.snapshot, hist: state.history, task, details: (section, fid) => store.openEvidence(task?.id ?? null, null, fid, section) };
}
export const hostLabel = (sn: Snapshot) => (id: string | null): string => (id ? sn.hosts.find((x) => x.id === id)?.label ?? id : "host unknown");

export function demoTag(): HTMLElement | null {
  if (state.mode !== "demo") return null;
  return h("span", { class: "demo-tag", role: "status" }, `DEMO, ${state.scenario ?? "default scenario"}`);
}
export function demoBar(): HTMLElement | null { return state.mode === "demo" ? h("div", { class: "demo-bar", "aria-hidden": "true" }) : null; }

function seg<T extends string | number>(label: string, opts: { v: T; text: string }[], cur: T, on: (v: T) => void, fidp: string): HTMLElement {
  return h("div", { class: "segctl", role: "group", "aria-label": label },
    ...opts.map((o) => h("button", { type: "button", class: "btn", "aria-pressed": o.v === cur ? "true" : "false", "data-fid": `${fidp}-${o.v}`, onclick: () => on(o.v) }, o.text)));
}

export function exportSnapshot(): void {
  if (!state.snapshot) return;
  const blob = new Blob([JSON.stringify(state.snapshot, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  const a = h("a", { href: url, download: `pitwall-${state.mode}${state.scenario ? "-" + state.scenario : ""}-${ts}.json` });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function controls(): HTMLElement {
  const wrap = h("div", { class: "controls" });
  wrap.appendChild(seg<"live" | "demo">("Data mode", [{ v: "live", text: "Live" }, { v: "demo", text: "Demo" }], state.mode, (m) => store.setMode(m), "mode"));
  if (state.mode === "demo") {
    const sel = h("select", { class: "btn sel", "aria-label": "Demo scenario", "data-fid": "scenario", onchange: (e: Event) => store.setMode("demo", (e.target as HTMLSelectElement).value) });
    const list = state.scenarios.length ? state.scenarios : state.scenario ? [{ id: state.scenario, note: "" }] : [];
    for (const sc of list) { const o = h("option", { value: sc.id, title: sc.note }, sc.id); if (sc.id === state.scenario) o.selected = true; sel.appendChild(o); }
    wrap.appendChild(sel);
  }
  wrap.appendChild(seg<number>("Time window", [{ v: 60, text: "1m" }, { v: 300, text: "5m" }, { v: 900, text: "15m" }], state.window, (w) => store.setWindow(w as store.WindowS), "win"));
  wrap.appendChild(seg<View>("Layout", [{ v: "desktop", text: "Desktop" }, { v: "strip", text: "Strip" }, { v: "narrow", text: "Narrow" }], state.view, (v) => store.setView(v), "view"));
  wrap.appendChild(h("button", { type: "button", class: "btn", "aria-pressed": state.reducedMotion ? "true" : "false", "data-fid": "motion", onclick: () => store.setReduced(!state.reducedMotion) }, "Reduce motion"));
  wrap.appendChild(h("button", { type: "button", class: "btn", "data-fid": "export", disabled: state.snapshot ? null : true, onclick: exportSnapshot }, "Export"));
  return wrap;
}

export function hostDots(sn: Snapshot | null): HTMLElement {
  const w = h("div", { class: "hosts", "aria-label": "Hosts" });
  if (!sn) return w;
  for (const x of sn.hosts) w.appendChild(h("span", { class: "host", title: x.role }, h("span", { class: "hn" }, x.label), badge(fromActivity(x.state), x.state, "compact")));
  return w;
}

/** Freshness per source; age is ticked in place by main.ts, no re-render. */
export function freshness(sn: Snapshot | null, collectorsOnly = false): HTMLElement {
  const w = h("div", { class: "fresh", "aria-label": "Source freshness" });
  if (!sn) return w;
  if (state.mode === "demo") { w.appendChild(h("span", { class: "src dim" }, "fixture data, no live sources")); return w; }
  for (const so of sn.sources) {
    if (collectorsOnly && so.id === "receipts") continue;
    let age: HTMLElement;
    if (so.observed_at) age = h("span", { class: "age", "data-since": String(Date.parse(so.observed_at)) }, fmtAge(ageSince(so.observed_at) ?? 0));
    else if (so.read_at) age = h("span", { class: "age", "data-since": String(Date.parse(so.read_at)) }, fmtAge(ageSince(so.read_at) ?? 0));
    else age = h("span", { class: "dim" }, "not read yet");
    w.appendChild(h("span", { class: "src", title: `${so.path}${so.last_error ? " | " + so.last_error : ""}` },
      badge(fromActivity(so.state), so.label, "compact"), " ", age));
  }
  return w;
}

export function banner(): HTMLElement | null {
  if (!state.connError) return null;
  const age = state.lastOkAt ? `last good data ${fmtAge((Date.now() - state.lastOkAt) / 1000)} ago` : "no data received yet";
  return h("div", { class: "banner", role: "alert" }, badge("unreachable", "Pitwall server unreachable"), ` ${state.connError}; ${age}. Values below are retained, not current.`);
}

export function exceptionBox(sn: Snapshot): HTMLElement {
  const e = sn.exception;
  if (!e) return h("div", { class: "exc exc-none" }, h("span", { class: "lab" }, "Exception"), h("span", { class: "glyph", "aria-hidden": "true" }, "✓"), " No exceptions");
  const kind: Kind = e.level === "failed" ? "failed" : e.level === "unreachable" ? "unreachable" : e.level === "stale" ? "stale" : "attention";
  const red = e.level === "failed" || e.level === "unreachable";
  return h("div", { class: `exc ${red ? "exc-red" : "exc-amber"}`, role: "status" }, h("span", { class: "lab" }, "Exception"), badge(kind, e.level),
    h("span", { class: "exc-t" }, e.text), h("span", { class: "dim exc-s" }, e.source));
}

export function activeRate(sn: Snapshot): HTMLElement | null {
  const act = sn.seats.filter((s) => s.state === "active" && typeof s.generation_rate.value === "number");
  if (act.length === 0) return null;
  return h("div", { class: "rate" }, h("span", { class: "lab" }, "Generation"), ...act.map((s) => h("span", {}, reading(s.generation_rate), h("span", { class: "dim" }, ` ${s.label}`))));
}

export function taskBar(sn: Snapshot, t: Task | null): HTMLElement {
  if (!t) return h("section", { class: "taskbar" }, h("span", { class: "empty-note" }, "No task reported."), h("div", { class: "tb-r" }, exceptionBox(sn)));
  const prog = ageSince(t.latest_progress_at);
  const durs = h("div", { class: "durs", "aria-label": "Scoped durations" },
    ...t.durations.map((d) => h("span", { class: "dur", title: `${d.label}: ${d.scope_note}` }, h("span", { class: "dur-l" }, d.label), " ", h("b", {}, fmtDur(d.seconds)))));
  return h("section", { class: "taskbar", "aria-label": "Selected task" },
    h("div", { class: "tb-1" },
      h("div", { class: "tb-out", title: "Task outcome (historical), not service state" }, h("span", { class: "lab" }, "Task outcome"), badge(fromOutcome(t.outcome.state), t.outcome.label || t.outcome.state)),
      h("div", { class: "tb-title ellip", title: t.title }, t.title),
      h("div", { class: "tb-r" }, activeRate(sn), exceptionBox(sn))),
    h("div", { class: "tb-2" },
      h("div", { class: "tb-prog ellip", title: t.latest_progress }, h("span", { class: "arrow", "aria-hidden": "true" }, "\u2192"), " ", t.latest_progress || "no progress recorded", prog !== null ? h("span", { class: "dim" }, ` (${fmtAge(prog)} ago)`) : null),
      durs.childElementCount ? durs : null));
}

export function pathBand(sn: Snapshot, t: Task | null, onOpen: (rec: string | null, fid: string) => void): HTMLElement {
  if (!t) return h("section", { class: "panel pathband", id: "sec-path" }, h("div", { class: "empty-note" }, "No task selected."));
  return h("section", { class: "panel pathband", id: "sec-path", "aria-label": "Observed path" },
    h("div", { class: "panel-h" }, h("span", {}, `OBSERVED PATH, ${t.short_title}`), h("span", { class: "dim" }, "this task's receipts only; click a node for evidence")),
    topology(t, hostLabel(sn), (hop) => onOpen(hop.evidence_record, `hop-${t.path.indexOf(hop)}`)),
    ribbon(t));
}

export function loading(): HTMLElement {
  return h("div", { class: "panel loading", role: "status" }, state.connError ? `Waiting for Pitwall server: ${state.connError}` : "Loading snapshot...");
}

export function worstDevices(sn: Snapshot): { peak: { d: Device; v: number } | null; mem: { d: Device; used: number; total: number } | null } {
  let peak: { d: Device; v: number } | null = null, mem: { d: Device; used: number; total: number } | null = null;
  for (const d of sn.devices) {
    if (typeof d.utilization.value === "number" && (!peak || d.utilization.value > peak.v)) peak = { d, v: d.utilization.value };
    const u = d.memory_used.value, tt = d.memory_total.value;
    if (typeof u === "number" && typeof tt === "number" && tt > 0 && (!mem || u / tt > mem.used / mem.total)) mem = { d, used: u, total: tt };
  }
  return { peak, mem };
}
void clock;
