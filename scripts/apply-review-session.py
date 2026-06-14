#!/usr/bin/env python3
"""Record a completed review session and update spaced review state."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

VALID_RESULTS = {"again", "hard", "good", "easy", "mastered"}


def read_payload(input_file: str | None) -> dict:
    if input_file:
        raw = Path(input_file).read_text(encoding="utf-8-sig")
    else:
        raw = sys.stdin.read().lstrip("\ufeff")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object.")
    return payload


def parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def as_float(value: object, default: float) -> float:
    if value is None:
        return default
    return float(value)


def prepare_session(payload: dict, now: datetime) -> dict:
    session = dict(payload.get("session") or {})
    session.setdefault("id", str(uuid.uuid4()))
    session.setdefault("session_type", "review")
    session.setdefault("status", "completed")
    session.setdefault("track", None)
    session.setdefault("source_id", None)
    session.setdefault("segment_id", None)
    session.setdefault("lesson_path", None)
    session.setdefault("answers_path", None)
    session.setdefault("feedback_path", None)
    session.setdefault("started_at", isoformat_z(now))
    session.setdefault("finished_at", isoformat_z(now))
    if not session.get("language"):
        session["language"] = payload.get("language")
    if not session.get("language"):
        raise ValueError("Review session requires `language`.")
    return session


def fetch_item(connection: sqlite3.Connection, item_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT id, language, track, source_id, segment_id, review_category, item_type,
               content, normalized_key, first_seen_at, last_seen_at, last_reviewed_at,
               due_at, interval_days, stability, priority_score, status
        FROM review_items
        WHERE id = ?
        """,
        (item_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown review item: {item_id}")
    return row


def schedule_item(item: sqlite3.Row, result: str, reviewed_at: datetime) -> dict[str, object]:
    if result not in VALID_RESULTS:
        raise ValueError(f"Unsupported review result: {result}")

    old_interval = as_float(item["interval_days"], 1.0)
    old_stability = as_float(item["stability"], 0.3)
    old_priority = as_float(item["priority_score"], 0.5)

    if result == "mastered":
        return {
            "status": "mastered",
            "last_seen_at": isoformat_z(reviewed_at),
            "last_reviewed_at": isoformat_z(reviewed_at),
            "due_at": None,
            "interval_days": clamp(max(old_interval, 7.0), 7.0, 180.0),
            "stability": clamp(max(old_stability, 0.92), 0.05, 1.0),
            "priority_score": clamp(min(old_priority, 0.2), 0.0, 1.0),
        }

    outcome_params = {
        "again": {
            "interval": max(0.25, old_interval * 0.5),
            "stability_delta": -0.16,
            "priority_delta": 0.18,
            "due_at": reviewed_at + timedelta(hours=6),
        },
        "hard": {
            "interval": max(1.0, old_interval * 1.35),
            "stability_delta": 0.03,
            "priority_delta": 0.08,
            "due_at": reviewed_at + timedelta(days=max(1.0, old_interval * 1.35)),
        },
        "good": {
            "interval": max(1.0, old_interval * 2.2),
            "stability_delta": 0.12,
            "priority_delta": -0.05,
            "due_at": reviewed_at + timedelta(days=max(1.0, old_interval * 2.2)),
        },
        "easy": {
            "interval": max(2.0, old_interval * 3.6),
            "stability_delta": 0.2,
            "priority_delta": -0.12,
            "due_at": reviewed_at + timedelta(days=max(2.0, old_interval * 3.6)),
        },
    }[result]

    next_stability = clamp(old_stability + outcome_params["stability_delta"], 0.05, 1.0)
    next_priority = clamp(
        old_priority + outcome_params["priority_delta"] + max(0.0, 0.4 - next_stability) * 0.25,
        0.0,
        1.0,
    )

    return {
        "status": "active",
        "last_seen_at": isoformat_z(reviewed_at),
        "last_reviewed_at": isoformat_z(reviewed_at),
        "due_at": isoformat_z(outcome_params["due_at"]),
        "interval_days": clamp(outcome_params["interval"], 0.25, 180.0),
        "stability": next_stability,
        "priority_score": next_priority,
    }


def upsert_session(connection: sqlite3.Connection, session: dict) -> None:
    connection.execute(
        """
        INSERT INTO sessions (
            id, language, track, session_type, source_id, segment_id, lesson_path,
            answers_path, feedback_path, started_at, finished_at, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            language = excluded.language,
            track = excluded.track,
            session_type = excluded.session_type,
            source_id = excluded.source_id,
            segment_id = excluded.segment_id,
            lesson_path = excluded.lesson_path,
            answers_path = excluded.answers_path,
            feedback_path = excluded.feedback_path,
            started_at = excluded.started_at,
            finished_at = excluded.finished_at,
            status = excluded.status
        """,
        (
            session["id"],
            session["language"],
            session["track"],
            session["session_type"],
            session["source_id"],
            session["segment_id"],
            session["lesson_path"],
            session["answers_path"],
            session["feedback_path"],
            session["started_at"],
            session["finished_at"],
            session["status"],
        ),
    )


def insert_profile_events(connection: sqlite3.Connection, events: list[dict], default_session_id: str) -> list[str]:
    inserted: list[str] = []
    for event in events:
        event_id = event.get("id") or str(uuid.uuid4())
        created_at = event.get("created_at") or isoformat_z(utc_now())
        connection.execute(
            """
            INSERT INTO profile_events (
                id, language, session_id, event_type, signal, evidence, strength, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                language = excluded.language,
                session_id = excluded.session_id,
                event_type = excluded.event_type,
                signal = excluded.signal,
                evidence = excluded.evidence,
                strength = excluded.strength,
                created_at = excluded.created_at
            """,
            (
                event_id,
                event["language"],
                event.get("session_id") or default_session_id,
                event["event_type"],
                event["signal"],
                event.get("evidence"),
                event.get("strength"),
                created_at,
            ),
        )
        inserted.append(event_id)
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a completed review session.")
    parser.add_argument("db", help="Path to state.db")
    parser.add_argument("--input-file", help="Read payload from file instead of stdin.")
    args = parser.parse_args()

    payload = read_payload(args.input_file)
    now = utc_now()
    session = prepare_session(payload, now)
    reviewed_items = payload.get("reviewed_items") or []
    if not isinstance(reviewed_items, list) or not reviewed_items:
        raise ValueError("Payload requires a non-empty `reviewed_items` list.")
    profile_events = payload.get("profile_events") or []
    if not isinstance(profile_events, list):
        raise ValueError("`profile_events` must be a list when provided.")

    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    outcomes = Counter()
    updated_items: list[dict[str, object]] = []

    try:
        with connection:
            upsert_session(connection, session)

            for item_payload in reviewed_items:
                item_id = item_payload["id"]
                result = item_payload["result"]
                reviewed_at = parse_iso8601(item_payload.get("reviewed_at")) or parse_iso8601(session["finished_at"]) or now
                item = fetch_item(connection, item_id)
                update = schedule_item(item, result, reviewed_at)
                connection.execute(
                    """
                    UPDATE review_items
                    SET last_seen_at = ?, last_reviewed_at = ?, due_at = ?,
                        interval_days = ?, stability = ?, priority_score = ?, status = ?
                    WHERE id = ?
                    """,
                    (
                        update["last_seen_at"],
                        update["last_reviewed_at"],
                        update["due_at"],
                        update["interval_days"],
                        update["stability"],
                        update["priority_score"],
                        update["status"],
                        item_id,
                    ),
                )
                outcomes[result] += 1
                updated_items.append(
                    {
                        "id": item_id,
                        "content": item["content"],
                        "result": result,
                        "status": update["status"],
                        "due_at": update["due_at"],
                        "interval_days": update["interval_days"],
                        "stability": update["stability"],
                        "priority_score": update["priority_score"],
                    }
                )

            inserted_events = insert_profile_events(connection, profile_events, session["id"])
    finally:
        connection.close()

    print(
        json.dumps(
            {
                "session_id": session["id"],
                "reviewed_count": len(updated_items),
                "outcomes": dict(outcomes),
                "profile_event_ids": inserted_events,
                "updated_items": updated_items,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
