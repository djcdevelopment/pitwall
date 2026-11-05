import "@fontsource/share-tech-mono/latin-400.css";
import "@fontsource/jetbrains-mono/latin-400.css";
import "@fontsource/jetbrains-mono/latin-600.css";
import "@fontsource/jetbrains-mono/latin-700.css";
import "@fontsource/jetbrains-mono/latin-800.css";
import "./styles.css";
import * as store from "./store";
import { state, selectedTask } from "./store";
import { desktop } from "./views/desktop";
import { strip } from "./views/strip";
import { narrow } from "./views/narrow";
import { evidencePanel } from "./components/evidencePanel";
import { fmtAge } from "./format";

const app = document.getElementById("app") as HTMLElement;
let lastEvidenceOpen = false;

function render(): void {
  const doc = document.documentElement;
  doc.dataset.view = state.view;
  doc.dataset.motion = state.reducedMotion ? "reduced" : "full";
  doc.dataset.mode = state.mode;
  const active = document.activeElement as HTMLElement | null;
  const fid = active?.getAttribute("data-fid") ?? null;
  const selStart = (active as HTMLInputElement | null)?.selectionStart;
  const sy = window.scrollY;

  const view = state.view === "strip" ? strip() : state.view === "narrow" ? narrow() : desktop();
  const nodes: Node[] = [view];
  const ev = state.evidence;
  if (ev.open && state.snapshot && state.view !== "strip") {
    nodes.push(evidencePanel(ev, state.snapshot, state.snapshot.tasks.find((t) => t.id === ev.taskId) ?? selectedTask(), state.mode, {
      close: () => store.closeEvidence(), openRecord: (id) => void store.openRecord(id),
    }));
  }
  app.replaceChildren(...nodes);
  window.scrollTo(0, sy);

  if (ev.open) {
    if (ev.section) { app.querySelector(`.ev-body [data-sec="${ev.section}"]`)?.scrollIntoView({ block: "start" }); ev.section = null; }
    if (ev.focusDrawer) { document.getElementById("ev-close")?.focus(); ev.focusDrawer = false; }
    else if (fid) (app.querySelector(`.ev-drawer [data-fid="${CSS.escape(fid)}"]`) as HTMLElement | null)?.focus();
    lastEvidenceOpen = true;
  } else {
    if (lastEvidenceOpen) {
      lastEvidenceOpen = false;
      const back = ev.returnFid && (app.querySelector(`[data-fid="${CSS.escape(ev.returnFid)}"]`) as HTMLElement | null);
      if (back) back.focus();
    } else if (fid) {
      const el = app.querySelector(`[data-fid="${CSS.escape(fid)}"]`) as HTMLElement | null;
      if (el && el !== document.activeElement) { el.focus(); if (selStart != null) { try { (el as HTMLInputElement).setSelectionRange(selStart, selStart); } catch { /* not a text field */ } } }
    }
  }
}

document.addEventListener("keydown", (e) => {
  if (!state.evidence.open) return;
  if (e.key === "Escape") { e.preventDefault(); store.closeEvidence(); return; }
  if (e.key !== "Tab") return;
  const drawer = app.querySelector<HTMLElement>(".ev-drawer"); if (!drawer) return;
  const f = Array.from(drawer.querySelectorAll<HTMLElement>('button, a[href], pre[tabindex], [tabindex="0"]')).filter((x) => !x.hasAttribute("disabled"));
  if (f.length === 0) return;
  const first = f[0], last = f[f.length - 1];
  if (!drawer.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
  else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
});

// Age labels tick in place; nothing re-renders.
setInterval(() => {
  document.querySelectorAll<HTMLElement>("[data-since]").forEach((el) => {
    const t = Number(el.dataset.since); if (!Number.isNaN(t)) el.textContent = fmtAge((Date.now() - t) / 1000);
  });
}, 1000);

store.subscribe(render);
render();
store.start();
