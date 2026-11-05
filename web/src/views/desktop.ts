import { h } from "../dom";
import { ch1, ch2, ch3, ch4, ch5, ch6 } from "../components/channels";
import { recentList, resultPanel } from "../components/resultCard";
import * as store from "../store";
import { state } from "../store";
import { banner, controls, ctxOf, demoBar, demoTag, freshness, hostDots, loading, pathBand, taskBar } from "./common";

export function header(): HTMLElement {
  return h("header", { class: "hdr" },
    h("div", { class: "hdr-row" },
      h("span", { class: "brand" }, h("span", { class: "brand-dot", "aria-hidden": "true" }), "PITWALL"),
      hostDots(state.snapshot), demoTag(), freshness(state.snapshot, true), controls()));
}

export function desktop(): HTMLElement {
  const c = ctxOf();
  const root = h("div", { class: "view view-desktop" }, demoBar(), header(), banner());
  if (!c) { root.appendChild(loading()); return root; }
  const open = (rec: string | null, fid: string) => c.task && store.openEvidence(c.task.id, rec, fid);
  root.append(taskBar(c.sn, c.task), pathBand(c.sn, c.task, open),
    h("div", { class: "grid-ch" }, ch1(c), ch2(c), ch3(c), ch4(c), ch5(c), ch6(c, true)),
    h("div", { class: "bottom" },
      c.task ? resultPanel(c.task, open, state.artifactsExpanded, store.toggleArtifacts) : h("div", { class: "panel" }, "No task selected."),
      recentList(c.sn, c.task?.id ?? null, state.recentExpanded, store.selectTask, store.toggleRecent)));
  return root;
}
