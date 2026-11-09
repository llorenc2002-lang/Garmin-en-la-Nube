"""Daily Garmin Personal API sync to Neon Postgres for GitHub Actions."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

import psycopg
from garmin_personal_api import GarminPersonalApiClient, PersonalApiAuthenticator
from psycopg.types.json import Jsonb

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logging.getLogger("garmin_personal_api").setLevel(logging.CRITICAL)


class SyncFailure(Exception):
    def __init__(self, stage: str, error_type: str, status_code: Any = None):
        self.stage = stage
        self.error_type = error_type
        self.status_code = status_code if isinstance(status_code, int) else None


def _garmin_call(stage: str, call: Any) -> Any:
    try:
        return call()
    except Exception as exc:
        raise SyncFailure(stage, type(exc).__name__, getattr(exc, "status_code", None)) from None


def _rows(value: Any, dataset: str, fallback_day: date) -> list[tuple[str, date, str, Any]]:
    items = value if isinstance(value, list) else [value]
    rows = []
    for index, payload in enumerate(items):
        if payload is None:
            continue
        if isinstance(payload, dict):
            external_id = next(
                (str(payload[k]) for k in ("activityId", "id", "calendarDate", "date") if payload.get(k) is not None),
                str(index),
            )
            date_value = next(
                (payload[k] for k in ("calendarDate", "date", "startTimeLocal", "startTimeGMT") if payload.get(k)),
                fallback_day.isoformat(),
            )
        else:
            external_id, date_value = str(index), fallback_day.isoformat()
        try:
            record_day = date.fromisoformat(str(date_value)[:10])
        except ValueError:
            record_day = fallback_day
        rows.append((dataset, record_day, external_id, payload))
    return rows


def sync() -> None:
    api_key = os.environ.get("GARMIN_PERSONAL_API_KEY", "").strip()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not api_key or not database_url:
        raise RuntimeError("required secret is missing")

    lookback = max(1, min(int(os.environ.get("SYNC_LOOKBACK_DAYS", "7")), 90))
    end_day = date.today()
    start_day = end_day - timedelta(days=lookback - 1)
    start, end = start_day.isoformat(), end_day.isoformat()
    collected: list[tuple[str, date, str, Any]] = []
    activity_files: list[tuple[int, date, bytes]] = []

    with psycopg.connect(database_url, connect_timeout=20) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS garmin_records (
                dataset TEXT NOT NULL,
                record_date DATE NOT NULL,
                external_id TEXT NOT NULL,
                payload JSONB NOT NULL,
                synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (dataset, record_date, external_id)
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS garmin_activity_files (
                activity_id BIGINT PRIMARY KEY,
                activity_date DATE NOT NULL,
                zip_data BYTEA NOT NULL,
                synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )"""
        )
        known_activity_ids = {
            row[0]
            for row in conn.execute(
                "SELECT activity_id FROM garmin_activity_files WHERE activity_date >= %s AND activity_date <= %s",
                (start_day, end_day),
            ).fetchall()
        }

    with PersonalApiAuthenticator() as authenticator:
        token = _garmin_call("token exchange", lambda: authenticator.obtain_token(api_key))
    with GarminPersonalApiClient(token.access_token) as client:
        range_calls = [
            ("daily summaries", "daily_summaries", lambda: client.get_daily_summaries(start, end)),
            ("sleep", "sleep_summaries", lambda: client.get_daily_sleep_summaries(start, end)),
            ("steps", "steps", lambda: client.get_daily_steps(start, end)),
            ("stress", "stress", lambda: client.get_daily_stress(start, end)),
            ("HRV", "hrv", lambda: client.get_daily_hrv_summaries(start, end)),
            ("body battery", "body_battery", lambda: client.get_daily_body_battery(start, end)),
        ]
        for stage, dataset, call in range_calls:
            collected.extend(_rows(_garmin_call(stage, call), dataset, end_day))

        page_start, page_size = 0, 100
        while True:
            activities = _garmin_call(
                "activity search",
                lambda: client.search_activities(
                    start=page_start,
                    limit=page_size,
                    start_date=start,
                    end_date=end,
                ),
            )
            page = activities if isinstance(activities, list) else []
            collected.extend(_rows(page, "activities", end_day))
            for activity in page:
                if not isinstance(activity, dict):
                    continue
                try:
                    activity_id = int(activity.get("activityId", 0))
                    activity_date = date.fromisoformat(
                        str(activity.get("startTimeLocal") or activity.get("startTimeGMT") or end)[:10]
                    )
                except (TypeError, ValueError):
                    continue
                if activity_id <= 0 or activity_id in known_activity_ids:
                    continue
                try:
                    zip_data = client.download_activity(activity_id)
                    if zip_data:
                        activity_files.append((activity_id, activity_date, zip_data))
                        known_activity_ids.add(activity_id)
                except Exception:
                    # Some activities have no downloadable file; retry on a later run.
                    continue
            if len(page) < page_size:
                break
            page_start += page_size

    with psycopg.connect(database_url, connect_timeout=20) as conn:
        if collected:
            conn.executemany(
                """INSERT INTO garmin_records (dataset, record_date, external_id, payload)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (dataset, record_date, external_id)
                   DO UPDATE SET payload = EXCLUDED.payload, synced_at = now()""",
                [(ds, day, ext_id, Jsonb(payload)) for ds, day, ext_id, payload in collected],
            )
        if activity_files:
            conn.executemany(
                """INSERT INTO garmin_activity_files (activity_id, activity_date, zip_data)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (activity_id) DO NOTHING""",
                activity_files,
            )
    logging.warning(
        "sync completed: %d JSON rows and %d activity files (%s to %s)",
        len(collected),
        len(activity_files),
        start,
        end,
    )


if __name__ == "__main__":
    try:
        sync()
    except SyncFailure as exc:
        status = f" HTTP {exc.status_code}" if exc.status_code is not None else ""
        logging.error("sync failed at %s (%s%s)", exc.stage, exc.error_type, status)
        raise SystemExit(1) from None
    except Exception as exc:
        # Keep health values, credentials, URLs, and API response bodies out of public run logs.
        logging.error("sync failed (%s)", type(exc).__name__)
        raise SystemExit(1) from None
