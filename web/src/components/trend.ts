import { h, s } from "../dom";
import type { History } from "../contract";
import { fmtNum } from "../format";

export interface TrendOpts { key: string; unit: string; color: "green" | "cyan"; yMax?: number; label: string; height?: number }

const WIN_LABEL: Record<number, string> = { 60: "1m", 300: "5m", 900: "15m" };

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1, 2, 2.5, 5, 10]) if (v <= m * p) return m * p;
  return 10 * p;
}

/** Line trend. Straight segments, broken at null; no fill; labelled unit, window and axis max. */
export function trend(hist: History | null, o: TrendOpts): HTMLElement {
  const wrap = h("div", { class: "trend crt-graticule", style: `height:${o.height ?? 56}px` });
  const ser = hist?.series.find((x) => x.key === o.key);
  const winS = hist?.window_s ?? 0;
  const winLabel = WIN_LABEL[winS] ?? `${winS}s`;
  const note = (t: string) => wrap.appendChild(h("span", { class: "trend-note" }, t));
  if (!hist || !ser) { wrap.classList.add("trend-empty"); note(hist ? "no series" : "history loading"); return wrap; }
  const nowS = hist.now > 1e12 ? hist.now / 1000 : hist.now;
  const scale = hist.now > 1e12 ? 1000 : 1;
  const t0 = nowS - winS;
  const pts = ser.points.map(([t, v]) => [t / scale, v] as [number, number | null]).filter(([t]) => t >= t0 - 1 && t <= nowS + 1);
  const vals = pts.filter(([, v]) => v !== null).map(([, v]) => v as number);
  if (vals.length === 0) { wrap.classList.add("trend-empty"); note("no samples in window"); return wrap; }
  const ymax = o.yMax ?? niceMax(Math.max(...vals));
  const W = 300, H = 100;
  const X = (t: number) => ((t - t0) / winS) * W;
  const Y = (v: number) => H - Math.max(0, Math.min(1, v / ymax)) * (H - 4) - 2;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", class: `trend-svg tr-${o.color}`, role: "img", "aria-label": `${o.label} ${o.unit}, last ${winLabel}, axis max ${fmtNum(ymax, ymax < 10 ? 1 : 0)}` });
  let seg: string[] = [];
  const flush = () => {
    if (seg.length === 1) { const [x, y] = seg[0].split(",").map(Number); svg.appendChild(s("polyline", { points: `${(x - 0.8).toFixed(1)},${y.toFixed(1)} ${(x + 0.8).toFixed(1)},${y.toFixed(1)}`, class: "tl", fill: "none" })); }
    else if (seg.length > 1) svg.appendChild(s("polyline", { points: seg.join(" "), class: "tl", fill: "none" }));
    seg = [];
  };
  for (const [t, v] of pts) { if (v === null) flush(); else seg.push(`${X(t).toFixed(1)},${Y(v).toFixed(1)}`); }
  flush();
  wrap.appendChild(svg);
  wrap.appendChild(h("span", { class: "trend-max" }, `${fmtNum(ymax, ymax < 10 ? 1 : 0)} ${o.unit} | ${winLabel}`));
  const startMs = hist.started_at ? Date.parse(hist.started_at) : NaN;
  const short = !Number.isNaN(startMs) && startMs / 1000 > t0 + 2;
  wrap.appendChild(h("span", { class: "trend-win" },
    short ? `since ${new Date(startMs).toLocaleTimeString("en-GB")}` : ""));
  return wrap;
}
