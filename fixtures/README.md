# Demo fixtures

These are captured, synthetic pairings. They are not live data and they do not describe a real moment.

`fleet-top` and `flow-top` build their fixtures independently, so every scenario in `scenarios.json` is an
explicit choice of one fleet fixture and one flow fixture. Pitwall labels each one as a synthetic pairing
(`scenario_note`), stamps every value with `source: "demo:<scenario>"`, and answers `mode: "demo"`.

| Scenario | Fleet fixture | Flow fixture |
|---|---|---|
| `idle` | `serving_idle_eval_active`, active work cleared (edited) | `orland_completed` |
| `active` | `serving_idle_eval_active` | `orland_live` |
| `degraded` | `unreachable_host_partial_power` | `degraded_collector` |
| `recovered` | `serving_idle_eval_active`, active work cleared (edited) | hand-written from the `orland_completed` shape |

## Edited fixtures

Two scenarios use fixtures that were edited by hand. The edited results are committed as JSON in `raw/`:

- `raw/fleet-idle_cleared.edited.json`: `serving_idle_eval_active` with `active_jobs` emptied, the FX99#0
  evaluation device set back to unassigned and idle, and the summary text changed to say so.
- `raw/flow-recovered.handwritten.json`: written from the `orland_completed` shape; keeps three tasks
  (`help-publish-recovery`, `help-orland-throughput`, `help-loop`), reordered, with header text edited.

The other raw files are unedited captures of `fleet-top --fixture` / `flow-top --fixture` output.

## Markup check

The `degraded` scenario appends the literal text `<img src=x onerror=alert(1)>` to the last task's `title` and
`human_title` when it is loaded (declared as `patches` in `scenarios.json`). The UI must render it inert.

## What demo mode does not do

Fixtures name real run directories. Demo mode never opens them. Each demo task gets a synthetic receipt view
derived from the fixture's own fields, so the same participation rules run; hop `basis` strings say
"demo: synthesized from fixture fields". Evidence is unavailable in demo (`evidence_available: false`, and
`/api/evidence` answers 404 with `mode=demo`). `stale_after_s` is 0 and `age_s` is null on demo sources
because fixtures do not age.
