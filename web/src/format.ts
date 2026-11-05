import type { Measurement } from "./contract";

export function fmtNum(v: number, digits = 0): string {
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
export function fmtBytes(n: number): string {
  if (n < 1024) return `${fmtNum(n)} B`;
  if (n < 1024 * 1024) return `${fmtNum(n / 1024, 1)} KiB`;
  return `${fmtNum(n / 1048576, 2)} MiB`;
}
export function fmtDur(sec: number | null): string {
  if (sec === null || sec === undefined) return "unknown";
  if (sec < 1) return `${fmtNum(sec * 1000, 0)} ms`;
  if (sec < 60) return `${fmtNum(sec, sec < 10 ? 1 : 0)} s`;
  const m = Math.floor(sec / 60), r = Math.round(sec % 60);
  if (m < 60) return `${m}m ${String(r).padStart(2, "0")}s`;
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
}
export function fmtAge(sec: number): string {
  sec = Math.max(0, Math.round(sec));
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
}
export function ageSince(iso: string | null): number | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : (Date.now() - t) / 1000;
}
export function clock(iso: string | null): string {
  if (!iso) return "unknown";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "unknown" : d.toLocaleTimeString("en-GB");
}
export function shortSha(s: string): string { return s ? s.slice(0, 8) : "no hash"; }

/** Convert a measured value into display number and unit. Memory is shown in GiB. */
export function scaled(m: Measurement): { n: number; unit: string; digits: number } | null {
  if (typeof m.value !== "number") return null;
  const u = m.unit;
  if (u === "B" || u === "bytes") return m.value >= 1024 ? { n: m.value / 1024, unit: "KiB", digits: 1 } : { n: m.value, unit: "B", digits: 0 };
  if (u === "GiB" || u === "GB") return { n: m.value, unit: u, digits: 1 };
  if (u === "W" || u === "C" || u === "°C" || u === "%") return { n: m.value, unit: u === "C" ? "°C" : u, digits: 0 };
  if (u === "tok/s") return { n: m.value, unit: u, digits: 1 };
  if (u === "ms") return { n: m.value, unit: u, digits: m.value < 10 ? 2 : 0 };
  return { n: m.value, unit: u, digits: Number.isInteger(m.value) ? 0 : 1 };
}
