# Org engine

Without an org layer, every specialist agent is another inbox.

That's the pain. You add a researcher, a writer, a hunter — and the founder now has three streams to read instead of one job to do. "AI" made the week louder.

The org engine is hub-and-spoke orchestration. Specialist agents don't talk to the principal. They report to a coordinator. The coordinator compiles one packet, runs quality gates, and only escalates when a gate fails.

That's operational leverage: more work moving, same attention budget.

## How it works

The **coordinator** (chief of staff) owns the spine — the rules, the cadence, the org chart, what counts as source of truth. Specialists don't rewrite that. They append their station. Separation of concerns: policy at the hub, execution at the spokes.

**Human-in-the-loop** sits above the hub. The coordinator doesn't ping the principal because something finished. It pings when something failed the bar — content that isn't useful, a list that isn't ready, a hunt that tried to become names too early.

## The week

Hunt runs on weekday mornings. Cards, not a worked list. Friday, the principal marks keep or skip. Then list-prep is allowed to run.

Sunday, marketing delivers two drafts. Midweek is a reminder to paste, not a license to invent a post.

The hub gates the week in quiet: Friday second eyes, Saturday list quality, Sunday content quality. If the bar is met, nobody gets a Slack novel. Weekday evening, the coordinator closes the handoff. Sunday, it writes the transfer pack — the only writer of the spine.

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
