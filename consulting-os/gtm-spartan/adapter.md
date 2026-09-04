# Adapter contract

Hunt, list, and apply are stations. The **adapter** is how a source plugs into those stations without rewriting the OS.

That's the architecture move. Upwork, a referral inbox, an inbound form — each is a different wire. The loop stays the same: fetch cards, wait for a human keep, prep a list, draft, wait for a human send.

```text
HuntAdapter
  fetch_cards() -> list[Card]
  # pattern, why it fits, source kind — no person names

ListAdapter
  from_keeps(keeps) -> WorkingList
  # one live file; the hub doesn't fork a second copy

ApplyAdapter
  draft(listing) -> Draft
  # queue only. never submit.
```

**Source kind** is a category (`board`, `referral`, `inbound`), not a product name. Implementations are vendor APIs from the account's connected tools. Secrets don't live in the prompt.

**Promotion rules are part of the contract.** Hunt cannot call list. List cannot call apply on a skip. Apply cannot POST. Those aren't manners. They're the control plane for a go-to-market graph that would otherwise optimize for volume.

Swap an adapter when the channel changes. Don't swap the loop.
