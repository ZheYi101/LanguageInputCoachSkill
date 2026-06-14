#!/usr/bin/env python3
"""Summarize review pressure for input-driven-language-coach."""

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


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def item_pressure(
    *,
    now: datetime,
    due_at: datetime | None,
    stability: float,
    priority_score: float,
) -> float:
    pressure = priority_score
    if due_at and due_at <= now:
        pressure += 1.0
    elif due_at and (due_at - now).total_seconds() <= 86400:
        pressure += 0.55
    elif due_at and (due_at - now).total_seconds() <= 3 * 86400:
        pressure += 0.25
    pressure += max(0.0, 0.45 - stability) * 1.2
    return round(clamp(pressure, 0.0, 3.0), 4)


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
        SELECT review_category, content, due_at, priority_score, stability, interval_days, status
        FROM review_items
        WHERE language = ? AND status = 'active'
        """,
        (args.language,),
    ).fetchall()

    overdue_count = 0
    due_soon_count = 0
    categories: dict[str, dict[str, object]] = {}
    preview_items = []
    overdue_preview = []
    due_soon_preview = []

    for row in active_rows:
        due_at = parse_iso8601(row["due_at"])
        stability = float(row["stability"] or 0.0)
        priority_score = float(row["priority_score"] or 0.0)
        pressure_score = item_pressure(
            now=now,
            due_at=due_at,
            stability=stability,
            priority_score=priority_score,
        )
        if due_at and due_at <= now:
            overdue_count += 1
        elif due_at and (due_at - now).days <= 3:
            due_soon_count += 1

        category = row["review_category"] or "uncategorized"
        bucket = categories.setdefault(category, {"count": 0, "max_priority": 0.0, "pressure_score": 0.0})
        bucket["count"] = int(bucket["count"]) + 1
        bucket["max_priority"] = max(float(bucket["max_priority"]), priority_score)
        bucket["pressure_score"] = float(bucket["pressure_score"]) + pressure_score

        item = {
            "review_category": category,
            "content": row["content"],
            "due_at": row["due_at"],
            "priority_score": priority_score,
            "stability": stability,
            "interval_days": float(row["interval_days"] or 0.0),
            "pressure_score": pressure_score,
        }
        preview_items.append(item)
        if due_at and due_at <= now:
            overdue_preview.append(item)
        elif due_at and (due_at - now).days <= 3:
            due_soon_preview.append(item)

    category_list = sorted(
        (
            {
                "review_category": name,
                "count": stats["count"],
                "max_priority": stats["max_priority"],
                "pressure_score": round(float(stats["pressure_score"]), 4),
            }
            for name, stats in categories.items()
        ),
        key=lambda item: (item["pressure_score"], item["max_priority"], item["count"]),
        reverse=True,
    )[: args.limit_categories]

    item_list = sorted(
        preview_items,
        key=lambda item: (-item["pressure_score"], item["due_at"] or "", -item["priority_score"]),
    )[: args.limit_items]

    overdue_preview = sorted(
        overdue_preview,
        key=lambda item: (item["due_at"] or "", -item["pressure_score"]),
    )[: args.limit_items]
    due_soon_preview = sorted(
        due_soon_preview,
        key=lambda item: (item["due_at"] or "", -item["pressure_score"]),
    )[: args.limit_items]

    if overdue_count >= 3 or (overdue_count >= 1 and any(item["pressure_score"] >= 1.5 for item in overdue_preview)):
        recommended_mode = "review_first"
    elif overdue_count >= 1 or due_soon_count >= 3 or any(item["pressure_score"] >= 1.0 for item in item_list):
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
        "overdue_preview": overdue_preview,
        "due_soon_preview": due_soon_preview,
        "display_mode": "summary_first",
        "recommended_mode": recommended_mode,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
