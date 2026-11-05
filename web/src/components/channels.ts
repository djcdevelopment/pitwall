import { h } from "../dom";
import type { Device, History, Measurement, Seat, Service, Snapshot, Task } from "../contract";
import { fmtAge, fmtNum, shortSha } from "../format";
import { badge, fromActivity, fromStep, STEP_TEXT } from "./badge";
import { hasRatio, reading, readingPair } from "./metric";
import { noRatio, ring } from "./ring";
import { segbar } from "./segbar";
import { trend } from "./trend";
import { linkEl } from "./resultCard";

export interface Ctx { sn: Snapshot; hist: History | null; task: Task | null; details: (section: string, fid: string) => void }

function detailsBtn(c: Ctx, section: string, fid: string, label = "Details"): HTMLElement {
  return h("button", { type: "button", class: "mini-btn", "data-fid": fid, "aria-label": `${label}: open evidence drawer`, onclick: () => c.details(section, fid) }, label);
}
function card(c: Ctx, id: string, num: number, title: string, right: Node | null, ...kids: (Node | null)[]): HTMLElement {
  void c;
  return h("section", { class: "panel ch", id, "aria-labelledby": `${id}-t` },
    h("div", { class: "panel-h" }, h("span", { id: `${id}-t` }, h("span", { class: "chn" }, `CH-${num}`), ` ${title}`), right),
    ...kids);
}
const hostDevs = (sn: Snapshot, re: RegExp) => sn.devices.filter((d) => re.test(d.host_id) || re.test(d.id));

function deviceBlock(d: Device, hist: History | null, color: "green" | "cyan"): HTMLElement {
  const um = d.memory_used, tm = d.memory_total;
  const memOk = typeof um.value === "number" && typeof tm.value === "number" && tm.value > 0;
  return h("div", { class: "dev", title: [d.mode, d.workload, d.owner].filter(Boolean).join(" | ") },
    h("div", { class: "dev-h" }, h("div", { class: "dev-t" }, h("b", {}, d.title)), badge(fromActivity(d.state), d.state, "compact")),
    h("div", { class: "dev-body" },
      trend(hist, { key: `device.${d.id}.utilization`, unit: "%", yMax: 100, color, label: `${d.title} utilization` }),
      h("div", { class: "dev-read" },
        h("div", { class: "dev-u" }, h("span", { class: "lab" }, "Util"), reading(d.utilization, { big: true, short: true })),
        h("div", { class: "kv" }, h("span", { class: "k" }, "Mem"), h("span", { class: "v" }, readingPair(um, tm))),
        memOk ? segbar(um.value as number, tm.value as number, { color: "cyan", label: `${d.title} memory used of total`, pips: 24 }) : segbar(null, null, { label: `${d.title} memory` }),
        h("div", { class: "dev-pt" }, h("span", {}, h("span", { class: "k" }, "Pwr "), readingPair(d.power, d.power_limit)), h("span", {}, h("span", { class: "k" }, "Temp "), readingPair(d.temp_core, d.temp_mem))))));
}

function devicesCard(ctx: Ctx, id: string, n: number, title: string, re: RegExp, hostRe: RegExp, ...extra: Node[]): HTMLElement {
  const devs = hostDevs(ctx.sn, re);
  const host = ctx.sn.hosts.find((x) => hostRe.test(x.id) || hostRe.test(x.label));
  return card(ctx, id, n, title, host ? badge(fromActivity(host.state), `host ${host.state}`) : null,
    ...(devs.length ? devs.map((d, i) => deviceBlock(d, ctx.hist, i % 2 ? "cyan" : "green")) : [h("div", { class: "empty-note" }, "No devices reported for this host.")]), ...extra);
}
export const ch1 = (c: Ctx) => devicesCard(c, "ch1", 1, "OMEN GPUs", /omen/i, /omen/i);
export const ch2 = (c: Ctx) => devicesCard(c, "ch2", 2, "AM4 GPUs", /am4/i, /am4/i);

export function ch3(c: Ctx): HTMLElement {
  const svc = c.sn.services.find((s: Service) => /npu|jepa|context/i.test(`${s.id} ${s.name}`));
  return devicesCard(c, "ch3", 3, "FX99 and NPU", /fx99/i, /fx99/i,
    h("div", { class: "npu", title: svc ? `${svc.responsibility}. ${svc.detail}` : "" },
      h("b", {}, svc ? svc.name : "NPU / context service"), svc ? badge(fromActivity(svc.state), `now: ${svc.state}`, "compact") : badge("unknown", "unknown", "compact")));
}

