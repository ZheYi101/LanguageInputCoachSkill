#!/usr/bin/env python3
"""Summarize review pressure for english-input-coach."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone


def parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize review agenda.")
    parser.add_argument("db", help="Path to state.db")
    parser.add_argument("--language", required=True, help="Language code, e.g. en")
    parser.add_argument("--limit-categories", type=int, default=3)
    parser.add_argument("--limit-items", type=int, default=5)
    args = parser.parse_args()

    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row

    now = utc_now()
    last_session_row = connection.execute(
        "SELECT MAX(finished_at) AS last_finished FROM sessions WHERE language = ?",
        (args.language,),
    ).fetchone()
    last_finished = parse_iso8601(last_session_row["last_finished"]) if last_session_row else None
    days_since_last_session = None
    if last_finished:
        days_since_last_session = max((now - last_finished).days, 0)

    active_rows = connection.execute(
        """
        SELECT review_category, content, due_at, priority_score, status
        FROM review_items
        WHERE language = ? AND status = 'active'
        """,
        (args.language,),
    ).fetchall()

    overdue_count = 0
    due_soon_count = 0
    categories: dict[str, dict[str, object]] = {}
    preview_items = []

    for row in active_rows:
        due_at = parse_iso8601(row["due_at"])
        if due_at and due_at <= now:
            overdue_count += 1
        elif due_at and (due_at - now).days <= 3:
            due_soon_count += 1

        category = row["review_category"] or "uncategorized"
        bucket = categories.setdefault(category, {"count": 0, "max_priority": 0.0})
        bucket["count"] = int(bucket["count"]) + 1
        bucket["max_priority"] = max(float(bucket["max_priority"]), float(row["priority_score"] or 0.0))

        preview_items.append(
            {
                "review_category": category,
                "content": row["content"],
                "due_at": row["due_at"],
                "priority_score": row["priority_score"] or 0.0,
            }
        )

    category_list = sorted(
        (
            {
                "review_category": name,
                "count": stats["count"],
                "max_priority": stats["max_priority"],
            }
            for name, stats in categories.items()
        ),
        key=lambda item: (item["max_priority"], item["count"]),
        reverse=True,
    )[: args.limit_categories]

    item_list = sorted(
        preview_items,
        key=lambda item: (item["priority_score"], item["due_at"] or ""),
        reverse=True,
    )[: args.limit_items]

    if overdue_count >= 5:
        recommended_mode = "review_first"
    elif overdue_count >= 1 or due_soon_count >= 3:
        recommended_mode = "mixed"
    else:
        recommended_mode = "new_content_first"

    output = {
        "language": args.language,
        "days_since_last_session": days_since_last_session,
        "overdue_items": overdue_count,
        "due_soon_items": due_soon_count,
        "focus_groups": category_list,
        "item_preview": item_list,
        "display_mode": "summary_first",
        "recommended_mode": recommended_mode,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
