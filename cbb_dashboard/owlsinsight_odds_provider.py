from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import numpy as np
import pandas as pd
import requests

from .market import MarketDataError, normalize_team_name


DEFAULT_BOOKS = (
    "pinnacle,circa,draftkings,fanduel,betmgm,caesars,bet365,hardrock,"
    "westgate,wynn,south_point,stations"
)

DEFAULT_REFERENCE_PRIORITY = (
    "draftkings",
    "fanduel",
    "pinnacle",
    "circa",
    "betmgm",
    "caesars",
    "bet365",
    "hardrock",
    "westgate",
    "wynn",
    "south_point",
    "stations",
)

SHARP_BOOKS = ("pinnacle", "circa")
RETAIL_BOOKS = ("draftkings", "fanduel")
VALID_SNAPSHOT_ROLES = {"observed", "open", "decision", "close"}

TEAM_ALIASES = {
    "uconn": "connecticut",
    "unc": "north carolina",
    "nc state": "north carolina state",
    "ole miss": "mississippi",
    "usc": "southern california",
    "lsu": "louisiana state",
    "smu": "southern methodist",
    "tcu": "texas christian",
    "ucf": "central florida",
    "byu": "brigham young",
    "vcu": "virginia commonwealth",
    "umass": "massachusetts",
    "utep": "texas el paso",
    "utsa": "texas san antonio",
    "uab": "alabama birmingham",
    "unlv": "nevada las vegas",
    "uncw": "north carolina wilmington",
    "uncg": "north carolina greensboro",
    "app state": "appalachian state",
    "pitt": "pittsburgh",
}


@dataclass(frozen=True)
class OwlsInsightOddsConfig:
    api_key: str
    books: str = DEFAULT_BOOKS
    reference_bookmaker: str = "draftkings"
    timeout_seconds: int = 20
    exclude_exchanges: bool = True
    alternates: bool = False


