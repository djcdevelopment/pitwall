// Dev verification: serve the app with sample data via Vite dev, screenshot four layouts, run overflow checks.
import { createServer } from "vite";
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import net from "node:net";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const OUT = new URL("../../evidence/frontend-dev", import.meta.url).pathname;
const PORT = Number(process.env.SHOOT_PORT ?? 5199);
const exe = path.join(os.homedir(), ".cache/ms-playwright/chromium-1248/chrome-linux64/chrome");
fs.mkdirSync(OUT, { recursive: true });
execFileSync("node", ["dev/make-sample.mjs"], { stdio: "inherit" });
await new Promise((res, rej) => { const s = net.connect(PORT, "127.0.0.1"); s.on("connect", () => { s.destroy(); rej(new Error(`port ${PORT} busy; set SHOOT_PORT`)); }); s.on("error", () => res()); });
process.env.PITWALL_DEV_SAMPLE = "1";
const server = await createServer({ server: { port: PORT, strictPort: true, host: "127.0.0.1" }, logLevel: "error" });
await server.listen();
const browser = await chromium.launch({ executablePath: exe, args: ["--no-sandbox"] });
const base = `http://127.0.0.1:${PORT}/`;
const report = [];
const external = new Set();
async function shot(name, w, h, query, { full = true, act } = {}) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on("request", (r) => { const u = new URL(r.url()); if (u.hostname !== "127.0.0.1") external.add(r.url()); });
  page.on("pageerror", (e) => report.push(`${name}: pageerror ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") report.push(`${name}: console ${m.text()}`); });
  await page.goto(base + query);
  await page.waitForSelector(".view .panel, .view-strip .strip-a", { timeout: 8000 });
  await page.waitForTimeout(500);
  if (act) { await act(page); await page.waitForTimeout(300); }
  const m = await page.evaluate(() => {
    const de = document.documentElement;
    const clipped = [];
    document.querySelectorAll(".view *").forEach((el) => {
      if (el.closest("svg") || el.closest(".trend")) return;
      const cs = getComputedStyle(el);
      if (el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0 && cs.display !== "inline" && !["auto", "scroll"].includes(cs.overflowX)) clipped.push(`${el.className || el.tagName}:${el.scrollWidth}>${el.clientWidth}`);
    });
    return { scrollH: de.scrollHeight, scrollW: de.scrollWidth, innerW: innerWidth, clipped: clipped.slice(0, 8) };
  });
  report.push(`${name} ${w}x${h}: scrollHeight=${m.scrollH} scrollWidth=${m.scrollW}/${m.innerW} hOverflow=${m.scrollW > m.innerW} clipped=${JSON.stringify(m.clipped)}`);
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: full });
  await ctx.close();
}
await shot("desktop-1400x900", 1400, 900, "?view=desktop");
await shot("strip-1400x140", 1400, 140, "?view=strip", { full: false });
await shot("strip-1024x140", 1024, 140, "?view=strip", { full: false });
await shot("narrow-820x1180", 820, 1180, "");
await shot("narrow-390x844", 390, 844, "");
await shot("desktop-demo-1400", 1400, 900, "?view=desktop#mode=demo&scenario=active");
await shot("strip-demo-1400x140", 1400, 140, "?view=strip#mode=demo&scenario=active", { full: false });
await shot("narrow-demo-390x844", 390, 844, "#mode=demo&scenario=active", { full: false });
await shot("desktop-evidence-1400", 1400, 900, "?view=desktop", { full: false, act: async (p) => { await p.click('[data-fid="hop-0"]'); await p.waitForSelector(".ev-drawer"); await p.waitForTimeout(400); } });
await shot("narrow-evidence-390", 390, 844, "", { full: false, act: async (p) => { await p.click('[data-fid="hop-0"]'); await p.waitForSelector(".ev-drawer"); await p.waitForTimeout(400); } });
await shot("desktop-markup-1400", 1400, 900, "?view=desktop#task=markup&mode=live", { full: false });
{
  // keyboard walk, Esc, reduced motion
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(base + "?view=desktop"); await page.waitForSelector(".panel");
  const walked = []; let bad = 0;
  for (let i = 0; i < 60; i++) {
    await page.keyboard.press("Tab");
    const r = await page.evaluate(() => { const e = document.activeElement; if (!e || e === document.body) return null; const cs = getComputedStyle(e); return { d: (e.getAttribute("data-fid") || e.id || e.tagName) + ":" + (e.textContent || "").trim().slice(0, 14), outline: cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0 }; });
    if (r) { walked.push(r.d); if (!r.outline) bad++; }
  }
  report.push(`keyboard walk: ${walked.length} focus stops in 60 Tabs, ${bad} without visible outline; first stops: ${walked.slice(0, 12).join(" | ")}`);
  await page.focus('[data-fid="hop-0"]'); await page.keyboard.press("Enter"); await page.waitForSelector(".ev-drawer");
  const inDrawer = await page.evaluate(() => !!document.activeElement?.closest(".ev-drawer"));
  for (let i = 0; i < 40; i++) await page.keyboard.press("Tab");
  const trapped = await page.evaluate(() => !!document.activeElement?.closest(".ev-drawer"));
  await page.keyboard.press("Escape"); await page.waitForTimeout(200);
  const closed = await page.evaluate(() => !document.querySelector(".ev-drawer"));
  const back = await page.evaluate(() => document.activeElement?.getAttribute("data-fid"));
  report.push(`drawer: focus moved in=${inDrawer}, trapped after 40 Tabs=${trapped}, Esc closed=${closed}, focus returned to ${back}`);
  const anim = () => page.evaluate(() => { const n = [".b-active .glyph", ".n-active"].map((q) => document.querySelector(q)).filter(Boolean); return n.map((e) => getComputedStyle(e).animationName).join(","); });
  const before = await anim();
  await page.click('[data-fid="motion"]'); await page.waitForTimeout(200);
  const after = await anim();
  report.push(`reduced motion: animation before toggle [${before}], after toggle [${after}]`);
  await ctx.close();
  const c2 = await browser.newContext({ viewport: { width: 1400, height: 900 }, reducedMotion: "reduce" });
  const p2 = await c2.newPage(); await p2.goto(base + "?view=desktop"); await p2.waitForSelector(".panel");
  report.push(`prefers-reduced-motion: animation [${await p2.evaluate(() => [...document.querySelectorAll(".b-active .glyph")].map((e) => getComputedStyle(e).animationName).join(","))}]`);
  await c2.close();
}
await browser.close(); await server.close();
report.push(`external requests: ${external.size ? [...external].join(", ") : "none"}`);
fs.writeFileSync(path.join(OUT, "report.txt"), report.join("\n") + "\n");
console.log(report.join("\n"));
