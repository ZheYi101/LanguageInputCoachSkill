#!/usr/bin/env python3
"""Apply user-controlled review and source actions with historical trace."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ITEM_STATUSES = {"active", "paused", "ignored", "deleted", "mastered"}
CATEGORY_STATUSES = ITEM_STATUSES


def read_payload(input_file: str | None) -> list[dict]:
    if input_file:
        raw = Path(input_file).read_text(encoding="utf-8-sig")
    else:
        raw = sys.stdin.read().lstrip("\ufeff")
    payload = json.loads(raw)
    if isinstance(payload, dict):
        return [payload]
    if not isinstance(payload, list):
        raise ValueError("Payload must be an object or a list of objects.")
    return payload


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def record_user_action(
    connection: sqlite3.Connection,
    *,
    target_type: str,
    target_id: str,
    action_type: str,
    reason: str | None,
    created_at: str,
) -> str:
    action_id = str(uuid.uuid4())
    connection.execute(
        """
        INSERT INTO user_actions (id, target_type, target_id, action_type, reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (action_id, target_type, target_id, action_type, reason, created_at),
    )
    return action_id


def apply_item_status(
    connection: sqlite3.Connection, item_ids: list[str], status: str, reason: str | None, created_at: str
) -> dict:
    if status not in ITEM_STATUSES:
        raise ValueError(f"Unsupported item status: {status}")
    if not item_ids:
        raise ValueError("`item_ids` must be non-empty.")

    placeholders = ", ".join("?" for _ in item_ids)
    cursor = connection.execute(
        f"UPDATE review_items SET status = ? WHERE id IN ({placeholders})",
        [status, *item_ids],
    )
    action_ids = [
        record_user_action(
            connection,
            target_type="review_item",
            target_id=item_id,
            action_type=f"set_status:{status}",
            reason=reason,
            created_at=created_at,
        )
        for item_id in item_ids
    ]
    return {"action": "set_item_status", "rows_affected": cursor.rowcount, "user_action_ids": action_ids}


def apply_category_status(
    connection: sqlite3.Connection,
    *,
    language: str,
    review_category: str,
    status: str,
    reason: str | None,
    created_at: str,
) -> dict:
    if status not in CATEGORY_STATUSES:
        raise ValueError(f"Unsupported category status: {status}")
    cursor = connection.execute(
        """
        UPDATE review_items
        SET status = ?
        WHERE language = ? AND review_category = ? AND status != 'deleted'
        """,
        (status, language, review_category),
    )
    action_id = record_user_action(
        connection,
        target_type="review_category",
        target_id=f"{language}:{review_category}",
        action_type=f"set_status:{status}",
        reason=reason,
        created_at=created_at,
    )
    return {"action": "set_category_status", "rows_affected": cursor.rowcount, "user_action_ids": [action_id]}


def apply_archive_source(
    connection: sqlite3.Connection, *, source_id: str, reason: str | None, created_at: str
) -> dict:
    source_cursor = connection.execute("UPDATE sources SET status = 'archived' WHERE id = ?", (source_id,))
    segment_cursor = connection.execute(
        "UPDATE segments SET status = 'archived' WHERE source_id = ? AND status != 'deleted'",
        (source_id,),
    )
    review_cursor = connection.execute(
        """
        UPDATE review_items
        SET status = 'ignored'
        WHERE source_id = ? AND status IN ('active', 'paused')
        """,
        (source_id,),
    )
    action_id = record_user_action(
        connection,
        target_type="source",
        target_id=source_id,
        action_type="archive",
        reason=reason,
        created_at=created_at,
    )
    return {
        "action": "archive_source",
        "source_rows_affected": source_cursor.rowcount,
        "segment_rows_affected": segment_cursor.rowcount,
        "review_rows_affected": review_cursor.rowcount,
        "user_action_ids": [action_id],
    }


def apply_operation(connection: sqlite3.Connection, operation: dict) -> dict:
    created_at = operation.get("created_at") or utc_now_iso()
    reason = operation.get("reason")
    action = operation["action"]

    if action == "set_item_status":
        return apply_item_status(connection, operation["item_ids"], operation["status"], reason, created_at)
    if action == "mark_item_not_useful":
        return apply_item_status(connection, operation["item_ids"], "ignored", reason, created_at)
    if action == "set_category_status":
        return apply_category_status(
            connection,
            language=operation["language"],
            review_category=operation["review_category"],
            status=operation["status"],
            reason=reason,
            created_at=created_at,
        )
    if action == "archive_source":
        return apply_archive_source(connection, source_id=operation["source_id"], reason=reason, created_at=created_at)
    raise ValueError(f"Unsupported action: {action}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply review and source control actions.")
    parser.add_argument("db", help="Path to state.db")
    parser.add_argument("--input-file", help="Read payload from file instead of stdin.")
    args = parser.parse_args()

    operations = read_payload(args.input_file)

    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    results = []
    try:
        with connection:
            for operation in operations:
                results.append(apply_operation(connection, operation))
    finally:
        connection.close()

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
