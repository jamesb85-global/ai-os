# Adapter

Public contract. Implementations stay private.

```text
HuntAdapter
  fetch_cards() -> list[Card]
  # Card: title, why_it_fit, source_kind, no person names

ListAdapter
  from_keeps(keeps) -> WorkingList
  # One live file. Hub does not upload a competing copy.

ApplyAdapter
  draft(listing) -> Draft
  # Never submit. Human clicks send.
```

## Rules

- Vendor APIs from the account's connected tools. No pasted secrets.
- No HTML scrape of a marketplace.
- Hunt does not promote to a worked list. James marks keep/skip first.
- Apply drafts may sit in a queue. They do not auto-send.

Source kind is a category (`board`, `referral`, `inbound`), not a product name.
