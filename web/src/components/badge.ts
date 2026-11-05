import { h } from "../dom";
import type { ActivityState, CheckState, DeliveryState, OutcomeState, ParticipationState, ReviewState, StageState, StepState } from "../contract";

export type Kind = "active" | "idle" | "reachable" | "stale" | "unreachable" | "unknown" | "unused" | "completed" | "recovered" | "failed" | "attention";

export const GLYPH: Record<Kind, string> = {
  active: "▶", idle: "■", reachable: "●", stale: "◷", unreachable: "✗", unknown: "?",
  unused: "·", completed: "✓", recovered: "↺", failed: "✗", attention: "!",
};

/** The one status badge: shape + colour + text, always. */
export function badge(kind: Kind, text?: string, extra = ""): HTMLElement {
  return h("span", { class: `badge b-${kind} ${extra}`.trim() },
    h("span", { class: "glyph", "aria-hidden": "true" }, GLYPH[kind]),
    h("span", { class: "btxt" }, text ?? kind));
}

export const fromActivity = (s: ActivityState): Kind => s;
export const fromParticipation = (s: ParticipationState): Kind =>
  s === "used" ? "completed" : s === "active" ? "active" : s === "unused" ? "unused" : "unknown";
export const fromOutcome = (s: OutcomeState): Kind =>
  s === "staged" ? "idle" : s;
export const fromStage = (s: StageState): Kind =>
  ({ done: "completed", working: "active", waiting: "idle", attention: "attention", failed: "failed", unknown: "unknown", unused: "unused" } as const)[s];
export const fromCheck = (s: CheckState): Kind => (s === "passed" ? "completed" : s === "failed" ? "failed" : "unknown");
export const fromReview = (s: ReviewState): Kind =>
  s === "accepted" ? "completed" : s === "rejected" ? "failed" : s === "pending" ? "idle" : "unknown";
export const fromDelivery = (s: DeliveryState): Kind =>
  s === "delivered" ? "completed" : s === "waiting" ? "idle" : s;
export const fromStep = (s: StepState): Kind => (s === "recorded" ? "completed" : s === "not_recorded" ? "unused" : "unknown");
export const STEP_TEXT: Record<StepState, string> = { recorded: "recorded", not_recorded: "not recorded", unknown: "unknown" };
