import { h } from "../dom";
import type { Task } from "../contract";
import { badge, fromDelivery, fromStage } from "./badge";

/** Task-stage ribbon; delivery stands apart so recovered delivery never reads as failed work. */
export function ribbon(t: Task): HTMLElement {
  const stages = h("ol", { class: "ribbon-stages", "aria-label": "Task stages" });
  if (t.stages.length === 0) stages.appendChild(h("li", { class: "stage-none" }, "No stages reported"));
  for (const st of t.stages) {
    stages.appendChild(h("li", { class: `stage st-${st.state}`, title: `${st.label}: ${st.state}` }, badge(fromStage(st.state), `${st.label}`)));
  }
  const dlv = h("div", { class: "ribbon-delivery", title: t.delivery.label },
    h("span", { class: "lab" }, "Delivery"),
    badge(fromDelivery(t.delivery.state), t.delivery.label || t.delivery.state));
  return h("div", { class: "ribbon" }, h("div", { class: "ribbon-work" }, h("span", { class: "lab" }, "Task stages"), stages), dlv);
}
