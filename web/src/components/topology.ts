import { h, s } from "../dom";
import type { PathHop, Task } from "../contract";
import { badge, fromParticipation } from "./badge";

const STATE_TEXT: Record<PathHop["state"], string> = { used: "used", active: "active", unused: "unused", unknown: "unknown" };

function arrow(): SVGElement {
  return s("svg", { viewBox: "0 0 28 12", width: 28, height: 12, class: "hop-arrow", "aria-hidden": "true" },
    s("path", { d: "M1 6H22M17 1.5L22.5 6L17 10.5", fill: "none", "stroke-width": 1.6 }));
}

/** Observed path: only task.path, in returned order. */
export function topology(t: Task, hostLabel: (id: string | null) => string, onOpen: (hop: PathHop) => void): HTMLElement {
  const wrap = h("div", { class: "topo", role: "list" });
  if (t.path.length === 0) wrap.appendChild(h("div", { class: "empty-note" }, "No path observed for this task."));
  t.path.forEach((hop, i) => {
    if (i > 0) wrap.appendChild(h("span", { class: `hop-link hl-${hop.state}`, "aria-hidden": "true" }, arrow()));
    const btn = h("button", {
      type: "button", role: "listitem", class: `node n-${hop.state}`, "data-fid": `hop-${i}`,
      title: `${hop.summary}\nbasis: ${hop.basis}`,
      "aria-label": `${hop.label}, ${STATE_TEXT[hop.state]}, host ${hostLabel(hop.host_id)}. Open evidence.`,
      onclick: () => onOpen(hop),
    },
      h("span", { class: "node-name" }, hop.label),
      badge(fromParticipation(hop.state), STATE_TEXT[hop.state]),
      h("span", { class: "node-host" }, hostLabel(hop.host_id)));
    wrap.appendChild(btn);
  });
  return wrap;
}
