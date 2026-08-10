# CBB Dashboard v1.3.4 — Priority Board UI Trim

## Changes
- Priority Board scope reduced to `Top 10` and `All`.
- Removed the public `Likely result range` metric from game cards, Matchup Explorer, dossiers, and glossary copy.
- Removed the repeated `Either team can realistically win` / outcome-range chip from game cards.
- Removed simulation-range-derived risk copy from `Why this pick?`.
- Raw simulation interval fields remain available in the underlying published data for research/audit purposes; this patch only removes them from the public presentation layer.
- Preserves v1.3.3 custom tooltips, ATS market-line safeguards, CLV separation, recent-upload selection behavior, and V1.1.3B champion presentation.

## Rationale
Daily college-basketball slates are small enough that Top 25/50 controls add no practical value. The P10/P90-derived display also created a visually large range that was less useful to casual bettors than the model spread, projected score, and win probability already shown on the card.
