from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any

import numpy as np
import pandas as pd
import requests

from .market import MarketDataError, normalize_team_name


DEFAULT_REFERENCE_PRIORITY = (
    "draftkings",
    "fanduel",
    "betmgm",
    "caesars",
    "williamhill_us",
    "fanatics",
    "betrivers",
    "espnbet",
)

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
class OddsApiConfig:
    api_key: str
    base_url: str = "https://api.the-odds-api.com"
    sport_key: str = "basketball_ncaab"
    regions: str = "us"
    bookmakers: str = ""
    markets: str = "h2h,spreads,totals"
    reference_bookmaker: str = "draftkings"
    timeout_seconds: int = 20


class OddsApiMarketProvider:
    """The Odds API adapter for the downstream CBB Market Terminal.

    The provider intentionally handles sportsbook prices and line movement only.
    The Odds API does not document ticket-share or money-share betting splits, so
    those fields remain blank unless a separate authorized split source is
    imported. The reference sportsbook supplies the actual line used by the
    display/ATS pipeline; cross-book data is used only for disagreement metrics.
    """

    def __init__(self, config: OddsApiConfig):
        if not str(config.api_key or "").strip():
            raise MarketDataError("The Odds API key is not configured.")
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"accept": "application/json", "user-agent": "cbb-market-terminal/1.4.2"})
        self.last_usage: dict[str, Any] = {}

    @staticmethod
    def _canonical_team(value: Any) -> str:
        text = normalize_team_name(value)
        if text.startswith("st "):
            text = "saint " + text[3:]
        text = TEAM_ALIASES.get(text, text)
        return text

    @staticmethod
    def _team_score(left: Any, right: Any) -> float:
        a, b = OddsApiMarketProvider._canonical_team(left), OddsApiMarketProvider._canonical_team(right)
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        if a in b or b in a:
            return 0.93
        ta, tb = set(a.split()), set(b.split())
        overlap = len(ta & tb) / max(len(ta | tb), 1)
        ratio = SequenceMatcher(None, a, b).ratio()
        return max(ratio, overlap)

    def _base_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "apiKey": self.config.api_key,
            "markets": self.config.markets,
            "oddsFormat": "american",
            "dateFormat": "iso",
        }
        books = str(self.config.bookmakers or "").strip()
        if books:
            params["bookmakers"] = books
        else:
            params["regions"] = str(self.config.regions or "us")
        return params

    def _request(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            response = self.session.get(url, params=params, timeout=self.config.timeout_seconds)
            self.last_usage = {
                "requests_remaining": response.headers.get("x-requests-remaining", ""),
                "requests_used": response.headers.get("x-requests-used", ""),
                "requests_last": response.headers.get("x-requests-last", ""),
            }
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", "unknown")
            raise MarketDataError(f"The Odds API request failed (HTTP {status}).") from exc
        except requests.RequestException as exc:
            raise MarketDataError(f"The Odds API request failed ({type(exc).__name__}).") from exc
        except ValueError as exc:
            raise MarketDataError("The Odds API returned a non-JSON response.") from exc

    @staticmethod
    def _slate_window(slate_date: str) -> tuple[str, str]:
        d = pd.to_datetime(slate_date).date()
        # A deliberately broad UTC window covers the full US college-basketball
        # calendar day from Eastern through Hawaii without relying on venue TZ.
        start = datetime.combine(d, time(4, 0), tzinfo=timezone.utc)
        end = datetime.combine(d + timedelta(days=1), time(11, 0), tzinfo=timezone.utc)
        return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")

    def current_odds(self, slate_date: str) -> list[dict[str, Any]]:
        start, end = self._slate_window(slate_date)
        params = self._base_params()
        params.update({"commenceTimeFrom": start, "commenceTimeTo": end, "includeRotationNumbers": "true"})
        payload = self._request(f"v4/sports/{self.config.sport_key}/odds", params)
        return payload if isinstance(payload, list) else []

    def historical_odds(self, snapshot_time_utc: str) -> tuple[list[dict[str, Any]], str]:
        stamp = pd.to_datetime(snapshot_time_utc, utc=True, errors="coerce")
        if pd.isna(stamp):
            raise MarketDataError("Historical snapshot time must be a valid UTC/ISO timestamp.")
        params = self._base_params()
        params["date"] = stamp.isoformat().replace("+00:00", "Z")
        payload = self._request(f"v4/historical/sports/{self.config.sport_key}/odds", params)
        if not isinstance(payload, dict):
            return [], stamp.isoformat()
        data = payload.get("data")
        actual = str(payload.get("timestamp") or stamp.isoformat())
        return (data if isinstance(data, list) else []), actual

    @staticmethod
    def _market(book: dict[str, Any], key: str) -> dict[str, Any] | None:
        for market in book.get("markets") or []:
            if isinstance(market, dict) and str(market.get("key") or "").lower() == key:
                return market
        return None

    @staticmethod
    def _outcome(market: dict[str, Any] | None, name: str) -> dict[str, Any] | None:
        if not market:
            return None
        target = OddsApiMarketProvider._canonical_team(name)
        for outcome in market.get("outcomes") or []:
            if not isinstance(outcome, dict):
                continue
            raw = str(outcome.get("name") or "")
            if raw.lower() in {"over", "under"}:
                if raw.lower() == str(name).lower():
                    return outcome
            elif OddsApiMarketProvider._canonical_team(raw) == target:
                return outcome
        return None

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

    @staticmethod
    def _last_update(book: dict[str, Any] | None, market: dict[str, Any] | None, fallback: str = "") -> str:
        value = (market or {}).get("last_update") or (book or {}).get("last_update") or fallback
        stamp = pd.to_datetime(value, utc=True, errors="coerce")
        if pd.isna(stamp):
            stamp = pd.Timestamp.now(tz="UTC")
        return stamp.isoformat()

    @staticmethod
    def _book_spread_summary(event: dict[str, Any], board_home_provider_name: str) -> dict[str, Any]:
        values: list[float] = []
        for book in event.get("bookmakers") or []:
            if not isinstance(book, dict):
                continue
            market = OddsApiMarketProvider._market(book, "spreads")
            outcome = OddsApiMarketProvider._outcome(market, board_home_provider_name)
            point = pd.to_numeric((outcome or {}).get("point"), errors="coerce")
            if pd.notna(point):
                values.append(float(point))
        if not values:
            return {"count": np.nan, "min": np.nan, "max": np.nan, "range": np.nan, "agreement": ""}
        lo, hi = min(values), max(values)
        spread_range = hi - lo
        agreement = "tight" if spread_range <= 0.5 else ("mixed" if spread_range <= 1.5 else "wide")
        return {"count": len(values), "min": lo, "max": hi, "range": spread_range, "agreement": agreement}

    def map_board_games(self, board: pd.DataFrame, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        available = [e for e in events if isinstance(e, dict)]
        used: set[str] = set()
        mapped: list[dict[str, Any]] = []
        for _, row in board.iterrows():
            bh, ba = str(row.get("Home Team") or ""), str(row.get("Away Team") or "")
            best: tuple[float, dict[str, Any], bool] | None = None
            for event in available:
                event_id = str(event.get("id") or "")
                if event_id and event_id in used:
                    continue
                eh, ea = str(event.get("home_team") or ""), str(event.get("away_team") or "")
                direct = (self._team_score(bh, eh) + self._team_score(ba, ea)) / 2.0
                swapped = (self._team_score(bh, ea) + self._team_score(ba, eh)) / 2.0
                score, is_swapped = (swapped, True) if swapped > direct else (direct, False)
                if best is None or score > best[0]:
                    best = (score, event, is_swapped)
            if best and best[0] >= 0.78:
                event_id = str(best[1].get("id") or "")
                if event_id:
                    used.add(event_id)
                mapped.append({"board_row": row, "event": best[1], "swapped": best[2], "match_score": best[0]})
        return mapped

    def parse_event(
        self,
        event: dict[str, Any],
        row: pd.Series,
        swapped: bool = False,
        snapshot_time_override: str = "",
        snapshot_role: str = "observed",
    ) -> tuple[pd.DataFrame, bool]:
        ref, used_fallback = self._reference_book(event)
        if ref is None:
            return pd.DataFrame(), used_fallback

        provider_home = str(event.get("home_team") or "")
        provider_away = str(event.get("away_team") or "")
        board_home_provider_name = provider_away if swapped else provider_home
        board_away_provider_name = provider_home if swapped else provider_away
        ref_title = str(ref.get("title") or ref.get("key") or "sportsbook")
        provider_game_id = str(event.get("id") or "")
        start = pd.to_datetime(event.get("commence_time") or row.get("Start Time UTC"), utc=True, errors="coerce")
        spread_summary = self._book_spread_summary(event, board_home_provider_name)
        scope = f"{ref_title} reference · {int(spread_summary['count']) if np.isfinite(spread_summary['count']) else 0} books compared"
        source = f"The Odds API · {ref_title}"
        rows: list[dict[str, Any]] = []

        def common(market_key: str, stamp: str) -> dict[str, Any]:
            st = pd.to_datetime(stamp, utc=True, errors="coerce")
            mins = (start - st).total_seconds() / 60.0 if pd.notna(start) and pd.notna(st) else np.nan
            return {
                "Slate Date": str(row.get("Target Date") or pd.to_datetime(start).date() if pd.notna(start) else ""),
                "Game ID": str(row.get("Game ID")),
                "Provider": "the_odds_api",
                "Provider Game ID": provider_game_id,
                "Snapshot Time UTC": st.isoformat() if pd.notna(st) else pd.Timestamp.now(tz="UTC").isoformat(),
                "Snapshot Role": snapshot_role,
                "Minutes To Tip": mins,
                "Market Type": market_key,
                "Source Label": source,
                "Sportsbook Scope": scope,
                "Activity Level": "",
                "Ticket Count": np.nan,
                "Provider Signals": "",
                "Book Count": spread_summary["count"] if market_key == "spread" else np.nan,
                "Home Spread Min": spread_summary["min"] if market_key == "spread" else np.nan,
                "Home Spread Max": spread_summary["max"] if market_key == "spread" else np.nan,
                "Book Spread Range": spread_summary["range"] if market_key == "spread" else np.nan,
                "Book Agreement": spread_summary["agreement"] if market_key == "spread" else "",
            }

        spread = self._market(ref, "spreads")
        if spread:
            h = self._outcome(spread, board_home_provider_name)
            a = self._outcome(spread, board_away_provider_name)
            hp = pd.to_numeric((h or {}).get("point"), errors="coerce")
            ap = pd.to_numeric((a or {}).get("point"), errors="coerce")
            if pd.notna(hp) or pd.notna(ap):
                stamp = snapshot_time_override or self._last_update(ref, spread)
                item = common("spread", stamp)
                item.update({
                    "Home Line": hp,
                    "Away Line": ap,
                    "Opening Home Line": hp if snapshot_role == "open" else np.nan,
                    "Opening Away Line": ap if snapshot_role == "open" else np.nan,
                    "Home Price": pd.to_numeric((h or {}).get("price"), errors="coerce"),
                    "Away Price": pd.to_numeric((a or {}).get("price"), errors="coerce"),
                })
                rows.append(item)

        h2h = self._market(ref, "h2h")
        if h2h:
            h = self._outcome(h2h, board_home_provider_name)
            a = self._outcome(h2h, board_away_provider_name)
            if h or a:
                stamp = snapshot_time_override or self._last_update(ref, h2h)
                item = common("moneyline", stamp)
                item.update({
                    "Home Price": pd.to_numeric((h or {}).get("price"), errors="coerce"),
                    "Away Price": pd.to_numeric((a or {}).get("price"), errors="coerce"),
                })
                rows.append(item)

        total = self._market(ref, "totals")
        if total:
            over = self._outcome(total, "Over")
            under = self._outcome(total, "Under")
            point = pd.to_numeric((over or under or {}).get("point"), errors="coerce")
            if pd.notna(point):
                stamp = snapshot_time_override or self._last_update(ref, total)
                item = common("total", stamp)
                item.update({
                    "Total Line": point,
                    "Opening Total": point if snapshot_role == "open" else np.nan,
                    "Over Price": pd.to_numeric((over or {}).get("price"), errors="coerce"),
                    "Under Price": pd.to_numeric((under or {}).get("price"), errors="coerce"),
                })
                rows.append(item)

        return pd.DataFrame(rows), used_fallback

    def refresh(
        self,
        board: pd.DataFrame,
        historical_at: str = "",
        snapshot_role: str = "observed",
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        if board is None or board.empty:
            raise MarketDataError("Publish/select a board before refreshing market data.")
        slate_date = str(board.iloc[0].get("Target Date"))
        if historical_at:
            events, actual_snapshot = self.historical_odds(historical_at)
            snapshot_override = actual_snapshot
            mode = "historical"
        else:
            events = self.current_odds(slate_date)
            snapshot_override = ""
            mode = "current"

        mapped = self.map_board_games(board, events)
        frames: list[pd.DataFrame] = []
        fallback_games: list[str] = []
        for item in mapped:
            parsed, used_fallback = self.parse_event(
                item["event"],
                item["board_row"],
                swapped=bool(item["swapped"]),
                snapshot_time_override=snapshot_override,
                snapshot_role=snapshot_role,
            )
            if not parsed.empty:
                frames.append(parsed)
            if used_fallback:
                fallback_games.append(str(item["board_row"].get("Game ID")))

        snapshots = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        health = {
            "provider": "The Odds API",
            "mode": mode,
            "board_games": len(board),
            "provider_events": len(events),
            "mapped_games": len(mapped),
            "snapshot_games": len(set(snapshots.get("Game ID", []))) if not snapshots.empty else 0,
            "snapshot_rows": len(snapshots),
            "reference_fallback_games": fallback_games,
            **self.last_usage,
        }
        # The Odds API does not supply AP rankings/conferences. Returning no
        # context avoids overwriting manually curated/ranking-derived context.
        return snapshots, pd.DataFrame(), health
