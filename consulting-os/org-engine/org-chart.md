# Topology

Hub-and-spoke. The principal is the human-in-the-loop above the graph. One coordinator sits at the hub. Every specialist is a spoke.

```
Principal
   └── Coordinator (chief of staff)
         ├── Hunt
         ├── List
         ├── Apply
         └── Marketing
```

This shape gives one compilation step (the packet), one policy owner (the coordinator), and gates that can fail closed without paging a human.

Hunt, list, and apply are stations on [GTM Spartan](../gtm-spartan/). Marketing is the [marketing engine](../marketing-engine/). This page is the graph they hang on.
