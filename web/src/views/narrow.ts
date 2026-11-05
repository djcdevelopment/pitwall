import { h } from "../dom";
import { ch1, ch2, ch3, ch4, ch5, ch6, servicesCompact } from "../components/channels";
import { recentList, resultPanel } from "../components/resultCard";
import * as store from "../store";
import { state } from "../store";
import { banner, controls, ctxOf, demoBar, demoTag, freshness, hostDots, loading, pathBand, taskBar } from "./common";

const NAV: [string, string, string][] = [["sec-channels", "Channels", "M3 17l5-6 4 4 7-9"], ["sec-path", "Path", "M5 6h4v4H5zM15 14h4v4h-4zM9 8h6v8"], ["sec-evidence", "Evidence", "M6 3h9l4 4v14H6zM9 12h7M9 16h7"], ["sec-services", "Services", "M4 7h16M4 12h16M4 17h16"]];

function navIcon(d: string): SVGElement {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg"); svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("width", "20"); svg.setAttribute("height", "20");
  svg.setAttribute("aria-hidden", "true");
  const p = document.createElementNS(ns, "path"); p.setAttribute("d", d); p.setAttribute("fill", "none"); p.setAttribute("stroke", "currentColor"); p.setAttribute("stroke-width", "1.8");
  svg.appendChild(p); return svg;
}

export function narrow(): HTMLElement {
  const c = ctxOf();
  const root = h("div", { class: "view view-narrow" }, demoBar(),
    h("header", { class: "hdr" },
      h("div", { class: "hdr-row" }, h("span", { class: "brand" }, h("span", { class: "brand-dot", "aria-hidden": "true" }), "PITWALL"), demoTag(), hostDots(state.snapshot)),
      controls(), freshness(state.snapshot)), banner());
  if (!c) { root.appendChild(loading()); return root; }
  const open = (rec: string | null, fid: string) => c.task && store.openEvidence(c.task.id, rec, fid);
  root.append(taskBar(c.sn, c.task), pathBand(c.sn, c.task, open),
    h("div", { class: "grid-ch", id: "sec-channels" }, ch1(c), ch2(c), ch3(c), ch4(c), ch5(c), ch6(c, false)),
    h("div", { class: "bottom", id: "sec-evidence" },
      c.task ? resultPanel(c.task, open, state.artifactsExpanded, store.toggleArtifacts) : h("div", { class: "panel" }, "No task selected."),
      recentList(c.sn, c.task?.id ?? null, state.recentExpanded, store.selectTask, store.toggleRecent)),
    h("section", { class: "panel", id: "sec-services" }, h("div", { class: "panel-h" }, h("span", {}, "SERVICES")), servicesCompact(c)),
    h("nav", { class: "bnav", "aria-label": "Sections" },
      ...NAV.map(([id, label, d]) => h("a", { href: `#${id}`, class: "bnav-a", onclick: (e: Event) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: state.reducedMotion ? "auto" : "smooth", block: "start" }); } }, navIcon(d), h("span", {}, label)))));
  return root;
}
