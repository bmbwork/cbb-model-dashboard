from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import requests

from .market import MarketDataError, normalize_market_import, normalize_team_name


@dataclass(frozen=True)
class OwlsInsightConfig:
    api_key: str
    timeout_seconds: int = 20


class OwlsInsightSplitsProvider:
    """Owls Insight NCAAB betting-splits adapter.

    Raw ticket/handle percentages are intended for the authenticated owner view.
    Public pages should consume only qualitative notes derived from these rows.
    """

    BASE_URL = "https://api.owlsinsight.com"

    def __init__(self, config: OwlsInsightConfig):
        key = str(config.api_key or "").strip()
        if not key:
            raise MarketDataError("Owls Insight API key is not configured.")
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "cbb-market-terminal/1.5.0",
        })
        self.last_rate_headers: dict[str, str] = {}

    @staticmethod
    def _num(value: Any) -> float:
        out = pd.to_numeric(value, errors="coerce")
        return float(out) if pd.notna(out) else float("nan")

    @staticmethod
    def _pct(value: Any) -> float:
        x = OwlsInsightSplitsProvider._num(value)
        if not np.isfinite(x):
            return float("nan")
        if abs(x) <= 1.000001:
            x *= 100.0
        return float(np.clip(x, 0.0, 100.0))

    @staticmethod
    def _get_alias(d: dict[str, Any], names: list[str], default: Any = None) -> Any:
        if not isinstance(d, dict):
            return default
        lower = {str(k).lower().replace("-", "_"): v for k, v in d.items()}
        for name in names:
            key = name.lower().replace("-", "_")
            if key in lower and lower[key] not in (None, ""):
                return lower[key]
        return default

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.BASE_URL}{path}"
        try:
            response = self.session.get(url, params=params or None, timeout=self.config.timeout_seconds)
            self.last_rate_headers = {
                "remaining_minute": str(response.headers.get("X-RateLimit-Remaining-Minute") or ""),
                "remaining_month": str(response.headers.get("X-RateLimit-Remaining-Month") or ""),
                "reset_minute": str(response.headers.get("X-RateLimit-Reset-Minute") or ""),
                "reset_month": str(response.headers.get("X-RateLimit-Reset-Month") or ""),
            }
            if response.status_code == 401:
                raise MarketDataError("Owls Insight rejected the API key (401). Check OWLS_INSIGHT_API_KEY in Streamlit Secrets.")
            if response.status_code == 403:
                raise MarketDataError("Owls Insight denied this endpoint (403). Confirm the subscription includes the requested feed.")
            if response.status_code == 429:
                raise MarketDataError("Owls Insight rate limit reached. Try again after the provider reset window.")
            response.raise_for_status()
            return response.json()
        except MarketDataError:
            raise
        except requests.RequestException as exc:
            raise MarketDataError(f"Owls Insight request failed safely ({type(exc).__name__}).") from exc
        except ValueError as exc:
            raise MarketDataError("Owls Insight returned a non-JSON response.") from exc

    def live_splits(self) -> Any:
        return self._get("/api/v1/ncaab/splits")

    @classmethod
    def _data_list(cls, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if isinstance(payload, dict):
            for key in ["data", "results", "games", "events", "items", "records"]:
                value = payload.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
                if isinstance(value, dict):
                    for nested in ["data", "results", "games", "events", "items", "records"]:
                        nested_value = value.get(nested)
                        if isinstance(nested_value, list):
                            return [x for x in nested_value if isinstance(x, dict)]
        return []

    @classmethod
    def _event_id(cls, event: dict[str, Any]) -> str:
        value = cls._get_alias(event, ["event_id", "eventId", "game_id", "gameId", "id"], "")
        if isinstance(value, dict):
            value = cls._get_alias(value, ["id", "event_id", "eventId"], "")
        return str(value or "")

    @classmethod
    def _team_name(cls, event: dict[str, Any], side: str) -> str:
        direct = cls._get_alias(event, [f"{side}_team", f"{side}Team", f"{side}_team_name", f"{side}TeamName"], "")
        if isinstance(direct, dict):
            direct = cls._get_alias(direct, ["name", "full_name", "fullName", "team"], "")
        if direct:
            return str(direct)
        game = cls._get_alias(event, ["game", "event", "matchup"], None)
        if isinstance(game, dict):
            return cls._team_name(game, side)
        return ""

    @staticmethod
    def _team_score(board_name: str, provider_name: str) -> float:
        b, p = normalize_team_name(board_name), normalize_team_name(provider_name)
        if not b or not p:
            return 0.0
        if b == p:
            return 1.0
        if b in p or p in b:
            return 0.90
        bt, pt = set(b.split()), set(p.split())
        union = len(bt | pt)
        return (len(bt & pt) / union) if union else 0.0

    def map_board_games(self, board: pd.DataFrame, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        used: set[str] = set()
        mapped: list[dict[str, Any]] = []
        for _, row in board.iterrows():
            bh, ba = str(row.get("Home Team") or ""), str(row.get("Away Team") or "")
            best: tuple[float, dict[str, Any], bool] | None = None
            for event in events:
                eid = self._event_id(event)
                if eid and eid in used:
                    continue
                eh, ea = self._team_name(event, "home"), self._team_name(event, "away")
                direct = (self._team_score(bh, eh) + self._team_score(ba, ea)) / 2.0
                swapped = (self._team_score(bh, ea) + self._team_score(ba, eh)) / 2.0
                score, is_swapped = (swapped, True) if swapped > direct else (direct, False)
                if best is None or score > best[0]:
                    best = (score, event, is_swapped)
            if best and best[0] >= 0.72:
                eid = self._event_id(best[1])
                if eid:
                    used.add(eid)
                mapped.append({
                    "board_row": row,
                    "event": best[1],
                    "provider_game_id": eid,
                    "swapped": best[2],
                    "match_score": best[0],
                })
        return mapped

    @classmethod
    def _book_nodes(cls, event: dict[str, Any]) -> list[dict[str, Any]]:
        value = cls._get_alias(event, ["splits", "books", "sportsbooks", "public_betting", "publicBetting"], None)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict):
            # Historical responses may key each sportsbook by name.
            out: list[dict[str, Any]] = []
            for key, node in value.items():
                if isinstance(node, dict):
                    item = dict(node)
                    item.setdefault("book", key)
                    out.append(item)
            if out:
                return out
        # Some historical endpoints return one row per sportsbook.
        if cls._get_alias(event, ["book", "sportsbook", "book_key", "bookKey"], ""):
            return [event]
        return []

    @classmethod
    def _market_node(cls, book: dict[str, Any], kind: str) -> dict[str, Any] | None:
        aliases = {
            "spread": ["spread", "spreads", "point_spread", "pointSpread"],
            "moneyline": ["moneyline", "money_line", "h2h", "ml"],
            "total": ["total", "totals", "over_under", "overUnder"],
        }
        value = cls._get_alias(book, aliases[kind], None)
        if isinstance(value, dict):
            return value
        # Flat historical row fallback.
        text_keys = " ".join(str(k).lower() for k in book.keys())
        if kind == "spread" and any(k in text_keys for k in ["spread", "home_bets", "away_bets"]):
            return book
        if kind == "moneyline" and any(k in text_keys for k in ["moneyline", "money_line", "home_ml"]):
            return book
        if kind == "total" and any(k in text_keys for k in ["over_bets", "under_bets", "over_handle", "under_handle"]):
            return book
        return None

    @classmethod
    def _field(cls, node: dict[str, Any], names: list[str]) -> float:
        return cls._num(cls._get_alias(node, names, np.nan))

    @classmethod
    def _pct_field(cls, node: dict[str, Any], names: list[str]) -> float:
        return cls._pct(cls._get_alias(node, names, np.nan))

    @classmethod
    def _snapshot_time(cls, payload: Any, event: dict[str, Any], book: dict[str, Any]) -> str:
        meta = payload.get("meta", {}) if isinstance(payload, dict) and isinstance(payload.get("meta"), dict) else {}
        aliases = [
            "timestamp", "updated_at", "updatedAt", "last_updated", "lastUpdated",
            "snapshot_time", "snapshotTime", "created_at", "createdAt",
            "commence_time", "commenceTime", "game_time", "gameTime",
        ]
        for obj in [book, event, payload if isinstance(payload, dict) else {}, meta]:
            raw = cls._get_alias(obj, aliases, None)
            ts = pd.to_datetime(raw, utc=True, errors="coerce")
            if pd.notna(ts):
                return ts.isoformat()
        # Historical public-betting records may omit an observation timestamp.
        # Use a deterministic end-of-day marker from the requested archive date
        # so rerunning the same backfill does not create duplicate hashes.
        hist_date = cls._get_alias(meta, ["date"], None)
        hist_day = pd.to_datetime(hist_date, utc=True, errors="coerce")
        if pd.notna(hist_day):
            return (hist_day.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)).isoformat()
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _parse_market_row(
        cls,
        payload: Any,
        board_row: pd.Series,
        event: dict[str, Any],
        provider_game_id: str,
        book: dict[str, Any],
        kind: str,
    ) -> dict[str, Any] | None:
        node = cls._market_node(book, kind)
        if not isinstance(node, dict):
            return None
        book_key = str(cls._get_alias(book, ["book", "sportsbook", "book_key", "bookKey", "key"], "unknown") or "unknown")
        book_title = str(cls._get_alias(book, ["title", "book_title", "bookTitle", "sportsbook_name", "sportsbookName", "name"], book_key) or book_key)
        common: dict[str, Any] = {
            "Slate Date": str(board_row.get("Target Date") or board_row.get("Slate Date") or ""),
            "Game ID": str(board_row.get("Game ID") or ""),
            "Provider": "owlsinsight",
            "Provider Game ID": str(provider_game_id or ""),
            "Source Label": f"Owls Insight · {book_title}",
            "Sportsbook Scope": book_key,
            "Snapshot Time UTC": cls._snapshot_time(payload, event, book),
            "Snapshot Role": "observed",
            "Market Type": kind,
        }
        if kind in {"spread", "moneyline"}:
            common.update({
                "Home Ticket %": cls._pct_field(node, ["home_bets_pct", "home_ticket_pct", "homeBetPct", "homeBetsPct", "home_tickets_pct"]),
                "Away Ticket %": cls._pct_field(node, ["away_bets_pct", "away_ticket_pct", "awayBetPct", "awayBetsPct", "away_tickets_pct"]),
                "Home Money %": cls._pct_field(node, ["home_handle_pct", "home_money_pct", "homeHandlePct", "homeMoneyPct"]),
                "Away Money %": cls._pct_field(node, ["away_handle_pct", "away_money_pct", "awayHandlePct", "awayMoneyPct"]),
            })
            if kind == "spread":
                common.update({
                    "Home Line": cls._field(node, ["home_line", "homeLine", "home_spread", "homeSpread"]),
                    "Away Line": cls._field(node, ["away_line", "awayLine", "away_spread", "awaySpread"]),
                })
            else:
                common.update({
                    "Home Price": cls._field(node, ["home_price", "homePrice", "home_odds", "homeOdds"]),
                    "Away Price": cls._field(node, ["away_price", "awayPrice", "away_odds", "awayOdds"]),
                })
        else:
            common.update({
                "Total Line": cls._field(node, ["line", "total_line", "totalLine", "total"]),
                "Over Ticket %": cls._pct_field(node, ["over_bets_pct", "over_ticket_pct", "overBetsPct", "overTicketPct"]),
                "Under Ticket %": cls._pct_field(node, ["under_bets_pct", "under_ticket_pct", "underBetsPct", "underTicketPct"]),
                "Over Money %": cls._pct_field(node, ["over_handle_pct", "over_money_pct", "overHandlePct", "overMoneyPct"]),
                "Under Money %": cls._pct_field(node, ["under_handle_pct", "under_money_pct", "underHandlePct", "underMoneyPct"]),
            })
        pct_cols = [k for k in common if "%" in k]
        if not any(np.isfinite(cls._num(common.get(k))) for k in pct_cols):
            return None
        return common

    def parse(self, payload: Any, board: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
        events = self._data_list(payload)
        mapped = self.map_board_games(board, events)
        rows: list[dict[str, Any]] = []
        empty_games: list[str] = []
        for item in mapped:
            event = item["event"]
            board_row = item["board_row"]
            books = self._book_nodes(event)
            before = len(rows)
            for book in books:
                for kind in ["spread", "moneyline", "total"]:
                    parsed = self._parse_market_row(payload, board_row, event, item["provider_game_id"], book, kind)
                    if parsed:
                        rows.append(parsed)
            if len(rows) == before:
                empty_games.append(str(board_row.get("Game ID") or ""))
        frame = normalize_market_import(pd.DataFrame(rows)) if rows else pd.DataFrame()
        health = {
            "board_games": int(len(board)),
            "provider_events": int(len(events)),
            "mapped_games": int(len(mapped)),
            "split_games": int(frame["Game ID"].nunique()) if not frame.empty else 0,
            "split_rows": int(len(frame)),
            "empty_games": empty_games,
            "rate": dict(self.last_rate_headers),
        }
        return frame, health

    def refresh(self, board: pd.DataFrame, slate_date: str | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Fetch the current NCAAB split feed and map it to the selected live board.

        V1.4.7 intentionally does not use Owls historical public-betting backfill.
        Historical split history is built from snapshots captured live into our
        private Supabase archive.
        """
        payload = self.live_splits()
        frame, health = self.parse(payload, board)
        health["mode"] = "live"
        health["requested_date"] = str(slate_date or "")
        health["records_fetched"] = int(health.get("provider_events", 0))
        return frame, health


def _leader(home: str, away: str, home_pct: float, away_pct: float) -> tuple[str, float]:
    if not (np.isfinite(home_pct) or np.isfinite(away_pct)):
        return "", float("nan")
    if not np.isfinite(home_pct):
        home_pct = 100.0 - away_pct
    if not np.isfinite(away_pct):
        away_pct = 100.0 - home_pct
    return (home, home_pct) if home_pct >= away_pct else (away, away_pct)


# These are dashboard interpretation thresholds, not Owls Insight provider-defined
# cutoffs and not predictive-model inputs. Owls documents that handle/ticket
# divergence can indicate sharp action; we use a deliberately conservative gap
# before surfacing that qualitative signal.
SHARP_GAP_WATCH = 10.0
SHARP_GAP_STRONG = 15.0
SHARP_GAP_VERY_STRONG = 25.0


def _sharp_strength(gap: float, leader_flip: bool = False) -> str:
    if not np.isfinite(gap) or gap < SHARP_GAP_WATCH:
        return ""
    if gap >= SHARP_GAP_VERY_STRONG:
        return "very strong"
    if gap >= SHARP_GAP_STRONG or leader_flip:
        return "strong"
    return "possible"


def _row_sharp_candidate(row: pd.Series, home: str, away: str) -> dict[str, Any]:
    kind = str(row.get("Market Type") or "").strip().lower()
    if kind in {"spread", "moneyline"}:
        ticket_home = pd.to_numeric(row.get("Home Ticket %"), errors="coerce")
        ticket_away = pd.to_numeric(row.get("Away Ticket %"), errors="coerce")
        money_home = pd.to_numeric(row.get("Home Money %"), errors="coerce")
        money_away = pd.to_numeric(row.get("Away Money %"), errors="coerce")
        candidates = []
        if pd.notna(ticket_home) and pd.notna(money_home):
            candidates.append((home, float(money_home - ticket_home)))
        if pd.notna(ticket_away) and pd.notna(money_away):
            candidates.append((away, float(money_away - ticket_away)))
        ticket_team, _ = _leader(home, away, float(ticket_home), float(ticket_away))
        money_team, _ = _leader(home, away, float(money_home), float(money_away))
    elif kind == "total":
        ticket_over = pd.to_numeric(row.get("Over Ticket %"), errors="coerce")
        ticket_under = pd.to_numeric(row.get("Under Ticket %"), errors="coerce")
        money_over = pd.to_numeric(row.get("Over Money %"), errors="coerce")
        money_under = pd.to_numeric(row.get("Under Money %"), errors="coerce")
        candidates = []
        if pd.notna(ticket_over) and pd.notna(money_over):
            candidates.append(("Over", float(money_over - ticket_over)))
        if pd.notna(ticket_under) and pd.notna(money_under):
            candidates.append(("Under", float(money_under - ticket_under)))
        ticket_team, _ = _leader("Over", "Under", float(ticket_over), float(ticket_under))
        money_team, _ = _leader("Over", "Under", float(money_over), float(money_under))
    else:
        return {"side": "", "gap": float("nan"), "strength": "", "signal": "none", "read": "", "ticket_leader": "", "money_leader": ""}

    if not candidates:
        return {"side": "", "gap": float("nan"), "strength": "", "signal": "none", "read": "", "ticket_leader": "", "money_leader": ""}
    side, gap = max(candidates, key=lambda x: x[1])
    leader_flip = bool(ticket_team and money_team and ticket_team != money_team and side == money_team)
    strength = _sharp_strength(gap, leader_flip=leader_flip)
    if not strength:
        return {"side": "", "gap": gap, "strength": "", "signal": "none", "read": "", "ticket_leader": ticket_team, "money_leader": money_team}

    if leader_flip:
        read = f"Money leads toward {side} even though more individual bets are on the other side."
        signal = "leader_flip"
    else:
        read = f"The dollar share on {side} is meaningfully heavier than its share of individual bets."
        signal = "money_over_tickets"
    return {"side": side, "gap": gap, "strength": strength, "signal": signal, "read": read, "ticket_leader": ticket_team, "money_leader": money_team}


def annotate_sharp_money_signals(raw_splits: pd.DataFrame, board: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add owner-only sharp-money diagnostics to split rows.

    No raw percentage or sharp diagnostic is required on public pages. The
    resulting Provider Signals value is persisted only in the owner split table.
    """
    if raw_splits is None or raw_splits.empty:
        return pd.DataFrame() if raw_splits is None else raw_splits.copy()
    frame = normalize_market_import(raw_splits)
    names: dict[str, tuple[str, str]] = {}
    if board is not None and not board.empty:
        for _, b in board.iterrows():
            names[str(b.get("Game ID") or "")] = (str(b.get("Home Team") or "Home"), str(b.get("Away Team") or "Away"))

    ticket_leaders: list[str] = []
    money_leaders: list[str] = []
    sides: list[str] = []
    gaps: list[float] = []
    strengths: list[str] = []
    signals: list[str] = []
    reads: list[str] = []
    provider_signals: list[str] = []
    for _, row in frame.iterrows():
        home, away = names.get(str(row.get("Game ID") or ""), ("Home", "Away"))
        sharp = _row_sharp_candidate(row, home, away)
        ticket_leaders.append(str(sharp.get("ticket_leader") or ""))
        money_leaders.append(str(sharp.get("money_leader") or ""))
        sides.append(str(sharp["side"] or ""))
        gaps.append(float(sharp["gap"]) if np.isfinite(sharp["gap"]) else np.nan)
        strengths.append(str(sharp["strength"] or ""))
        signals.append(str(sharp["signal"] or "none"))
        reads.append(str(sharp["read"] or ""))
        existing = str(row.get("Provider Signals") or "").strip()
        if sharp["side"]:
            token = f"sharp_money:{sharp['side']}|gap={sharp['gap']:.1f}|strength={sharp['strength']}|basis={sharp['signal']}"
            provider_signals.append(" | ".join(x for x in [existing, token] if x))
        else:
            provider_signals.append(existing)
    frame["Ticket Leader"] = ticket_leaders
    frame["Money Leader"] = money_leaders
    frame["Sharp Side"] = sides
    frame["Sharp Gap Pts"] = gaps
    frame["Sharp Strength"] = strengths
    frame["Sharp Signal"] = signals
    frame["Sharp Read"] = reads
    frame["Provider Signals"] = provider_signals
    return frame


def _aggregate_sharp_spread(group: pd.DataFrame, home: str, away: str) -> dict[str, Any]:
    ann = annotate_sharp_money_signals(group, pd.DataFrame([{"Game ID": str(group.iloc[0].get("Game ID") or ""), "Home Team": home, "Away Team": away}]))
    ann = ann[(ann["Market Type"].astype(str) == "spread") & ann["Sharp Side"].astype(str).str.strip().ne("")].copy()
    if ann.empty:
        return {"side": "", "signal": "none", "confidence": "none", "note": "", "books": ""}

    # Keep one current candidate per sportsbook so repeated observations do not
    # give a book extra voting weight.
    if "Snapshot Time UTC" in ann.columns:
        ann["Snapshot Time UTC"] = pd.to_datetime(ann["Snapshot Time UTC"], utc=True, errors="coerce")
        ann = ann.sort_values("Snapshot Time UTC")
    ann = ann.drop_duplicates("Sportsbook Scope", keep="last")
    sides = [str(x) for x in ann["Sharp Side"].tolist() if str(x).strip()]
    books = sorted({str(x) for x in ann["Source Label"].dropna().astype(str) if str(x).strip()})
    unique = sorted(set(sides))
    if not sides:
        return {"side": "", "signal": "none", "confidence": "none", "note": "", "books": " | ".join(books)}
    if len(unique) > 1:
        return {
            "side": "",
            "signal": "sharp_mixed",
            "confidence": "mixed",
            "note": "Sharp-money signals disagree across the available sportsbooks, so there is no clean professional-money read.",
            "books": " | ".join(books),
        }

    side = unique[0]
    leader_flips = ann["Sharp Signal"].astype(str).eq("leader_flip").sum()
    max_gap = pd.to_numeric(ann["Sharp Gap Pts"], errors="coerce").max()
    if len(sides) >= 2:
        confidence = "strong" if leader_flips > 0 or (pd.notna(max_gap) and max_gap >= SHARP_GAP_STRONG) else "moderate"
        signal = "sharp_consensus"
        note = (
            f"Sharp-money signals from multiple sportsbooks point toward {side}. The dollars are disproportionately heavier on that side than the number of individual bets, "
            "a pattern that can indicate larger or more informed wagers. It does not prove who placed the bets."
        )
    else:
        confidence = str(ann.iloc[0].get("Sharp Strength") or "possible")
        signal = "sharp_possible"
        note = (
            f"There is a possible sharp-money signal toward {side}: the dollars are more concentrated there than the number of individual bets. "
            "That can indicate larger wagers, but one split source is not enough to call professional action confirmed."
        )
    return {"side": side, "signal": signal, "confidence": confidence, "note": note, "books": " | ".join(books)}


def derive_public_betting_notes(board: pd.DataFrame, raw_splits: pd.DataFrame) -> list[dict[str, Any]]:
    """Turn private split percentages into non-numeric public commentary.

    Sharp-money wording is a downstream interpretation of the provider's
    ticket-vs-handle split, never a model input and never proof of bettor identity.
    """
    if raw_splits is None or raw_splits.empty:
        return []
    normalized = annotate_sharp_money_signals(raw_splits, board)
    spread = normalized[normalized["Market Type"].eq("spread")].copy()
    if spread.empty:
        return []
    by_game = {str(gid): group for gid, group in spread.groupby(spread["Game ID"].astype(str))}
    now = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, Any]] = []
    for _, row in board.iterrows():
        gid = str(row.get("Game ID") or "")
        group = by_game.get(gid)
        if group is None or group.empty:
            continue
        home, away = str(row.get("Home Team") or "Home"), str(row.get("Away Team") or "Away")
        pick = str(row.get("Model Pick") or "")
        ht = pd.to_numeric(group["Home Ticket %"], errors="coerce").mean()
        at = pd.to_numeric(group["Away Ticket %"], errors="coerce").mean()
        hm = pd.to_numeric(group["Home Money %"], errors="coerce").mean()
        am = pd.to_numeric(group["Away Money %"], errors="coerce").mean()
        ticket_team, ticket_pct = _leader(home, away, float(ht), float(at))
        money_team, money_pct = _leader(home, away, float(hm), float(am))
        sharp = _aggregate_sharp_spread(group, home, away)
        sharp_side = str(sharp.get("side") or "")
        sharp_signal = str(sharp.get("signal") or "none")
        sharp_confidence = str(sharp.get("confidence") or "none")
        if not ticket_team and not money_team and not sharp_side:
            continue

        signal = "mixed"
        label = "Mixed betting action"
        sentences: list[str] = []
        if ticket_team and money_team and ticket_team != money_team:
            signal = "money_disagrees"
            label = "Bets and money disagree"
            sentences.append(f"More individual bets are on {ticket_team}, but more of the money is on {money_team}. That means the average wager is larger on {money_team}.")
        elif ticket_team:
            if np.isfinite(ticket_pct) and ticket_pct >= 70:
                signal = "public_heavy"
                label = f"Public heavily on {ticket_team}"
                sentences.append(f"The betting public is heavily backing {ticket_team}. Popularity is not the same as value, so be careful about blindly following the crowd if the price has already moved.")
            elif np.isfinite(ticket_pct) and ticket_pct >= 60:
                signal = "public_lean"
                label = f"Public leaning {ticket_team}"
                sentences.append(f"The betting public is leaning toward {ticket_team}, but the crowd is not one-sided enough to treat this as a major signal by itself.")
            else:
                signal = "balanced"
                label = "Betting action fairly balanced"
                sentences.append("Betting action is fairly balanced. There is no strong public-side warning from the ticket split.")
            if money_team == ticket_team and np.isfinite(money_pct) and money_pct >= 60:
                sentences.append(f"The money is leaning the same way toward {ticket_team}, so both ticket count and dollars point to the same side.")

        sharp_note = str(sharp.get("note") or "")
        if sharp_signal == "sharp_consensus" and sharp_side:
            label = f"Sharp-money signal: {sharp_side}"
            sentences.append(sharp_note)
        elif sharp_signal == "sharp_possible" and sharp_side:
            if signal in {"balanced", "mixed"}:
                label = f"Possible sharp money: {sharp_side}"
            sentences.append(sharp_note)
        elif sharp_signal == "sharp_mixed":
            sentences.append(sharp_note)

        if pick:
            opponent = away if pick == home else home
            if sharp_side:
                if pick == sharp_side:
                    sentences.append(f"The model independently agrees with the sharp-money side on {pick}. That is supportive market context, not an input to the model.")
                elif opponent == sharp_side:
                    sentences.append(f"The model likes {pick}, but the sharp-money signal favors {opponent}. Treat that disagreement as a risk flag rather than an automatic reason to abandon the model pick.")
            elif ticket_team and money_team:
                if ticket_team != money_team and money_team == pick:
                    sentences.append(f"The model also likes {pick}, so it lines up with the money side rather than the more popular side. That is supportive market context, not an input to the model.")
                elif ticket_team == pick and money_team != pick:
                    sentences.append(f"The model likes {pick}, but more of the money is on {opponent}. Treat that disagreement as a risk flag, not an automatic reason to fade the model.")
                elif ticket_team == pick and money_team == pick:
                    sentences.append(f"The model, the crowd, and the money all point toward {pick}. That agreement can be reassuring, but it also means this is not a contrarian setup.")
                elif ticket_team == opponent and money_team == opponent:
                    sentences.append(f"The model is on the less-popular side: both the crowd and the money favor {opponent}. That is useful context, but it does not make {pick} automatically valuable.")

        books = sorted({str(x) for x in group["Source Label"].dropna().astype(str) if str(x).strip()})
        records.append({
            "slate_date": str(row.get("Target Date") or row.get("Slate Date") or ""),
            "game_id": gid,
            "betting_public_side": ticket_team or None,
            "betting_money_side": money_team or None,
            "betting_signal": signal,
            "betting_label": label,
            "betting_note": " ".join(sentences).strip(),
            "betting_source": "Owls Insight",
            "betting_books": " | ".join(books),
            "betting_updated_at": now,
            "betting_sharp_side": sharp_side or None,
            "betting_sharp_signal": sharp_signal,
            "betting_sharp_confidence": sharp_confidence,
            "betting_sharp_note": sharp_note or None,
            "betting_sharp_books": str(sharp.get("books") or ""),
        })
    return records
