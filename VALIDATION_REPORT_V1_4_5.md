# Validation Report — CBB Dashboard v1.4.5

## Result

**PASS — 99/99 automated tests passed** against the complete v1.4.4 website after applying the v1.4.5 patch.

## Validated

- Owls API key remains Bearer-header only and is never placed in URLs.
- DraftKings/Circa spread, moneyline and total split parsing remains compatible.
- Owner-only raw split storage remains protected by RLS with no public SELECT policy.
- Sharp-money diagnostics calculate money-share minus ticket-share per side.
- 10-point minimum dashboard threshold prevents trivial divergence from being labeled sharp.
- Opposite ticket/money leaders upgrade the money side to a strong signal.
- Cross-book agreement produces a sharp-money consensus read.
- Conflicting book signals produce a mixed read rather than a false consensus.
- Raw percentages remain absent from public game-card commentary.
- Sharp-money context can appear in Why We Like / Risks without becoming a production-model feature.
- Existing Odds API line, ATS decision-line and CLV close-line provenance rules remain intact.
- Existing historical compatibility, security, UI, storage and performance tests remain green.

## Model firewall

V1.1.3B continues to receive no market, ticket, handle or sharp-money variables. The new layer is downstream display/research context only.