function seatRow(s: Seat, hist: History | null): HTMLElement {
  const occ = s.occupancy;
  const occTxt = occ.numerator !== null && occ.denominator !== null ? `${fmtNum(occ.numerator)}/${fmtNum(occ.denominator)} reqs` : "? reqs";
  return h("div", { class: "seat", title: `${s.health} | ${s.context_tokens ?? "?"} ctx` },
    h("div", { class: "seat-n" }, h("b", {}, s.label), h("span", { class: "seat-m" }, badge(fromActivity(s.state), s.state, "compact"), h("span", { class: "dim ellip" }, s.model))),
    trend(hist, { key: `seat.${s.id}.generation_rate`, unit: "tok/s", color: "cyan", label: `${s.label} generation rate` }),
    h("div", { class: "seat-r" }, reading(s.generation_rate, { short: true })),
    h("div", { class: "seat-o" }, h("span", {}, occTxt), segbar(occ.numerator, occ.denominator, { color: "cyan", label: `${s.label} slots occupied`, pips: 8 })),
    h("div", { class: "seat-q", title: "Queue depth: backlog only, not occupancy" }, h("span", { class: "k" }, "queue "), reading(s.queued, { short: true, unitOverride: "" })));
}
export function ch4(c: Ctx): HTMLElement {
  return card(c, "ch4", 4, "Generation rate", null,
    ...(c.sn.seats.length ? c.sn.seats.map((s) => seatRow(s, c.hist)) : [h("div", { class: "empty-note" }, "No serving seats reported.")]),
    h("div", { class: "foot dim" }, "Sparkline tok/s over window. Queue is backlog; occupancy active/slots."));
}

function line(label: string, scope: string | null, value: Node, m?: Measurement | null, col: "green" | "cyan" = "green"): HTMLElement {
  return h("div", { class: "cl", title: m?.note || undefined },
    m && hasRatio(m) ? ring(m.numerator, m.denominator, col, label, 22) : null,
    h("span", { class: "k" }, label), scope ? h("em", { class: "scope-tag" }, scope) : null, h("span", { class: "grow" }), value);
}
function cacheVal(m: Measurement | null): HTMLElement {
  if (m && m.denominator === 0 && m.numerator === 0) return noRatio("0/0, no ratio");
  if (m && typeof m.value === "boolean") return h("span", { class: "rd rd-ok" }, h("span", { class: "rd-val" }, m.value ? "hit" : "miss"));
  const w = h("span", {}, reading(m));
  if (m && hasRatio(m)) w.append(h("span", { class: "dim" }, ` ${fmtNum(m.numerator)}/${fmtNum(m.denominator)}`));
  return w;
}
/** Cold and warm timings from the pack-cache receipt, shown on the face with their scope. */
function packTimings(m: Measurement | null | undefined): HTMLElement | null {
  const hit = m?.note.match(/cold ([\d.]+) ms, warm ([\d.]+) ms/);
  if (!hit) return null;
  return h("div", { class: "cl dim cr-n" }, `cold ${Number(hit[1]).toFixed(2)} ms, warm ${Number(hit[2]).toFixed(2)} ms (one receipt)`);
}
const bytesEl = (m: Measurement): HTMLElement => typeof m.value === "number" ? h("span", { class: "rd rd-ok" }, h("span", { class: "rd-val" }, fmtNum(m.value)), h("span", { class: "rd-unit" }, " B")) : reading(m);

export function ch5(c: Ctx): HTMLElement {
  const t = c.task;
  const left: (Node | null)[] = [
    line("Pack cache", "job", cacheVal(t?.caches.pack_cache ?? null), t?.caches.pack_cache, "green"),
    packTimings(t?.caches.pack_cache),
    line("AST/RAM", "job", cacheVal(t?.caches.ast_ram ?? null), t?.caches.ast_ram, "green"),
    line("Cached input", "job", cacheVal(t?.caches.model_kv ?? null), t?.caches.model_kv, "cyan"),
    h("div", { class: "cl cl-h" }, h("span", { class: "k" }, "Engine/daemon uptime, not per job")),
  ];
  if (c.sn.engine_caches.length === 0) left.push(line("no engine counters", null, reading(null)));
  for (const e of c.sn.engine_caches) left.push(line(e.id === "npu_ast_arena" ? "NPU AST arena" : `${e.id} KV`, null, cacheVal(e.hit), e.hit, "cyan"));
  const right: Node[] = [h("div", { class: "cl cl-h" }, h("span", { class: "k" }, "Context pack"))];
  if (t) {
    const cx = t.context;
    right.push(line("HEARTH input bytes", null, bytesEl(cx.hearth_input)), line("Selected pack bytes", null, bytesEl(cx.selected_pack)));
    const fact = (label: string, m: Measurement, field: string) => {
      const corr = cx.corrections.find((x) => x.field === field);
      const txt = corr ? corr.displayed_value : m.numerator !== null && m.denominator !== null ? `${m.numerator}/${m.denominator}` : "unknown";
      const out: Node[] = [line(label, null, h("span", { class: m.numerator === null && !corr ? "rd rd-unknown" : "rd rd-ok" }, txt))];
      if (corr) out.push(
        h("div", { class: "cl corr", title: corr.source }, h("span", { class: "amb" }, `${corr.displayed_value} \u2014 ${corr.basis_label || "corrected"}`)),
        h("div", { class: "cl corr" }, h("span", { class: "dim" }, `producer record: ${corr.producer_value}`)));
      return out;
    };
    right.push(...fact("Facts selected", cx.required_facts_selected, "required_facts_selected"), ...fact("Facts baseline", cx.required_facts_baseline, "required_facts_baseline"));
  } else right.push(h("div", { class: "empty-note" }, "No task selected."));
  return card(c, "ch5", 5, "Context and caches", detailsBtn(c, "details", "det-ch5"), h("div", { class: "cols2" }, h("div", { class: "colx" }, ...left.filter((x): x is Node => x !== null)), h("div", { class: "colx" }, ...right)));
}

