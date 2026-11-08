import { h } from "../dom";
import { safeHref } from "../dom";
import type { InspectionLink, Snapshot, Task } from "../contract";
import { ageSince, fmtAge, fmtNum, shortSha } from "../format";
import { badge, fromCheck, fromOutcome, fromReview } from "./badge";
import { segbar } from "./segbar";

export function linkEl(l: InspectionLink): HTMLElement {
  const href = safeHref(l.url);
  if (l.enabled && href) return h("span", { class: "ilink-w" }, h("a", { class: "ilink", href, target: "_blank", rel: "noopener noreferrer" }, l.label, " ↗"),
    l.annotation ? h("span", { class: "ilink-note" }, ` ${l.annotation}`) : null);
  return h("span", { class: "ilink ilink-off", "aria-disabled": "true" }, l.label, " (disabled: ", l.reason || (href ? "service not reachable now" : "link not loopback"), ")");
}

function tokenRow(label: string, used: number | null, budget: number | null): HTMLElement {
  const known = used !== null;
  const txt = !known ? "unknown" : budget !== null && budget > 0 ? `${fmtNum(used)} of ${fmtNum(budget)} task budget` : `${fmtNum(used)} (no budget)`;
  return h("div", { class: "tok" },
    h("div", { class: "kv" }, h("span", { class: "k" }, label), h("span", { class: `v${known ? "" : " rd-unknown"}` }, txt)),
    segbar(used, budget, { color: "cyan", label: `${label} of task budget`, pips: 24 }));
}

export function resultPanel(t: Task, openRecord: (rec: string | null, fid: string) => void, expanded: boolean, onMore: () => void): HTMLElement {
  const dec = (title: string, kindEl: HTMLElement, detail: string, rec: string | null, fid: string) =>
    h("div", { class: "dec", title: detail },
      h("div", { class: "dec-h" }, h("span", { class: "lab" }, title), kindEl, rec ? h("button", { type: "button", class: "mini-btn", "data-fid": fid, onclick: () => openRecord(rec, fid) }, "evidence") : null),
      h("span", { class: "dec-detail" }, detail || "no detail recorded"));
  const a = ageSince(t.outcome.finished_at);
  const outcome = dec("Task outcome", badge(fromOutcome(t.outcome.state), t.outcome.label || t.outcome.state), `${t.outcome.summary}${a !== null ? ` Finished ${fmtAge(a)} ago.` : ""}`, null, "x");
  const checks = dec("Checks", badge(fromCheck(t.checks.state), t.checks.state), t.checks.detail, t.checks.evidence_record, "ev-checks");
  const review = dec("Review", badge(fromReview(t.review.state), t.review.state), t.review.detail, t.review.evidence_record, "ev-review");
  const tk = t.tokens;
  const tokens = h("div", { class: "sub" }, h("h4", {}, "Tokens, of task budget"),
    tokenRow("In", tk.tokens_in, tk.budget_in), tokenRow("Out", tk.tokens_out, tk.budget_out), tokenRow("Calls", tk.model_calls, tk.budget_calls),
    h("div", { class: "dim" }, `reasoning ${tk.tokens_reasoning === null ? "unknown" : fmtNum(tk.tokens_reasoning)} | emit repairs ${tk.emit_repairs === null ? "unknown" : fmtNum(tk.emit_repairs)}`));
  const r = t.routing;
  const rtRows: [string, string][] = [["family", r.task_family], ["provider", r.provider], ["model", r.model], ["routed_by", r.routed_by], ["regime", r.regime], ["job", r.job_id]];
  if (r.execution_mode || (r.fence_epoch !== null && r.fence_epoch !== undefined)) {
    rtRows.push(["mode", `${r.execution_mode ?? "ticket"}${r.fence_epoch !== null && r.fence_epoch !== undefined ? ` (epoch ${r.fence_epoch})` : ""}`]);
  }
  if (r.generation || (r.consul_index !== null && r.consul_index !== undefined)) {
    rtRows.push(["consul", `gen ${r.generation ?? "?"}${r.consul_index !== null && r.consul_index !== undefined ? ` @${r.consul_index}` : ""}`]);
  }
  if (r.thinking_source) {
    rtRows.push(["thinking_src", r.thinking_source]);
  }
  const routing = h("div", { class: "sub" }, h("h4", {}, "HEARTH routing"),
    h("div", { class: "rt" }, ...rtRows.map(([k, v]) => h("div", { class: "rt-i", title: `${k}: ${v}` }, h("span", { class: "k" }, k), h("span", { class: "mono-wrap" }, v || "unknown")))));
  const arts = expanded ? t.artifacts : t.artifacts.slice(0, 3);
  const artEl = h("div", { class: "sub" }, h("h4", {}, "Artifacts"),
    t.artifacts.length === 0 ? h("div", { class: "empty-note" }, "No artifact references.") : null,
    ...arts.map((x, i) => h("div", { class: "art", title: x.note },
      x.record_id ? h("button", { type: "button", class: "art-name linkish", "data-fid": `art-${i}`, onclick: () => openRecord(x.record_id, `art-${i}`) }, x.name) : h("span", { class: "art-name" }, x.name),
      h("span", { class: "sha", title: x.sha256 }, `sha256 ${shortSha(x.sha256)}`))),
    t.artifacts.length > 3 ? h("button", { type: "button", class: "mini-btn", "data-fid": "art-more", "aria-expanded": String(expanded), onclick: onMore }, expanded ? "fewer" : `more (${t.artifacts.length - 3})`) : null,
    h("div", { class: "links" }, ...t.links.map(linkEl)));
  return h("section", { class: "panel result", "aria-label": "Selected task result" },
    h("div", { class: "panel-h" }, h("span", {}, "SELECTED TASK RESULT"), h("span", { class: "dim ellip" }, t.short_title)),
    h("div", { class: "decs" }, outcome, checks, review),
    h("div", { class: "result-grid" }, tokens, routing, artEl));
}

