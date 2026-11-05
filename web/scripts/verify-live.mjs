// Verifies the running service at PITWALL_URL. Read-only against the service. Writes to evidence/live.
import { chromium } from "playwright";
import { writeFileSync } from "node:fs";
import { homedir } from "node:os";
const BASE = process.env.PITWALL_URL ?? "http://127.0.0.1:18110";
const OUT = new URL("../../evidence/live/", import.meta.url).pathname;
const browser = await chromium.launch({ executablePath: `${homedir()}/.cache/ms-playwright/chromium-1248/chrome-linux/chrome` }).catch(() => chromium.launch());
const log = []; const say = (...a) => { const s = a.join(" "); log.push(s); console.log(s); };
const external = new Set(), errors = [];
async function open(w, h, q = "", extra = {}) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, ...extra });
  const p = await ctx.newPage();
  p.on("request", (r) => { if (!r.url().startsWith(BASE) && !r.url().startsWith("data:") && !r.url().startsWith("blob:")) external.add(r.url()); });
  p.on("pageerror", (e) => errors.push(`${q}: ${e.message}`));
  p.on("dialog", (d) => { errors.push(`DIALOG ${d.message()}`); d.dismiss(); });
  await p.goto(`${BASE}/${q}`); await p.waitForTimeout(1800);
  return { ctx, p };
}
const size = (p) => p.evaluate(() => ({ sh: document.documentElement.scrollHeight, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
const text = (p) => p.evaluate(() => document.body.innerText);
const taskOf = async (p) => { const t = await text(p); return ["Ontology Relpack", "Orland — copy link", "HearthClient"].filter((x) => t.includes(x)); };

for (const [name, w, h, q] of [["desktop", 1400, 900, "?view=desktop"], ["strip", 1400, 140, "?view=strip"], ["strip-1024", 1024, 140, "?view=strip"], ["tablet", 820, 1180, "?view=narrow"], ["narrow", 390, 844, "?view=narrow"]]) {
  const { ctx, p } = await open(w, h, q);
  const s = await size(p);
  await p.screenshot({ path: `${OUT}${name}.png`, fullPage: name === "tablet" || name === "narrow" });
  say(name, `${w}x${h}`, `scrollHeight=${s.sh}`, `hOverflow=${s.sw > s.cw}`);
  await ctx.close();
}

// Same task and values across views, within one context so preferences carry.
{
  const { ctx, p } = await open(1400, 900, "?view=desktop");
  const snap = await (await p.request.get(`${BASE}/api/snapshot`)).json();
  const orland = snap.tasks.find((t) => t.id.startsWith("help-orland-throughput"));
  await p.getByText(orland.short_title, { exact: false }).first().click(); await p.waitForTimeout(300);
  const seen = {};
  for (const v of ["Desktop", "Strip", "Narrow"]) {
    if (v === "Strip") { await p.setViewportSize({ width: 1400, height: 140 }); }
    if (v === "Narrow") { await p.goto(`${BASE}/?view=narrow${await p.evaluate(() => location.hash)}`); await p.setViewportSize({ width: 390, height: 844 }); }
    else await p.getByRole("button", { name: v, exact: true }).click().catch(() => {});
    await p.waitForTimeout(500);
    const t = await text(p);
    seen[v] = { task: t.includes(orland.short_title), recovered: /recovered/i.test(t), hash: await p.evaluate(() => location.hash) };
  }
  say("selection across views", JSON.stringify(seen)); await ctx.close();
}

// Honesty on the face of the live desktop.
{
  const { ctx, p } = await open(1400, 900, "?view=desktop");
  const t = await text(p);
  for (const s of ["3/9", "producer", "4/9", "7,092", "8,462", "unknown", "unreachable", "Source snapshot", "Transition written", "Transition read back"]) say("desktop contains", s, t.includes(s));
  for (const s of ["3090", "kHz", "efficiency", "20x", "time saved", "auto-adopted", "ETA", "CLUSTER-88"]) say("desktop lacks", s, !t.includes(s));
  const btn = p.getByRole("button", { name: "Export" });
  const [dl] = await Promise.all([p.waitForEvent("download"), btn.click()]);
  const path = await dl.path(); const body = (await import("node:fs")).readFileSync(path, "utf8");
  say("export", dl.suggestedFilename(), `bytes=${body.length}`, `schema=${JSON.parse(body).schema}`, `mode=${JSON.parse(body).mode}`);
  // Evidence: first hop opens a drawer with real content.
  await p.locator(".hop, .node, [data-fid^='hop']").first().click(); await p.waitForTimeout(700);
  await p.screenshot({ path: `${OUT}desktop-evidence.png` });
  say("evidence drawer lists BROKER or IRC", /RECEIPTS|consumption|RESULT/.test(await text(p)));
  await p.keyboard.press("Escape");
  await ctx.close();
}

// Demo scenarios, labelled in every layout, no live values.
const scen = (await (await fetch(`${BASE}/api/scenarios`)).json()).scenarios.map((s) => s.id);
for (const id of scen) {
  const snap = await (await fetch(`${BASE}/api/snapshot?mode=demo&scenario=${id}`)).json();
  const strs = JSON.stringify(snap); const nonDemoSources = snap.devices.flatMap((d) => [d.utilization.source]).filter((x) => !x.startsWith("demo:"));
  say("demo api", id, `mode=${snap.mode}`, `nonDemoSources=${nonDemoSources.length}`, `outcomes=${[...new Set(snap.tasks.map((t) => t.outcome.state))]}`, `exception=${snap.exception?.level ?? "none"}`, `bytes=${strs.length}`);
  for (const [name, w, h, v] of [["desktop", 1400, 900, "desktop"], ["strip", 1400, 140, "strip"], ["narrow", 390, 844, "narrow"]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h } });
    await ctx.addInitScript(() => {});
    const p = await ctx.newPage();
    p.on("pageerror", (e) => errors.push(`demo ${id}: ${e.message}`));
    p.on("dialog", (d) => { errors.push(`DIALOG ${d.message()}`); d.dismiss(); });
    await p.goto(`${BASE}/?view=${v}#mode=demo&scenario=${id}`); await p.waitForTimeout(900);
    const shown = (await text(p)).includes("DEMO");
    const opts = v === "strip" ? 0 : await p.locator("select[aria-label='Demo scenario'] option").count();
    say("demo size", id, name, JSON.stringify(await size(p)), `scenarioOptions=${opts}`);
    if (name === "desktop") { await p.screenshot({ path: `${OUT}demo-${id}.png` }); }
    if (id === "degraded") say("xss img present in DOM as element", await p.evaluate(() => document.querySelectorAll("img[src='x']").length));
    say("demo label", id, name, shown);
    await ctx.close();
  }
}

// Browser cost over 60 s, live desktop.
{
  const { ctx, p } = await open(1400, 900, "?view=desktop");
  const c = await ctx.newCDPSession(p); await c.send("Performance.enable");
  const m = async () => Object.fromEntries((await c.send("Performance.getMetrics")).metrics.map((x) => [x.name, x.value]));
  const a = await m(); await p.waitForTimeout(60000); const b = await m();
  say("browser 60s", `taskTime=${(b.TaskDuration - a.TaskDuration).toFixed(2)}s`, `cpuShare=${(100 * (b.TaskDuration - a.TaskDuration) / 60).toFixed(1)}%`, `jsHeapMiB=${(b.JSHeapUsedSize / 1048576).toFixed(1)}`, `nodes=${b.Nodes}`, `layouts=${b.LayoutCount - a.LayoutCount}`);
  await ctx.close();
}
say("external requests", external.size ? [...external].join(" ") : "none");
say("page errors", errors.length ? errors.join(" | ") : "none");
writeFileSync(`${OUT}verify-report.txt`, log.join("\n") + "\n");
await browser.close();
