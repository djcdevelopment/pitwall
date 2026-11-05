import { h } from "../dom";

export interface SegOpts { pips?: number; color?: "green" | "cyan"; label: string }

/** Segmented bar. Only with a real denominator; otherwise a hatched bar that says unknown. */
export function segbar(num: number | null | undefined, den: number | null | undefined, o: SegOpts): HTMLElement {
  const n = o.pips ?? 20;
  if (num === null || num === undefined || den === null || den === undefined || den <= 0) {
    return h("div", { class: "seg-bar seg-hatch", role: "img", "aria-label": `${o.label}: unknown (no denominator)` });
  }
  const ratio = Math.max(0, Math.min(1, num / den));
  let lit = Math.round(ratio * n);
  if (num > 0 && lit === 0) lit = 1;
  const bar = h("div", { class: "seg-bar", role: "img", "aria-label": `${o.label}: ${num} of ${den}` });
  for (let i = 0; i < n; i++) bar.appendChild(h("span", { class: `seg-pip${i < lit ? ` c-${o.color ?? "green"}` : ""}` }));
  return bar;
}
