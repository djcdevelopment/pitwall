import { h } from "../dom";
import type { Snapshot, Task } from "../contract";
import type { EvidenceState } from "../store";
import { badge, fromActivity, fromParticipation } from "./badge";
import { fmtBytes } from "../format";
import { servicesList } from "./channels";

export interface EvActions { close(): void; openRecord(id: string): void }

/** Right-side drawer (full-screen in narrow). Focus trap and Esc are wired by main.ts. */
export function evidencePanel(ev: EvidenceState, sn: Snapshot, task: Task | null, mode: "live" | "demo", a: EvActions): HTMLElement {
  const body = h("div", { class: "ev-body" });
  const notes: string[] = [];
  const hops = h("section", { class: "ev-sec", "data-sec": "details" }, h("h3", {}, task ? `Selected task details: ${task.short_title}` : "Details"));
  if (!task) hops.appendChild(h("p", { class: "empty-note" }, "No task selected."));
  if (task) {
    hops.appendChild(h("h4", {}, "Observed path, basis for every hop"));
    if (task.path.length === 0) hops.appendChild(h("p", { class: "empty-note" }, "No hops."));
    for (const hop of task.path) hops.appendChild(h("div", { class: "ev-hop" },
      h("div", { class: "ev-hop-h" }, h("b", {}, hop.label), badge(fromParticipation(hop.state), hop.state)),
      h("div", { class: "ev-line" }, hop.summary),
      h("div", { class: "ev-line dim" }, "basis: ", hop.basis || "none recorded")));
    const cx = task.context, d = task.duckdb;
    const add = (l: string, v: string) => { if (v) notes.push(`${l}: ${v}`); };
    add("Pack cache", task.caches.pack_cache.note); add("AST/RAM", task.caches.ast_ram.note); add("Cached input tokens or prefix reuse, per job", task.caches.model_kv.note);
    add("Context concept", cx.concept); add("Selected pack sha256", cx.selected_pack_sha256); add("Comparison", cx.comparison_note);
    add("DuckDB source snapshot read", d.source_snapshot_detail); add("DuckDB transition written", d.transition_written_detail); add("DuckDB transition read back", d.transition_read_back_detail);
    for (const du of task.durations) add(`Duration, ${du.label}`, du.scope_note);
    add("Task", task.title);
    for (const c of cx.corrections) notes.push(`${c.field}: ${c.displayed_value} \u2014 ${c.basis_label || "corrected"}; producer record: ${c.producer_value}. Source: ${c.source} ${c.note}`);
  }
  for (const e of sn.engine_caches) if (e.hit.note) notes.push(`Engine KV ${e.label}: ${e.hit.note}`);
  for (const n of sn.network) notes.push(`${n.label}: ${n.latency.note || "no note"}`);
  if (notes.length) { hops.appendChild(h("h4", {}, "Measurement notes")); const l = h("ul", { class: "plain" }); for (const n of notes) l.appendChild(h("li", {}, n)); hops.appendChild(l); }
  body.appendChild(hops);
  const recs = h("section", { class: "ev-sec", "data-sec": "records" }, h("h3", {}, "Records"));
  if (mode === "demo") recs.appendChild(h("p", { class: "ev-warn" }, "Evidence is unavailable in demo mode: demo scenarios have no run directories to inspect."));
  else if (ev.loading) recs.appendChild(h("p", {}, "Loading records..."));
  else if (ev.error) recs.appendChild(h("p", { class: "ev-err" }, `Could not load evidence: ${ev.error}`));
  else if (ev.index) {
    if (ev.index.records.length === 0) recs.appendChild(h("p", { class: "empty-note" }, "No served records for this task."));
    const ul = h("ul", { class: "ev-recs" });
    for (const r of ev.index.records) ul.appendChild(h("li", {}, h("button", {
      type: "button", class: `ev-rec${ev.recordId === r.record_id ? " sel" : ""}`, "data-fid": `rec-${r.record_id}`, onclick: () => a.openRecord(r.record_id),
    }, h("span", { class: "rn" }, r.name), h("span", { class: "dim" }, `${r.kind} | ${fmtBytes(r.bytes)}`))));
    recs.appendChild(ul);
    if (ev.recordId) {
      recs.appendChild(h("h4", {}, ev.index.records.find((r) => r.record_id === ev.recordId)?.name ?? ev.recordId));
      if (ev.recordError) recs.appendChild(h("p", { class: "ev-err" }, `Could not read record: ${ev.recordError}`));
      else if (ev.imageUrl) recs.appendChild(h("img", { class: "ev-img", src: ev.imageUrl, alt: `Evidence image ${ev.recordId}` }));
      else if (ev.text !== null) recs.appendChild(h("pre", { class: "ev-pre", tabindex: 0 }, ev.text));
      else recs.appendChild(h("p", {}, "Loading record..."));
    }
    const ns = h("div", { class: "ev-ns" }, h("h4", {}, "Not served (names only)"));
    if (ev.index.not_served.length === 0) ns.appendChild(h("p", { class: "empty-note" }, "None."));
    else { const l = h("ul", { class: "plain" }); for (const n of ev.index.not_served) l.appendChild(h("li", {}, n)); ns.appendChild(l); }
    recs.appendChild(ns);
  }
  body.appendChild(recs);
  const svcs = h("section", { class: "ev-sec", "data-sec": "services" });
  if (sn.campaign) {
    const c = sn.campaign;
    svcs.appendChild(h("h3", {}, "Steppewise + Consul (M0\u2013M8) Campaign & Deployment Boundaries"));
    svcs.appendChild(h("div", { class: "ev-hop" },
      h("div", { class: "ev-hop-h" }, h("b", {}, c.title), badge("attention", `verdict: ${c.verdict}`)),
      h("div", { class: "ev-line" }, `Deployed to HEARTH :8710: ${c.deployed_commits} | ${c.deployed_hashes_verified}`),
      h("div", { class: "ev-line" }, `Live Consul control plane: ${c.active_units} | ${c.passing_seats}`),
      h("div", { class: "ev-line" }, `M5 Stage 4 (300s): ${c.stage4_draws ?? 0} successes (${c.stage4_rate_per_min ?? 0}/min), ${c.stage4_duplicate_terminals ?? 0} dupes, ${c.stage4_reconciled_acks ?? 0} lost ACKs reconciled`),
      h("div", { class: "ev-line dim" }, `Stage 4 GPU >50% gate: ${c.stage4_util_gate}`),
      h("div", { class: "ev-line dim" }, `Stage 4 scope: ${c.stage4_note}`),
      c.h3_backup_warning ? h("div", { class: "ev-line ev-warn" }, c.h3_backup_warning) : null));
    for (const m of c.milestones) {
      const bk = (["completed", "active", "attention", "unknown", "failed", "stale", "idle"].includes(m.badge) ? m.badge : "unknown") as Parameters<typeof badge>[0];
      svcs.appendChild(h("div", { class: "ev-hop" },
        h("div", { class: "ev-hop-h" }, h("b", {}, m.label), badge(bk, m.state)),
        h("div", { class: "ev-line" }, m.summary),
        m.limits ? h("div", { class: "ev-line dim" }, "boundary: ", m.limits) : null));
    }
  }
  svcs.appendChild(h("h3", {}, "Services, now"));
  svcs.appendChild(servicesList({ sn, hist: null, task, details: () => undefined }));
  body.appendChild(svcs);
  const srcs = h("section", { class: "ev-sec", "data-sec": "sources" }, h("h3", {}, "Sources and collector versions"),
    h("p", { class: "ev-warn" }, "Collectors are external checkouts. Pitwall's clean Git status does not pin them, so these readings are not reproducible from a Pitwall commit alone."));
  for (const so of sn.sources) {
    const v = so.version;
    const access = so.path === "self_refresh" ? "invoked the collector (--dump-json)" : so.path === "tui_cache" ? "read its cached snapshot; writer not identified" : so.path === "fixture" ? "committed fixture" : so.path === "direct_probes" ? "Pitwall's own probes: TCP connect, HTTP GET and docker inspect of container state" : "read run-directory receipts";
    const version = !v ? null : v.commit ? `commit ${v.commit}, ${v.dirty === null ? "dirty state unknown" : v.dirty ? `dirty, ${v.changed_files.length} changed` : "clean"}` : "commit unknown";
    srcs.appendChild(h("div", { class: "ev-hop" },
      h("div", { class: "ev-hop-h" }, h("b", {}, so.label), badge(fromActivity(so.state), so.state)),
      h("div", { class: "ev-line" }, `Access: ${access}`),
      so.last_error ? h("div", { class: "ev-line ev-err" }, `Last error: ${so.last_error}`) : null,
      version ? h("div", { class: "ev-line" }, `Version: ${version}`) : null,
      v ? h("div", { class: "ev-line dim" }, `${v.repo}${v.checked_at ? `, checked ${v.checked_at}` : ""}`) : null,
      v?.changed_files.length ? h("div", { class: "ev-line dim" }, v.changed_files.join(", ")) : null,
      v?.note ? h("div", { class: "ev-line dim" }, v.note) : null));
  }
  body.appendChild(srcs);
  const cov = h("section", { class: "ev-sec", "data-sec": "coverage" }, h("h3", {}, "Coverage notes"));
  if (sn.coverage_notes.length === 0) cov.appendChild(h("p", { class: "empty-note" }, "None reported."));
  else { const l = h("ul", { class: "plain" }); for (const n of sn.coverage_notes) l.appendChild(h("li", {}, n)); cov.appendChild(l); }
  body.appendChild(cov);
  return h("div", { class: "ev-scrim", "data-scrim": "1", onclick: (e: Event) => { if ((e.target as HTMLElement).dataset.scrim) a.close(); } },
    h("aside", { class: "ev-drawer", role: "dialog", "aria-modal": "true", "aria-label": `Evidence for ${task?.short_title ?? ev.taskId ?? "task"}` },
      h("header", { class: "ev-h" }, h("div", {}, h("span", { class: "lab" }, "EVIDENCE"), h("div", { class: "ev-title" }, task?.short_title ?? ev.taskId ?? "")),
        h("button", { type: "button", class: "btn", id: "ev-close", "data-fid": "ev-close", onclick: () => a.close() }, "Close (Esc)")),
      body));
}