export function servicesCompact(c: Ctx): HTMLElement {
  const list = h("ul", { class: "svc2" });
  for (const s of c.sn.services) list.appendChild(h("li", { title: `${s.name}: ${s.detail}` }, h("span", { class: "svc2-n ellip" }, s.name), badge(fromActivity(s.state), s.state, "compact")));
  if (c.sn.services.length === 0) list.appendChild(h("li", { class: "empty-note" }, "No services reported."));
  return h("div", { class: "svcwrap" },
    h("div", { class: "cl cl-h" }, h("span", { class: "k", title: "Current state. A completed historical task does not imply a service is reachable now." }, "Services, now"), h("span", { class: "grow" }), detailsBtn(c, "services", "det-svc")), list);
}

export function servicesList(c: Ctx): HTMLElement {
  const list = h("ul", { class: "svcs" });
  for (const s of c.sn.services) {
    const a = s.age_s;
    list.appendChild(h("li", { class: "svc" },
      h("div", { class: "svc-h" }, h("b", {}, s.name), badge(fromActivity(s.state), `now: ${s.state}`)),
      h("div", { class: "dim" }, `${s.responsibility}${s.endpoint ? ` | ${s.endpoint}` : ""}`),
      h("div", { class: "dim" }, s.detail, a !== null ? ` (${fmtAge(a)} ago, ${s.source})` : ""),
      s.link ? linkEl(s.link) : null));
  }
  if (c.sn.services.length === 0) list.appendChild(h("li", { class: "empty-note" }, "No services reported."));
  return h("div", { class: "svcwrap" }, h("p", { class: "own" }, "Service state is current and independent of any task. A completed historical task does not mean a service is reachable now."), list);
}

export function ch6(c: Ctx, withServices: boolean): HTMLElement {
  const t = c.task;
  const left: Node[] = [];
  if (t) {
    const d = t.duckdb;
    const st = (label: string, s: typeof d.source_snapshot_read, det: string) => h("div", { class: "cl", title: det || undefined }, h("span", { class: "k" }, label), h("span", { class: "grow" }), badge(fromStep(s), STEP_TEXT[s], "compact"));
    left.push(h("div", { class: "cl cl-h" }, h("span", { class: "k" }, "DuckDB steps")),
      st("Source snapshot read", d.source_snapshot_read, d.source_snapshot_detail), st("Transition written", d.transition_written, d.transition_written_detail), st("Transition read back", d.transition_read_back, d.transition_read_back_detail));
  } else left.push(h("div", { class: "empty-note" }, "No task selected."));
  left.push(h("div", { class: "cl cl-h" }, h("span", { class: "k" }, "Network")));
  if (c.sn.network.length === 0) left.push(h("div", { class: "cl" }, h("span", { class: "k" }, "OMEN-AM4 Network latency"), h("span", { class: "grow" }), reading(null)));
  for (const l of c.sn.network) left.push(h("div", { class: "cl nl", title: l.latency.note || undefined }, h("span", { class: "k" }, l.label), h("span", { class: "grow" }), reading(l.latency)),
    l.latency.note ? h("div", { class: "dim cr-n ellip", title: l.latency.note }, l.latency.note) : h("span"));
  if (!withServices) return card(c, "ch6", 6, "Data and network", detailsBtn(c, "details", "det-ch6"), ...left);
  return card(c, "ch6", 6, "Data and network", detailsBtn(c, "details", "det-ch6"), h("div", { class: "cols2 cols-ch6" }, h("div", { class: "colx" }, ...left), h("div", { class: "colx" }, servicesCompact(c))));
}
void shortSha;
