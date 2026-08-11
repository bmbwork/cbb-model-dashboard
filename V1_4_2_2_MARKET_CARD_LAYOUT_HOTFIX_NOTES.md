# CBB Dashboard v1.4.2.2 - Market Card Layout Hotfix

This is a presentation-only hotfix for the Market Pulse block on game cards.

## Fixes
- Adds the missing Market Pulse child classes so the three metrics receive their intended card styling.
- Adds the missing source/timestamp and readout styles.
- Removes empty BETS/MONEY placeholders when the active source is The Odds API and no split provider is connected.
- Replaces those empty columns with Sportsbook Line, Line Movement, and Book Consensus.
- Shortens first-snapshot copy to prevent wrapping and visual collisions.
- Stacks Market Pulse metrics on narrow screens.

## No model or grading changes
This patch does not modify V1.1.3B forecasts, Odds API fetching, Supabase schema, ATS grading, CLV logic, or stored market data.