class OwlsInsightOddsProvider:
    """Owls Insight NCAAB sportsbook-odds adapter.

    The adapter is intentionally downstream from the V1.1.3B forecast. It emits
    the existing provider-agnostic market snapshot schema so Supabase provenance,
    ATS decision-line grading, and CLV close-line logic stay unchanged.
    """

    BASE_URL = "https://api.owlsinsight.com"

    def __init__(self, config: OwlsInsightOddsConfig):
        key = str(config.api_key or "").strip()
        if not key:
            raise MarketDataError("Owls Insight API key is not configured.")
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "cbb-market-terminal/1.5.0",
            }
        )
        self.last_rate_headers: dict[str, str] = {}
        self.last_meta: dict[str, Any] = {}

    @staticmethod
    def _canonical_team(value: Any) -> str:
        text = normalize_team_name(value)
        if text.startswith("st "):
            text = "saint " + text[3:]
        return TEAM_ALIASES.get(text, text)

    @classmethod
    def _team_score(cls, board_name: str, provider_name: str) -> float:
        b, p = cls._canonical_team(board_name), cls._canonical_team(provider_name)
        if not b or not p:
            return 0.0
        if b == p:
            return 1.0
        if b in p or p in b:
            return 0.94
        bt, pt = set(b.split()), set(p.split())
        union = len(bt | pt)
        jaccard = (len(bt & pt) / union) if union else 0.0
        sequence = SequenceMatcher(None, b, p).ratio()
        return max(jaccard, sequence * 0.88)

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
                raise MarketDataError(
                    "Owls Insight rejected the API key (401). Check OWLS_INSIGHT_API_KEY in Streamlit Secrets."
                )
            if response.status_code == 403:
                raise MarketDataError(
                    "Owls Insight denied the NCAAB odds endpoint (403). Confirm the MVP subscription is active."
                )
            if response.status_code == 429:
                raise MarketDataError(
                    "Owls Insight rate limit reached. Try again after the provider reset window."
                )
            response.raise_for_status()
            payload = response.json()
        except MarketDataError:
            raise
        except requests.RequestException as exc:
            raise MarketDataError(f"Owls Insight odds request failed safely ({type(exc).__name__}).") from exc
        except ValueError as exc:
            raise MarketDataError("Owls Insight returned a non-JSON odds response.") from exc

        if isinstance(payload, dict) and payload.get("success") is False:
            message = str(payload.get("message") or payload.get("error") or "provider returned success=false")
            raise MarketDataError(f"Owls Insight odds request failed: {message}")
        return payload

    def current_odds(self) -> Any:
        params: dict[str, Any] = {
            "exclude_exchanges": "true" if self.config.exclude_exchanges else "false",
            "alternates": "true" if self.config.alternates else "false",
        }
        books = ",".join(x.strip().lower() for x in str(self.config.books or "").split(",") if x.strip())
        if books:
            params["books"] = books
        return self._get("/api/v1/ncaab/odds", params)

    @staticmethod
    def _market(book: dict[str, Any], key: str) -> dict[str, Any] | None:
        for market in book.get("markets") or []:
            if isinstance(market, dict) and str(market.get("key") or "").lower() == key:
                return market
        return None

    @classmethod
    def _outcome(cls, market: dict[str, Any] | None, name: str) -> dict[str, Any] | None:
        if not market:
            return None
        target = cls._canonical_team(name)
        for outcome in market.get("outcomes") or []:
            if not isinstance(outcome, dict):
                continue
            raw = str(outcome.get("name") or "")
            if raw.lower() in {"over", "under"}:
                if raw.lower() == str(name).lower():
                    return outcome
            elif cls._canonical_team(raw) == target:
                return outcome
        return None

    @staticmethod
    def _parse_timestamp(value: Any) -> pd.Timestamp:
        return pd.to_datetime(value, utc=True, errors="coerce")

    @classmethod
    def _book_update(cls, book: dict[str, Any]) -> pd.Timestamp:
        candidates: list[Any] = [book.get("last_update"), book.get("updated_at")]
        for market in book.get("markets") or []:
            if isinstance(market, dict):
                candidates.extend([market.get("last_update"), market.get("updated_at")])
        stamps = [cls._parse_timestamp(x) for x in candidates]
        stamps = [x for x in stamps if pd.notna(x)]
        return max(stamps) if stamps else pd.NaT

    @classmethod
    def _event_group_key(cls, event: dict[str, Any]) -> tuple[str, str, str]:
        home = cls._canonical_team(event.get("home_team"))
        away = cls._canonical_team(event.get("away_team"))
        stamp = cls._parse_timestamp(event.get("commence_time"))
        day = stamp.strftime("%Y-%m-%d") if pd.notna(stamp) else ""
        if home or away:
            # Owls normalizes event structure, but grouping on the unordered matchup
            # also protects cross-book coalescing if a source flips home/away labels.
            first, second = sorted((home, away))
            return first, second, day
        return str(event.get("id") or ""), "", day

    @classmethod
    def _coalesce_events(cls, payload: Any) -> list[dict[str, Any]]:
        """Merge the unified per-book response into one event with many books."""
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if not isinstance(data, dict):
            return []

        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for outer_book, events in data.items():
            if not isinstance(events, list):
                continue
            for raw_event in events:
                if not isinstance(raw_event, dict):
                    continue
                key = cls._event_group_key(raw_event)
                if key not in grouped:
                    grouped[key] = {
                        "id": str(raw_event.get("id") or ""),
                        "sport_key": raw_event.get("sport_key"),
                        "commence_time": raw_event.get("commence_time"),
                        "home_team": raw_event.get("home_team"),
                        "away_team": raw_event.get("away_team"),
                        "bookmakers": [],
                        "provider_ids": {},
                    }
                merged = grouped[key]
                event_id = str(raw_event.get("id") or "")
                if event_id:
                    merged.setdefault("provider_ids", {})[str(outer_book).lower()] = event_id
                    if not merged.get("id"):
                        merged["id"] = event_id
                if not merged.get("commence_time") and raw_event.get("commence_time"):
                    merged["commence_time"] = raw_event.get("commence_time")

                books = [x for x in (raw_event.get("bookmakers") or []) if isinstance(x, dict)]
                if not books and raw_event.get("markets"):
                    books = [
                        {
                            "key": str(outer_book),
                            "title": str(outer_book),
                            "last_update": raw_event.get("last_update"),
                            "markets": raw_event.get("markets") or [],
                        }
                    ]
                for book in books:
                    item = dict(book)
                    item.setdefault("key", str(outer_book))
                    item.setdefault("title", str(outer_book))
                    existing = {
                        str(x.get("key") or "").lower(): x
                        for x in merged["bookmakers"]
                        if isinstance(x, dict)
                    }
                    bkey = str(item.get("key") or outer_book).lower()
                    current = existing.get(bkey)
                    if current is None:
                        merged["bookmakers"].append(item)
                    else:
                        current_ts = cls._book_update(current)
                        item_ts = cls._book_update(item)
                        if pd.isna(current_ts) or (pd.notna(item_ts) and item_ts >= current_ts):
                            merged["bookmakers"] = [
                                item if str(x.get("key") or "").lower() == bkey else x
                                for x in merged["bookmakers"]
                            ]
        return list(grouped.values())

    def _reference_book(self, event: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
        books = [b for b in event.get("bookmakers") or [] if isinstance(b, dict)]
        if not books:
            return None, False
        by_key = {str(b.get("key") or "").lower(): b for b in books}
        preferred = str(self.config.reference_bookmaker or "").lower().strip()
        if preferred and preferred in by_key:
            return by_key[preferred], False
        for key in DEFAULT_REFERENCE_PRIORITY:
            if key in by_key:
                return by_key[key], True
        return books[0], True

    @classmethod
    def _last_update(
        cls,
        book: dict[str, Any] | None,
        market: dict[str, Any] | None,
        fallback: str = "",
    ) -> str:
        value = (market or {}).get("last_update") or (book or {}).get("last_update") or fallback
        stamp = cls._parse_timestamp(value)
        if pd.isna(stamp):
            stamp = pd.Timestamp.now(tz="UTC")
        return stamp.isoformat()

    @classmethod
    def _spread_values_by_book(
        cls, event: dict[str, Any], board_home_provider_name: str
    ) -> dict[str, float]:
        values: dict[str, float] = {}
        for book in event.get("bookmakers") or []:
            if not isinstance(book, dict):
                continue
            market = cls._market(book, "spreads")
            outcome = cls._outcome(market, board_home_provider_name)
            point = pd.to_numeric((outcome or {}).get("point"), errors="coerce")
            if pd.notna(point):
                values[str(book.get("key") or book.get("title") or "unknown").lower()] = float(point)
        return values

    @classmethod
    def _book_spread_summary(
        cls, event: dict[str, Any], board_home_provider_name: str
    ) -> dict[str, Any]:
        by_book = cls._spread_values_by_book(event, board_home_provider_name)
        values = list(by_book.values())
        if not values:
            return {
                "count": np.nan,
                "min": np.nan,
                "max": np.nan,
                "range": np.nan,
                "agreement": "",
                "consensus": np.nan,
                "sharp": np.nan,
                "retail": np.nan,
                "sharp_count": 0,
            }
        lo, hi = min(values), max(values)
        spread_range = hi - lo
        agreement = "tight" if spread_range <= 0.5 else ("mixed" if spread_range <= 1.5 else "wide")
        sharp_values = [by_book[k] for k in SHARP_BOOKS if k in by_book]
        retail_values = [by_book[k] for k in RETAIL_BOOKS if k in by_book]
        return {
            "count": len(values),
            "min": lo,
            "max": hi,
            "range": spread_range,
            "agreement": agreement,
            "consensus": float(np.median(values)),
            "sharp": float(np.median(sharp_values)) if sharp_values else np.nan,
            "retail": float(np.median(retail_values)) if retail_values else np.nan,
            "sharp_count": len(sharp_values),
        }

    @staticmethod
    def _fmt_signal(value: Any) -> str:
        number = pd.to_numeric(value, errors="coerce")
        return f"{float(number):+.2f}" if pd.notna(number) else "na"

    @classmethod
    def _provider_signals(cls, summary: dict[str, Any]) -> str:
        return (
            f"consensus_home_spread={cls._fmt_signal(summary.get('consensus'))};"
            f"sharp_home_spread={cls._fmt_signal(summary.get('sharp'))};"
            f"retail_home_spread={cls._fmt_signal(summary.get('retail'))};"
            f"sharp_books={int(summary.get('sharp_count') or 0)}"
        )

    def map_board_games(self, board: pd.DataFrame, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        available = [e for e in events if isinstance(e, dict)]
        used: set[str] = set()
        mapped: list[dict[str, Any]] = []
        for _, row in board.iterrows():
            bh, ba = str(row.get("Home Team") or ""), str(row.get("Away Team") or "")
            board_start = self._parse_timestamp(row.get("Start Time UTC"))
            best: tuple[float, dict[str, Any], bool] | None = None
            for event in available:
                event_key = "|".join(str(x) for x in self._event_group_key(event))
                if event_key in used:
                    continue
                event_start = self._parse_timestamp(event.get("commence_time"))
                if pd.notna(board_start) and pd.notna(event_start):
                    time_gap_hours = abs((event_start - board_start).total_seconds()) / 3600.0
                    if time_gap_hours > 8.0:
                        continue
                eh, ea = str(event.get("home_team") or ""), str(event.get("away_team") or "")
                direct = (self._team_score(bh, eh) + self._team_score(ba, ea)) / 2.0
                swapped = (self._team_score(bh, ea) + self._team_score(ba, eh)) / 2.0
                score, is_swapped = (swapped, True) if swapped > direct else (direct, False)
                if pd.notna(board_start) and pd.notna(event_start):
                    time_gap_hours = abs((event_start - board_start).total_seconds()) / 3600.0
                    if time_gap_hours <= 1.0:
                        score = min(1.0, score + 0.03)
                if best is None or score > best[0]:
                    best = (score, event, is_swapped)
            if best and best[0] >= 0.78:
                event_key = "|".join(str(x) for x in self._event_group_key(best[1]))
                used.add(event_key)
                mapped.append(
                    {
                        "board_row": row,
                        "event": best[1],
                        "swapped": best[2],
                        "match_score": best[0],
                    }
                )
        return mapped

    def parse_event(
        self,
        event: dict[str, Any],
        row: pd.Series,
        *,
        swapped: bool = False,
        snapshot_role: str = "observed",
        response_timestamp: str = "",
    ) -> tuple[pd.DataFrame, bool]:
        role = str(snapshot_role or "observed").strip().lower()
        if role not in VALID_SNAPSHOT_ROLES:
            raise MarketDataError(
                "Snapshot role must be one of: observed, open, decision, close."
            )
        ref, used_fallback = self._reference_book(event)
        if ref is None:
            return pd.DataFrame(), used_fallback

        provider_home = str(event.get("home_team") or "")
        provider_away = str(event.get("away_team") or "")
        board_home_provider_name = provider_away if swapped else provider_home
        board_away_provider_name = provider_home if swapped else provider_away
        ref_key = str(ref.get("key") or "").lower()
        ref_title = str(ref.get("title") or ref.get("key") or "sportsbook")
        provider_ids = event.get("provider_ids") if isinstance(event.get("provider_ids"), dict) else {}
        provider_game_id = str(provider_ids.get(ref_key) or event.get("id") or "")
        start = self._parse_timestamp(event.get("commence_time") or row.get("Start Time UTC"))
        summary = self._book_spread_summary(event, board_home_provider_name)
        book_count = int(summary["count"]) if np.isfinite(summary["count"]) else 0
        sharp_count = int(summary.get("sharp_count") or 0)
        scope = f"{ref_title} reference · {book_count} books compared · sharp {sharp_count}/2"
        source = f"Owls Insight · {ref_title}"
        signal_text = self._provider_signals(summary)
        board_date = str(row.get("Target Date") or "").strip()
        if not board_date and pd.notna(start):
            board_date = str(start.date())

        rows: list[dict[str, Any]] = []

        def common(market_key: str, stamp: str) -> dict[str, Any]:
            st = self._parse_timestamp(stamp)
            if pd.isna(st):
                st = pd.Timestamp.now(tz="UTC")
            mins = (start - st).total_seconds() / 60.0 if pd.notna(start) else np.nan
            return {
                "Slate Date": board_date,
                "Game ID": str(row.get("Game ID") or ""),
                "Provider": "owls_insight_odds",
                "Provider Game ID": provider_game_id,
                "Snapshot Time UTC": st.isoformat(),
                "Snapshot Role": role,
                "Minutes To Tip": mins,
                "Market Type": market_key,
                "Source Label": source,
                "Sportsbook Scope": scope,
                "Activity Level": "",
                "Ticket Count": np.nan,
                "Provider Signals": signal_text if market_key == "spread" else "",
                "Book Count": summary["count"] if market_key == "spread" else np.nan,
                "Home Spread Min": summary["min"] if market_key == "spread" else np.nan,
                "Home Spread Max": summary["max"] if market_key == "spread" else np.nan,
                "Book Spread Range": summary["range"] if market_key == "spread" else np.nan,
                "Book Agreement": summary["agreement"] if market_key == "spread" else "",
            }

        spread = self._market(ref, "spreads")
        if spread and not bool(spread.get("suspended")):
            home = self._outcome(spread, board_home_provider_name)
            away = self._outcome(spread, board_away_provider_name)
            home_point = pd.to_numeric((home or {}).get("point"), errors="coerce")
            away_point = pd.to_numeric((away or {}).get("point"), errors="coerce")
            if pd.notna(home_point) or pd.notna(away_point):
                stamp = self._last_update(ref, spread, response_timestamp)
                item = common("spread", stamp)
                item.update(
                    {
                        "Home Line": home_point,
                        "Away Line": away_point,
                        "Opening Home Line": home_point if role == "open" else np.nan,
                        "Opening Away Line": away_point if role == "open" else np.nan,
                        "Home Price": pd.to_numeric((home or {}).get("price"), errors="coerce"),
                        "Away Price": pd.to_numeric((away or {}).get("price"), errors="coerce"),
                    }
                )
                rows.append(item)

        h2h = self._market(ref, "h2h")
        if h2h and not bool(h2h.get("suspended")):
            home = self._outcome(h2h, board_home_provider_name)
            away = self._outcome(h2h, board_away_provider_name)
            if home or away:
                stamp = self._last_update(ref, h2h, response_timestamp)
                item = common("moneyline", stamp)
                item.update(
                    {
                        "Home Price": pd.to_numeric((home or {}).get("price"), errors="coerce"),
                        "Away Price": pd.to_numeric((away or {}).get("price"), errors="coerce"),
                    }
                )
                rows.append(item)

        total = self._market(ref, "totals")
        if total and not bool(total.get("suspended")):
            over = self._outcome(total, "Over")
            under = self._outcome(total, "Under")
            point = pd.to_numeric((over or under or {}).get("point"), errors="coerce")
            if pd.notna(point):
                stamp = self._last_update(ref, total, response_timestamp)
                item = common("total", stamp)
                item.update(
                    {
                        "Total Line": point,
                        "Opening Total": point if role == "open" else np.nan,
                        "Over Price": pd.to_numeric((over or {}).get("price"), errors="coerce"),
                        "Under Price": pd.to_numeric((under or {}).get("price"), errors="coerce"),
                    }
                )
                rows.append(item)

        return pd.DataFrame(rows), used_fallback

    def refresh(
        self,
        board: pd.DataFrame,
        *,
        snapshot_role: str = "observed",
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        if board is None or board.empty:
            raise MarketDataError("Publish/select a board before refreshing market data.")
        role = str(snapshot_role or "observed").strip().lower()
        if role not in VALID_SNAPSHOT_ROLES:
            raise MarketDataError(
                "Snapshot role must be one of: observed, open, decision, close."
            )

        payload = self.current_odds()
        meta = payload.get("meta", {}) if isinstance(payload, dict) and isinstance(payload.get("meta"), dict) else {}
        self.last_meta = dict(meta)
        events = self._coalesce_events(payload)
        mapped = self.map_board_games(board, events)
        response_timestamp = str(meta.get("timestamp") or "")

        frames: list[pd.DataFrame] = []
        fallback_games: list[str] = []
        mapped_ids: set[str] = set()
        for item in mapped:
            game_id = str(item["board_row"].get("Game ID") or "")
            if game_id:
                mapped_ids.add(game_id)
            parsed, used_fallback = self.parse_event(
                item["event"],
                item["board_row"],
                swapped=bool(item["swapped"]),
                snapshot_role=role,
                response_timestamp=response_timestamp,
            )
            if not parsed.empty:
                frames.append(parsed)
            if used_fallback:
                fallback_games.append(game_id)

        snapshots = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        board_ids = {str(x) for x in board.get("Game ID", pd.Series(dtype=str)).astype(str) if str(x)}
        freshness = meta.get("freshness") if isinstance(meta.get("freshness"), dict) else {}
        health = {
            "provider": "Owls Insight",
            "mode": "current",
            "board_games": len(board),
            "provider_events": len(events),
            "mapped_games": len(mapped),
            "snapshot_games": len(set(snapshots.get("Game ID", []))) if not snapshots.empty else 0,
            "snapshot_rows": len(snapshots),
            "snapshot_role": role,
            "reference_fallback_games": [x for x in fallback_games if x],
            "unmatched_game_ids": sorted(board_ids - mapped_ids),
            "requested_books": list(meta.get("requestedBooks") or []),
            "available_books": list(meta.get("availableBooks") or []),
            "books_returned": list(meta.get("booksReturned") or []),
            "freshness": freshness,
            "rate": dict(self.last_rate_headers),
        }
        # Odds are downstream market data only. No game-context frame is emitted.
        return snapshots, pd.DataFrame(), health
