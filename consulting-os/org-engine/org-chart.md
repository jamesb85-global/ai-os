# Topology

Hub-and-spoke. That's the architecture, not a metaphor.

The principal is not a node that every agent writes to. They're the human-in-the-loop above the graph. One coordinator sits at the hub. Every specialist is a spoke.

```
Principal
   └── Coordinator (chief of staff)
         ├── Hunt
         ├── List
         ├── Apply
         └── Marketing
```

**Why this shape.** A mesh — every agent talking to every agent, and all of them to the founder — recreates the Slack problem in silicon. Hub-and-spoke gives you a single compilation step: the packet. It gives you a single policy owner: the coordinator. It gives you gates that can fail closed without paging a human.

Hunt, list, and apply are stations on [GTM Spartan](../gtm-spartan/). Marketing is the [marketing engine](../marketing-engine/). This page is the graph they hang on — the org function of the OS.
