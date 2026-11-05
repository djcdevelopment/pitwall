import { h, s } from "../dom";

/** Ring meter; caller must have checked numerator and denominator > 0. */
export function ring(num: number, den: number, color: "green" | "cyan", label: string, size = 44): SVGElement {
  const r = 16, c = 2 * Math.PI * r;
  const ratio = Math.max(0, Math.min(1, num / den));
  const svg = s("svg", { viewBox: "0 0 40 40", width: size, height: size, class: `gauge gauge-${color}`, role: "img", "aria-label": `${label}: ${num} of ${den}` },
    s("circle", { cx: 20, cy: 20, r, fill: "none", class: "gauge-bg", "stroke-width": 4 }),
    s("circle", { cx: 20, cy: 20, r, fill: "none", class: "gauge-fg", "stroke-width": 4, "stroke-dasharray": c.toFixed(2), "stroke-dashoffset": (c * (1 - ratio)).toFixed(2), transform: "rotate(-90 20 20)" }),
    s("text", { x: 20, y: 23.5, "text-anchor": "middle", class: "gauge-txt" }, `${Math.round(ratio * 100)}%`));
  return svg;
}
export function noRatio(text: string): HTMLElement { return h("span", { class: "no-ratio" }, text); }
