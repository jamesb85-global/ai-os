# Adapter contract

Hunt, list, and apply are stations. The **adapter** is how a source plugs into those stations without rewriting the OS.

The loop stays the same: fetch cards, wait for a human keep, prep a list, draft, wait for a human send.

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

**Promotion rules are part of the contract.** Hunt can't call list. List can't call apply on a skip. Apply can't POST.

Swap an adapter when the channel changes. Don't swap the loop.
