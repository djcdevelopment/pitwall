import { h } from "../dom";
import type { Measurement } from "../contract";
import { ageSince, fmtAge, fmtNum, scaled } from "../format";
import { GLYPH } from "./badge";

export interface ReadingOpts { digits?: number; unitOverride?: string; big?: boolean; short?: boolean }

/** Every reading goes through here: value + unit, or a worded state with a distinct shape. */
export function reading(m: Measurement | null | undefined, o: ReadingOpts = {}): HTMLElement {
  const cls = `rd${o.big ? " rd-big" : ""}`;
  if (!m) return h("span", { class: `${cls} rd-unknown` }, h("span", { class: "glyph", "aria-hidden": "true" }, GLYPH.unknown), " unknown");
  const title = `${m.source || "no source"} | scope ${m.scope}${m.note ? " | " + m.note : ""}`;
  const sc = scaled(m);
  const su = o.unitOverride ?? (m.unit === "C" ? "\u00B0C" : m.unit);
  const word = (w: string) => (o.short ? su : w);
  if (m.status === "unreachable") return state(cls, "unreachable", word("unreachable"), title);
  if (m.status === "unused") return state(cls, "unused", word("unused"), title);
  if (sc === null || m.value === null) return state(cls, "unknown", word("unknown"), title);
  const valEl = h("span", { class: "rd-val" }, fmtNum(sc.n, o.digits ?? sc.digits));
  const unit = o.unitOverride ?? sc.unit;
  const body: (Node | string)[] = [valEl, unit ? h("span", { class: "rd-unit" }, ` ${unit}`) : ""];
  if (m.status === "stale") {
    const a = ageSince(m.observed_at);
    body.push(h("span", { class: "rd-stale" }, h("span", { class: "glyph", "aria-hidden": "true" }, GLYPH.stale),
      a === null ? " stale" : o.short ? fmtAge(a) : ` stale ${fmtAge(a)}`));
  }
  return h("span", { class: `${cls} ${m.status === "stale" ? "rd-staleval" : "rd-ok"}`, title }, ...body);
}
function state(cls: string, kind: "unknown" | "unused" | "unreachable", text: string, title: string): HTMLElement {
  return h("span", { class: `${cls} rd-${kind}`, title }, h("span", { class: "glyph", "aria-hidden": "true" }, GLYPH[kind]), ` ${text}`);
}

export function hasRatio(m: Measurement | null | undefined): m is Measurement & { numerator: number; denominator: number } {
  return !!m && m.numerator !== null && m.denominator !== null && m.denominator > 0 && m.status !== "unknown" && m.status !== "unreachable";
}

/** label : reading row */
export function row(label: string, value: Node | string, tag?: string): HTMLElement {
  return h("div", { class: "kv" }, h("span", { class: "k" }, label, tag ? h("em", { class: "scope-tag" }, tag) : null), h("span", { class: "v" }, value));
}

/** "25.3 / 32.0 GiB" when both are fresh numbers in one unit; otherwise two separate readings. */
export function readingPair(a: Measurement, b: Measurement): HTMLElement {
  const sh = { short: true };
  const sa = scaled(a), sb = scaled(b);
  if (sa && sb && a.status === "ok" && b.status === "ok" && sa.unit === sb.unit) {
    return h("span", { class: "rd rd-ok", title: `${a.source} | ${b.source}` }, h("span", { class: "rd-val" }, `${fmtNum(sa.n, sa.digits)} / ${fmtNum(sb.n, sb.digits)}`), h("span", { class: "rd-unit" }, ` ${sa.unit}`));
  }
  return h("span", {}, reading(a, sh), h("span", { class: "dim" }, " / "), reading(b, sh));
}