export function recentList(sn: Snapshot, selId: string | null, expanded: boolean, onSelect: (id: string) => void, onToggle: () => void): HTMLElement {
  const tasks = sn.tasks.slice(0, 10);
  const shown = expanded ? tasks : tasks.slice(0, 3);
  const list = h("div", { class: `recent-list${expanded ? " rl-open" : ""}`, role: "listbox", "aria-label": "Recent tasks" });
  shown.forEach((t, i) => {
    const sel = t.id === selId;
    const fin = ageSince(t.outcome.finished_at);
    list.appendChild(h("button", {
      type: "button", role: "option", "aria-selected": sel ? "true" : "false", class: `rcard${sel ? " rsel" : ""}`,
      "data-fid": `recent-${i}`, onclick: () => onSelect(t.id), title: t.title,
      onkeydown: (e: Event) => {
        const k = (e as KeyboardEvent).key;
        const dir = k === "ArrowDown" || k === "ArrowRight" ? 1 : k === "ArrowUp" || k === "ArrowLeft" ? -1 : 0;
        if (!dir) return;
        e.preventDefault();
        const sibs = Array.from(list.querySelectorAll<HTMLElement>(".rcard"));
        sibs[(i + dir + sibs.length) % sibs.length]?.focus();
      },
    },
      badge(fromOutcome(t.outcome.state), t.outcome.label || t.outcome.state),
      h("span", { class: "rc-title" }, t.short_title),
      h("span", { class: "rc-sub" }, `${fin !== null ? fmtAge(fin) + " ago | " : ""}Checks ${t.checks.state} | Review ${t.review.state}`)));
  });
  const more = tasks.length - 3;
  return h("section", { class: "panel recent", "aria-label": "Recent tasks" },
    h("div", { class: "panel-h" }, h("span", {}, "RECENT TASKS"),
      more > 0 ? h("button", { type: "button", class: "mini-btn", "data-fid": "recent-more", "aria-expanded": String(expanded), onclick: onToggle }, expanded ? "fewer" : `more (${more})`) : null),
    list);
}
