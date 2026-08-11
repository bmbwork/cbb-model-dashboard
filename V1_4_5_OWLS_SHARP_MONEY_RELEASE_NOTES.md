# V1.4.5 — Owls Insight Sharp-Money Layer

## Added

- Explicit sharp-money diagnostics derived from Owls Insight handle-vs-ticket divergence.
- Owner-only row fields: Sharp Side, Sharp Gap Pts, Sharp Strength, Sharp Signal.
- Cross-book sharp-money consensus detection.
- Mixed-signal detection when sportsbooks point to different sides.
- Public qualitative sharp-money fields with no raw percentages.
- Sharp-money context in “Why we like this team” / risk reasoning.
- Market Terminal count of games with a sharp-money read.

## Interpretation rules

The provider documents that divergence between handle percentage and ticket percentage can indicate sharp action. The dashboard applies its own conservative threshold before surfacing that wording. It never claims bettor identity is known.

## Model firewall

No Owls ticket, handle, or sharp-money field is used by V1.1.3B. The production prediction remains market-blind.
