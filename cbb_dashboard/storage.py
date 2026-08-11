from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

from .data import BoardReport, dataframe_records
from .performance import slate_grade_metrics


class StorageConfigurationError(RuntimeError):
    pass


class StorageOperationError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoreConfig:
    url: str
    publishable_key: str
    secret_key: str | None = None


def sha256_frame(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SupabaseSlateStore:
    TABLE = "cbb_slates"
    MARKET_TABLE = "cbb_market_snapshots"
    CONTEXT_TABLE = "cbb_game_context"

    def __init__(self, config: StoreConfig):
        self.config = config
        try:
            from supabase import create_client
        except Exception as exc:
            raise StorageConfigurationError("The `supabase` Python package is not installed.") from exc
        self._create_client = create_client
        self._public = create_client(config.url, config.publishable_key)
        self._admin = None

    def _admin_client(self):
        if not self.config.secret_key:
            raise StorageConfigurationError("Supabase secret/server key is not configured.")
        if self._admin is None:
            self._admin = self._create_client(self.config.url, self.config.secret_key)
        return self._admin

    @staticmethod
    def _data(response: Any) -> Any:
        data = getattr(response, "data", None)
        return data if data is not None else []

    def check_access(self, admin: bool = False) -> None:
        client = self._admin_client() if admin else self._public
        try:
            client.table(self.TABLE).select("slate_date").limit(1).execute()
        except Exception as exc:
            raise StorageOperationError(f"Supabase table `{self.TABLE}` is not ready or not accessible: {type(exc).__name__}") from exc

    def check_market_access(self, admin: bool = False) -> None:
        client = self._admin_client() if admin else self._public
        for table in [self.MARKET_TABLE, self.CONTEXT_TABLE]:
            try:
                client.table(table).select("slate_date").limit(1).execute()
            except Exception as exc:
                raise StorageOperationError(f"Supabase market table `{table}` is not ready or not accessible: {type(exc).__name__}") from exc

    def list_market_snapshots(self, slate_date: str | None = None, limit: int = 5000) -> list[dict[str, Any]]:
        try:
            query = self._public.table(self.MARKET_TABLE).select("*")
            if slate_date:
                query = query.eq("slate_date", slate_date)
            resp = query.order("snapshot_time_utc", desc=False).limit(int(limit)).execute()
            return [dict(x) for x in self._data(resp)]
        except Exception as exc:
            raise StorageOperationError(f"Could not read market snapshots: {type(exc).__name__}") from exc

    def list_game_context(self, slate_date: str | None = None, limit: int = 5000) -> list[dict[str, Any]]:
        try:
            query = self._public.table(self.CONTEXT_TABLE).select("*")
            if slate_date:
                query = query.eq("slate_date", slate_date)
            resp = query.order("slate_date", desc=True).limit(int(limit)).execute()
            return [dict(x) for x in self._data(resp)]
        except Exception as exc:
            raise StorageOperationError(f"Could not read game context: {type(exc).__name__}") from exc

    def publish_market_records(self, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0
        client = self._admin_client()
        now = datetime.now(timezone.utc).isoformat()
        payload = []
        for record in records:
            row = dict(record)
            row.setdefault("created_at", now)
            row["updated_at"] = now
            payload.append(row)
        try:
            resp = client.table(self.MARKET_TABLE).upsert(payload, on_conflict="raw_snapshot_hash").execute()
            data = self._data(resp)
            return len(data) if data else len(payload)
        except Exception as exc:
            raise StorageOperationError(f"Market snapshot publish failed: {type(exc).__name__}") from exc

    def publish_context_records(self, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0
        client = self._admin_client()
        now = datetime.now(timezone.utc).isoformat()
        payload = []
        for record in records:
            row = dict(record)
            row["updated_at"] = now
            payload.append(row)
        try:
            resp = client.table(self.CONTEXT_TABLE).upsert(payload, on_conflict="slate_date,game_id").execute()
            data = self._data(resp)
            return len(data) if data else len(payload)
        except Exception as exc:
            raise StorageOperationError(f"Game-context publish failed: {type(exc).__name__}") from exc

    @staticmethod
    def _publish_sort_key(record: dict[str, Any]) -> tuple[int, str, int]:
        """Sort published boards by upload/publish time, not game date.

        `published_at` is refreshed whenever a decision board is published in
        Admin Studio. Grading updates do not change it, so grading an older
        slate cannot unexpectedly become the default public board.
        """
        stamp = pd.to_datetime(record.get("published_at"), utc=True, errors="coerce")
        stamp_ns = -1 if pd.isna(stamp) else int(stamp.value)
        slate_date = str(record.get("slate_date") or "")
        try:
            revision = int(record.get("revision") or 0)
        except (TypeError, ValueError):
            revision = 0
        return stamp_ns, slate_date, revision

    @classmethod
    def sort_records_by_publish_recency(cls, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            (dict(record) for record in records),
            key=cls._publish_sort_key,
            reverse=True,
        )

    def latest(self) -> dict[str, Any] | None:
        records = self.list_records(limit=1)
        return records[0] if records else None

    def list_records(self, limit: int = 80) -> list[dict[str, Any]]:
        try:
            resp = (
                self._public.table(self.TABLE)
                .select("*")
                .order("published_at", desc=True)
                .order("slate_date", desc=True)
                .limit(int(limit))
                .execute()
            )
            return self.sort_records_by_publish_recency([dict(x) for x in self._data(resp)])
        except Exception as exc:
            raise StorageOperationError(f"Could not read published CBB history: {type(exc).__name__}") from exc

    def get(self, slate_date: str, admin: bool = False) -> dict[str, Any] | None:
        client = self._admin_client() if admin else self._public
        try:
            resp = client.table(self.TABLE).select("*").eq("slate_date", slate_date).limit(1).execute()
            data = self._data(resp)
            return dict(data[0]) if data else None
        except Exception as exc:
            raise StorageOperationError(f"Could not read slate {slate_date}: {type(exc).__name__}") from exc

    @staticmethod
    def board_frame(record: dict[str, Any]) -> pd.DataFrame:
        return pd.DataFrame(record.get("board_json") or [])

    @staticmethod
    def grading_frame(record: dict[str, Any]) -> pd.DataFrame:
        return pd.DataFrame(record.get("grading_json") or [])

    def publish_board(self, frame: pd.DataFrame, report: BoardReport, filename: str, actor: str) -> dict[str, Any]:
        client = self._admin_client()
        digest = sha256_frame(frame)
        existing = self.get(report.slate_date, admin=True)
        now = datetime.now(timezone.utc).isoformat()
        revision = 1
        preserve_grading = False
        if existing:
            same = str(existing.get("board_sha256") or "") == digest
            revision = int(existing.get("revision") or 1) if same else int(existing.get("revision") or 1) + 1
            preserve_grading = same
        payload = {
            "slate_date": report.slate_date,
            "model_version": report.model_version,
            "revision": revision,
            "board_filename": filename,
            "board_sha256": digest,
            "board_rows": int(len(frame)),
            "board_json": dataframe_records(frame),
            "published_at": now,
            "published_by": actor,
            "updated_at": now,
            "schema_version": "cbb_web_v1_1",
        }
        if existing and preserve_grading:
            for key in ["grading_filename", "grading_sha256", "grading_json", "metrics_json", "graded_at", "graded_by"]:
                payload[key] = existing.get(key)
        else:
            payload.update({
                "grading_filename": None, "grading_sha256": None, "grading_json": None,
                "metrics_json": None, "graded_at": None, "graded_by": None,
            })
        try:
            resp = client.table(self.TABLE).upsert(payload, on_conflict="slate_date").execute()
            data = self._data(resp)
            return dict(data[0]) if data else payload
        except Exception as exc:
            raise StorageOperationError(f"Board publish failed: {type(exc).__name__}") from exc

    def publish_grading(self, frame: pd.DataFrame, report: BoardReport, filename: str, actor: str) -> dict[str, Any]:
        client = self._admin_client()
        existing = self.get(report.slate_date, admin=True)
        if not existing:
            raise StorageOperationError(f"Publish the {report.slate_date} decision board before publishing grading.")
        board_ids = set(pd.DataFrame(existing.get("board_json") or []).get("Game ID", pd.Series(dtype=object)).astype(str))
        grade_ids = set(frame.get("Game ID", pd.Series(dtype=object)).astype(str))
        if board_ids and grade_ids != board_ids:
            missing = len(board_ids - grade_ids)
            extra = len(grade_ids - board_ids)
            raise StorageOperationError(f"Graded board Game IDs do not exactly match the published board (missing={missing}, extra={extra}).")
        digest = sha256_frame(frame)
        now = datetime.now(timezone.utc).isoformat()
        metrics = slate_grade_metrics(frame)
        clean_metrics = {}
        for key, value in metrics.items():
            if isinstance(value, (np.floating, float)) and not np.isfinite(value):
                clean_metrics[key] = None
            elif isinstance(value, np.integer):
                clean_metrics[key] = int(value)
            elif isinstance(value, np.floating):
                clean_metrics[key] = float(value)
            else:
                clean_metrics[key] = value
        payload = {
            "grading_filename": filename,
            "grading_sha256": digest,
            "grading_json": dataframe_records(frame),
            "metrics_json": clean_metrics,
            "graded_at": now,
            "graded_by": actor,
            "updated_at": now,
        }
        try:
            resp = client.table(self.TABLE).update(payload).eq("slate_date", report.slate_date).execute()
            data = self._data(resp)
            return dict(data[0]) if data else {**existing, **payload}
        except Exception as exc:
            raise StorageOperationError(f"Grading publish failed: {type(exc).__name__}") from exc
