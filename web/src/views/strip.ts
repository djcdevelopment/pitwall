import { h } from "../dom";
import type { Snapshot } from "../contract";
import { badge, fromActivity, fromOutcome } from "../components/badge";
import { reading } from "../components/metric";
import { fmtNum } from "../format";
import * as store from "../store";
import { state, selectedTask } from "../store";
import { banner, demoBar, demoTag, exceptionBox, freshness, loading, worstDevices } from "./common";

function tile(label: string, value: Node | string, sub: string): HTMLElement {
  return h("div", { class: "tile" }, h("span", { class: "lab" }, label), h("span", { class: "tile-v" }, value), h("span", { class: "tile-s dim" }, sub));
}
function instruments(sn: Snapshot): HTMLElement[] {
  const { peak, mem } = worstDevices(sn);
  const seats = sn.seats, known = seats.filter((s) => s.occupancy.numerator !== null);
  const busy = known.filter((s) => (s.occupancy.numerator ?? 0) > 0).length;
  const rates = seats.filter((s) => typeof s.generation_rate.value === "number");
  const total = rates.reduce((a, s) => a + (s.generation_rate.value as number), 0);
  return [
    tile("Peak GPU util", peak ? reading(peak.d.utilization) : reading(null), peak ? peak.d.title : "no device reading"),
    tile("Highest memory", mem ? h("span", { class: "rd rd-ok" }, h("span", { class: "rd-val" }, `${fmtNum(mem.used, 1)}/${fmtNum(mem.total, 1)}`), h("span", { class: "rd-unit" }, ` ${mem.d.memory_total.unit}`)) : reading(null), mem ? mem.d.title : "no device reading"),
    tile("Seats occupied", known.length ? h("span", { class: "rd rd-ok" }, h("span", { class: "rd-val" }, `${busy}/${seats.length}`)) : reading(null), known.length ? "seats with active requests" : "occupancy unknown"),
    tile("Generation rate", rates.length ? h("span", { class: "rd rd-ok" }, h("span", { class: "rd-val" }, fmtNum(total, 1)), h("span", { class: "rd-unit" }, " tok/s")) : reading(null), rates.length ? `sum of ${rates.length} seat${rates.length > 1 ? "s" : ""}` : "no seat reading"),
  ];
}

export function strip(): HTMLElement {
  const root = h("div", { class: "view view-strip" }, demoBar());
  const sn = state.snapshot;
  if (!sn) { root.appendChild(loading()); return root; }
  const t = selectedTask();
  const working = t?.stages.find((x) => x.state === "working" || x.state === "waiting" || x.state === "attention");
  const stage = t ? (working ? `${working.state}: ${working.label}` : t.stage || "no stage") : "no task";
  root.append(
    h("div", { class: "strip-a" },
      h("span", { class: "brand" }, h("span", { class: "brand-dot", "aria-hidden": "true" }), "PITWALL"),
      badge(fromActivity(sn.overall.state), sn.overall.state),
      sn.overall.headline && sn.overall.headline.toLowerCase() !== sn.overall.state ? h("button", { type: "button", class: "hl", title: `${sn.overall.headline}. ${sn.overall.reason}`, "aria-expanded": "false", onclick: (e: Event) => { const b = e.currentTarget as HTMLElement; b.setAttribute("aria-expanded", String(b.getAttribute("aria-expanded") !== "true")); } }, sn.overall.headline, h("span", { class: "hl-full" }, `${sn.overall.headline}. ${sn.overall.reason}`)) : null,
      h("span", { class: "strip-task", title: t?.title ?? "" }, t?.short_title ?? "no task"),
      t ? badge(fromOutcome(t.outcome.state), t.outcome.label || t.outcome.state, "compact") : null,
      h("span", { class: "strip-stage", title: t?.attention || t?.latest_progress || "" }, `${stage}${t?.attention ? " | " + t.attention : ""}`),
      demoTag(), h("span", { class: "grow" }), freshness(sn, true),
      h("button", { type: "button", class: "btn", "data-fid": "expand", title: "Switches this page to the desktop layout. It does not resize the window.", onclick: () => store.setView("desktop") }, "Expand")),
    h("div", { class: "strip-x" }, exceptionBox(sn)),
    h("div", { class: "strip-b" }, ...instruments(sn)));
  const b = banner(); if (b) root.appendChild(b);
  return root;
}
