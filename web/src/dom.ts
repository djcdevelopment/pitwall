// Tiny DOM helpers. Text always goes through textContent; attributes through setAttribute.
type Child = Node | string | number | null | undefined | false;
type AttrVal = string | number | boolean | null | undefined | ((e: Event) => void);
export type Attrs = Record<string, AttrVal>;

function apply(el: Element, attrs: Attrs): void {
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (typeof v === "function") { el.addEventListener(k.replace(/^on/, ""), v); continue; }
    if (k === "text") { el.textContent = String(v); continue; }
    el.setAttribute(k, v === true ? "" : String(v));
  }
}
function kids(el: Element, children: Child[]): void {
  for (const c of children) {
    if (c === null || c === undefined || c === false) continue;
    el.appendChild(typeof c === "object" ? c : document.createTextNode(String(c)));
  }
}
export function h<K extends keyof HTMLElementTagNameMap>(tag: K, attrs: Attrs = {}, ...children: Child[]): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  apply(el, attrs); kids(el, children);
  return el;
}
const SVGNS = "http://www.w3.org/2000/svg";
export function s<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Attrs = {}, ...children: Child[]): SVGElementTagNameMap[K] {
  const el = document.createElementNS(SVGNS, tag);
  apply(el, attrs); kids(el, children);
  return el;
}
/** Only loopback http URLs become hrefs. */
export function safeHref(url: string | null | undefined): string | null {
  if (!url) return null;
  return /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?(\/|$|\?|#)/.test(url) ? url : null;
}
