# Org engine

Hub-and-spoke orchestration for Consulting OS. Specialist agents report to a coordinator. The coordinator compiles one packet, runs quality gates, and only escalates when a gate fails.

## How it works

The **coordinator** (chief of staff) owns the spine — the rules, the cadence, the org chart, what counts as source of truth. Specialists don't rewrite that. They append their station.

**Human-in-the-loop** sits above the hub. The coordinator pings the principal when something failed the bar — content that isn't useful, a list that isn't ready, a hunt that tried to become names too early.

## The week

Hunt runs on weekday mornings. Cards, not a worked list. Friday, the principal marks keep or skip. Then list-prep can run.

Sunday, marketing delivers two drafts. Midweek is a reminder to paste, not a new post.

The hub gates Friday second eyes, Saturday list quality, and Sunday content quality. Weekday evening, the coordinator closes the handoff. Sunday, it writes the transfer pack — the only writer of the spine.

## Architecture

```
Principal  (human-in-the-loop)
   └── Coordinator  (chief of staff)
         ├── Hunt
         ├── List
         ├── Apply
         └── Marketing
```

Hunt, list, and apply are GTM Spartan's three stations. Marketing is the marketing engine. The org engine is the graph they hang on.

- [Control plane](operating-rules.md) — policy the whole OS runs under
- [Cadence](cadences.md) — the clock
- [Topology](org-chart.md) — hub and spokes
- [Knowledge layer](sources-of-truth.md) — where truth lives
- [Coordinator](agents/chief-of-staff.md) — the chief-of-staff agent
