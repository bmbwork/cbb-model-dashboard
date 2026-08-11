from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import requests

from .market import MarketDataError, normalize_team_name


@dataclass(frozen=True)
class SportsDataIOConfig:
    api_key: str
    splits_mode: str = "trial"  # trial = preview only; production = publishable
    timeout_seconds: int = 20

    @property
    def production_mode(self) -> bool:
        return str(self.splits_mode or "trial").strip().lower() == "production"


class SportsDataIOSplitsProvider:
    """SportsDataIO NCAA men's basketball betting-splits adapter.

    This connector uses only the documented SportsDataIO CBB endpoints:
    - GameOddsByDate/{date} to resolve SportsDataIO GameIDs
    - BettingSplitsByGameId/{gameId} for ticket/money split history
    - BettingMetadata to map enum IDs when the payload does not include labels

    The API key is sent in the Ocp-Apim-Subscription-Key request header so it is
    never placed in a URL or exposed to the browser.
    """

    BASE_URL = "https://api.sportsdata.io/v3/cbb"

    def __init__(self, config: SportsDataIOConfig):
        if not str(config.api_key or "").strip():
            raise MarketDataError("SportsDataIO API key is not configured.")
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "application/json",
            "user-agent": "cbb-market-terminal/1.4.3",
            "Ocp-Apim-Subscription-Key": str(config.api_key).strip(),
        })
        self._metadata_cache: dict[str, dict[str, str]] | None = None

    @staticmethod
    def _lower(d: dict[str, Any]) -> dict[str, Any]:
        return {str(k).lower().replace("-", "_").replace(" ", "_"): v for k, v in d.items()}

    @classmethod
    def _first(cls, d: dict[str, Any], names: list[str], default: Any = None) -> Any:
        if not isinstance(d, dict):
            return default
        low = cls._lower(d)
        for name in names:
            key = name.lower().replace("-", "_").replace(" ", "_")
            if key in low and low[key] not in (None, ""):
                return low[key]
        return default

    @staticmethod
    def _walk(obj: Any):
        if isinstance(obj, dict):
            yield obj
            for value in obj.values():
                yield from SportsDataIOSplitsProvider._walk(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from SportsDataIOSplitsProvider._walk(value)

    def _get(self, path: str) -> Any:
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        try:
            response = self.session.get(url, timeout=self.config.timeout_seconds)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise MarketDataError(f"SportsDataIO request failed safely ({type(exc).__name__}).") from exc
        except ValueError as exc:
            raise MarketDataError("SportsDataIO returned a non-JSON response.") from exc

    def game_odds_by_date(self, slate_date: str) -> list[dict[str, Any]]:
        day = pd.to_datetime(slate_date, errors="coerce")
        if pd.isna(day):
            raise MarketDataError("SportsDataIO refresh needs a valid slate date.")
        payload = self._get(f"odds/json/GameOddsByDate/{day:%Y-%m-%d}")
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if isinstance(payload, dict):
            for key in ["data", "results", "games", "Games", "GameInfo"]:
                value = payload.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
        return []

    def betting_splits_by_game(self, game_id: str | int) -> Any:
        return self._get(f"odds/json/BettingSplitsByGameId/{game_id}")

    def betting_metadata(self) -> Any:
        return self._get("odds/json/BettingMetadata")

    @classmethod
    def _provider_game_id(cls, event: dict[str, Any]) -> str:
        value = cls._first(event, ["GameID", "GameId", "game_id", "ID", "Id"], "")
        return str(value or "")

    @classmethod
    def _team_name(cls, event: dict[str, Any], side: str) -> str:
        side_cap = side.capitalize()
        direct = cls._first(event, [
            f"{side_cap}TeamName", f"{side_cap}Team", f"{side_cap}Name",
            f"{side_cap}TeamKey", f"{side_cap}TeamShortName",
        ], "")
        if isinstance(direct, dict):
            direct = cls._first(direct, ["Name", "FullName", "School", "Key", "ShortName"], "")
        return str(direct or "")

    @classmethod
    def _start_time(cls, event: dict[str, Any]) -> pd.Timestamp | None:
        raw = cls._first(event, ["DateTime", "DateTimeUTC", "StartTime", "StartTimeUTC", "Day"], None)
        ts = pd.to_datetime(raw, utc=True, errors="coerce")
        return ts if pd.notna(ts) else None

    @staticmethod
    def _team_score(board_name: str, provider_name: str) -> float:
        b, p = normalize_team_name(board_name), normalize_team_name(provider_name)
        if not b or not p:
            return 0.0
        if b == p:
            return 1.0
        if b in p or p in b:
            return 0.88
        bt, pt = set(b.split()), set(p.split())
        union = len(bt | pt)
        if not union:
            return 0.0
        return len(bt & pt) / union

    def map_board_games(self, board: pd.DataFrame, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        used: set[str] = set()
        mapped: list[dict[str, Any]] = []
        for _, row in board.iterrows():
            bh, ba = str(row.get("Home Team") or ""), str(row.get("Away Team") or "")
            bstart = pd.to_datetime(row.get("Start Time UTC"), utc=True, errors="coerce")
            best: tuple[float, dict[str, Any], bool] | None = None
            for event in events:
                gid = self._provider_game_id(event)
                if gid and gid in used:
                    continue
                eh, ea = self._team_name(event, "home"), self._team_name(event, "away")
                direct = (self._team_score(bh, eh) + self._team_score(ba, ea)) / 2.0
                swapped = (self._team_score(bh, ea) + self._team_score(ba, eh)) / 2.0
                score, is_swapped = (swapped, True) if swapped > direct else (direct, False)
                estart = self._start_time(event)
                if pd.notna(bstart) and estart is not None:
                    mins = abs((estart - bstart).total_seconds()) / 60.0
                    if mins <= 20:
                        score += 0.12
                    elif mins <= 120:
                        score += 0.04
                if best is None or score > best[0]:
                    best = (score, event, is_swapped)
            if best and best[0] >= 0.72:
                gid = self._provider_game_id(best[1])
                if gid:
                    used.add(gid)
                mapped.append({"board_row": row, "event": best[1], "provider_game_id": gid, "swapped": best[2], "match_score": best[0]})
        return mapped

    @classmethod
    def _metadata_maps(cls, payload: Any) -> dict[str, dict[str, str]]:
        maps: dict[str, dict[str, str]] = {"bet": {}, "period": {}, "outcome": {}, "market": {}}

        def category(path: str) -> str | None:
            text = path.lower()
            if "outcome" in text:
                return "outcome"
            if "period" in text:
                return "period"
            if "bettype" in text or "bet_type" in text or "bettingbet" in text:
                return "bet"
            if "markettype" in text or "market_type" in text:
                return "market"
            return None

        def visit(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                cat = category(path)
                if cat:
                    ident = cls._first(obj, ["ID", "Id", "Key", "BettingEntityMetadataID", "BettingBetTypeID", "BetTypeID", "BettingPeriodTypeID", "PeriodTypeID", "BettingOutcomeTypeID", "OutcomeTypeID", "BettingMarketTypeID", "MarketTypeID"], None)
                    name = cls._first(obj, ["Name", "Description", "Value", "Label", "BettingBetType", "BetType", "BettingPeriodType", "PeriodType", "BettingOutcomeType", "OutcomeType", "BettingMarketType", "MarketType"], None)
                    if ident not in (None, "") and name not in (None, ""):
                        maps[cat][str(ident)] = str(name)
                for key, value in obj.items():
                    visit(value, f"{path}/{key}")
            elif isinstance(obj, list):
                for value in obj:
                    visit(value, path)

        visit(payload)
        return maps

    def _ensure_metadata(self) -> dict[str, dict[str, str]]:
        if self._metadata_cache is None:
            try:
                self._metadata_cache = self._metadata_maps(self.betting_metadata())
            except MarketDataError:
                # Text labels are normally included in split payloads. Metadata is
                # a safety net, so a metadata failure should not kill the refresh.
                self._metadata_cache = {"bet": {}, "period": {}, "outcome": {}, "market": {}}
        return self._metadata_cache

    @classmethod
    def _label(cls, obj: dict[str, Any], direct_names: list[str], id_names: list[str], mapping: dict[str, str]) -> str:
        direct = cls._first(obj, direct_names, "")
        if direct not in (None, ""):
            return str(direct)
        ident = cls._first(obj, id_names, "")
        return str(mapping.get(str(ident), ident if ident not in (None, "") else ""))

    @classmethod
    def _market_nodes(cls, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            direct = cls._first(payload, ["BettingMarketSplits", "MarketSplits", "Markets"], None)
            if isinstance(direct, list):
                return [x for x in direct if isinstance(x, dict)]
        nodes: list[dict[str, Any]] = []
        seen: set[int] = set()
        for node in cls._walk(payload):
            splits = cls._first(node, ["BettingSplits", "Splits"], None)
            if isinstance(splits, list) and id(node) not in seen:
                seen.add(id(node))
                nodes.append(node)
        return nodes

    @classmethod
    def _market_kind(cls, market: dict[str, Any], maps: dict[str, dict[str, str]]) -> str:
        label = cls._label(
            market,
            ["BettingBetType", "BetType", "BettingBetTypeName", "BetTypeName", "MarketName", "Name"],
            ["BettingBetTypeID", "BetTypeID"],
            maps.get("bet", {}),
        ).lower().replace("_", " ")
        market_label = cls._label(
            market,
            ["BettingMarketType", "MarketType", "BettingMarketTypeName", "MarketTypeName"],
            ["BettingMarketTypeID", "MarketTypeID"],
            maps.get("market", {}),
        ).lower().replace("_", " ")
        text = f"{label} {market_label}"
        if "moneyline" in text or "money line" in text:
            return "moneyline"
        if "spread" in text or "point spread" in text or "handicap" in text:
            return "spread"
        if "total" in text or "over under" in text or "over/under" in text:
            return "total"
        return ""

    @classmethod
    def _full_game(cls, market: dict[str, Any], maps: dict[str, dict[str, str]]) -> bool:
        label = cls._label(
            market,
            ["BettingPeriodType", "PeriodType", "BettingPeriodTypeName", "PeriodTypeName"],
            ["BettingPeriodTypeID", "PeriodTypeID"],
            maps.get("period", {}),
        ).lower().replace("_", " ")
        if not label:
            return True
        if "full" in label or "game" == label.strip() or "game lines" in label:
            return True
        partial_words = ["half", "quarter", "period", "1st", "2nd", "first", "second"]
        return not any(word in label for word in partial_words)

    @classmethod
    def _outcome_side(cls, split: dict[str, Any], maps: dict[str, dict[str, str]]) -> str:
        label = cls._label(
            split,
            ["BettingOutcomeType", "OutcomeType", "BettingOutcomeTypeName", "OutcomeTypeName", "Outcome", "Name", "Label"],
            ["BettingOutcomeTypeID", "OutcomeTypeID"],
            maps.get("outcome", {}),
        ).lower().replace("_", " ")
        if "home" in label:
            return "home"
        if "away" in label:
            return "away"
        if "over" in label:
            return "over"
        if "under" in label:
            return "under"
        return ""

    @classmethod
    def _pct(cls, value: Any) -> float:
        num = pd.to_numeric(value, errors="coerce")
        if pd.isna(num):
            return float("nan")
        x = float(num)
        if abs(x) <= 1.000001:
            x *= 100.0
        return float(np.clip(x, 0.0, 100.0))

    def parse_game_splits(self, payload: Any, board_row: pd.Series, provider_game_id: str) -> pd.DataFrame:
        maps = self._ensure_metadata()
        groups: dict[tuple[str, str], dict[str, Any]] = {}
        start = pd.to_datetime(board_row.get("Start Time UTC"), utc=True, errors="coerce")
        mode = "production" if self.config.production_mode else "trial"

        for market in self._market_nodes(payload):
            kind = self._market_kind(market, maps)
            if kind not in {"spread", "moneyline", "total"} or not self._full_game(market, maps):
                continue
            splits = self._first(market, ["BettingSplits", "Splits"], [])
            if not isinstance(splits, list):
                continue
            market_id = str(self._first(market, ["BettingMarketID", "BettingMarketId", "MarketID", "MarketId"], "") or "")
            for split in splits:
                if not isinstance(split, dict):
                    continue
                side = self._outcome_side(split, maps)
                if not side:
                    continue
                raw_stamp = self._first(split, ["LastSeen", "Updated", "UpdatedAt", "Created", "CreatedAt", "Timestamp"], None)
                stamp = pd.to_datetime(raw_stamp, utc=True, errors="coerce")
                if pd.isna(stamp):
                    stamp = pd.Timestamp.now(tz="UTC")
                # Five-second precision is enough to pair home/away rows while
                # retaining movement history without manufacturing timestamps.
                stamp = stamp.floor("s")
                key = (kind, stamp.isoformat())
                row = groups.setdefault(key, {
                    "Slate Date": str(board_row.get("Target Date") or ""),
                    "Game ID": str(board_row.get("Game ID") or ""),
                    "Provider": "sportsdataio",
                    "Provider Game ID": str(provider_game_id),
                    "Snapshot Time UTC": stamp.isoformat(),
                    "Snapshot Role": "observed",
                    "Market Type": kind,
                    "Source Label": "SportsDataIO betting splits",
                    "Sportsbook Scope": "SportsDataIO public betting splits",
                    "Activity Level": "",
                    "Ticket Count": np.nan,
                    "Provider Signals": f"sportsdataio_splits;mode={mode};market_id={market_id}",
                })
                pct_bets = self._pct(self._first(split, ["BetPercentage", "BetPct", "BetPercent", "TicketPercentage", "TicketPct"], np.nan))
                pct_money = self._pct(self._first(split, ["MoneyPercentage", "MoneyPct", "MoneyPercent", "HandlePercentage", "HandlePct"], np.nan))
                if kind in {"spread", "moneyline"}:
                    if side == "home":
                        row["Home Ticket %"] = pct_bets
                        row["Home Money %"] = pct_money
                    elif side == "away":
                        row["Away Ticket %"] = pct_bets
                        row["Away Money %"] = pct_money
                elif kind == "total":
                    if side == "over":
                        row["Over Ticket %"] = pct_bets
                        row["Over Money %"] = pct_money
                    elif side == "under":
                        row["Under Ticket %"] = pct_bets
                        row["Under Money %"] = pct_money

        rows = list(groups.values())
        for row in rows:
            stamp = pd.to_datetime(row.get("Snapshot Time UTC"), utc=True, errors="coerce")
            row["Minutes To Tip"] = (start - stamp).total_seconds() / 60.0 if pd.notna(start) and pd.notna(stamp) else np.nan
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        # Keep only rows that actually carry at least one percentage.
        pct_cols = ["Home Ticket %", "Away Ticket %", "Home Money %", "Away Money %", "Over Ticket %", "Under Ticket %", "Over Money %", "Under Money %"]
        for col in pct_cols:
            if col not in frame.columns:
                frame[col] = np.nan
        mask = frame[pct_cols].apply(pd.to_numeric, errors="coerce").notna().any(axis=1)
        return frame.loc[mask].sort_values(["Market Type", "Snapshot Time UTC"]).reset_index(drop=True)

    def refresh(self, board: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
        if board is None or board.empty:
            raise MarketDataError("Publish/select a board before refreshing SportsDataIO betting splits.")
        slate_date = str(board.iloc[0].get("Target Date") or "")
        events = self.game_odds_by_date(slate_date)
        mapped = self.map_board_games(board, events)
        frames: list[pd.DataFrame] = []
        empty_games: list[str] = []
        errors: list[str] = []
        for item in mapped:
            gid = item["provider_game_id"]
            try:
                payload = self.betting_splits_by_game(gid)
                parsed = self.parse_game_splits(payload, item["board_row"], gid)
                if parsed.empty:
                    empty_games.append(str(item["board_row"].get("Game ID") or ""))
                else:
                    frames.append(parsed)
            except MarketDataError:
                errors.append(str(item["board_row"].get("Game ID") or ""))

        snapshots = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        health = {
            "provider": "SportsDataIO",
            "mode": "production" if self.config.production_mode else "trial",
            "publishable": self.config.production_mode,
            "board_games": len(board),
            "provider_events": len(events),
            "mapped_games": len(mapped),
            "split_games": len(set(snapshots.get("Game ID", []))) if not snapshots.empty else 0,
            "snapshot_rows": len(snapshots),
            "empty_games": empty_games,
            "errors": errors,
        }
        return snapshots, health
