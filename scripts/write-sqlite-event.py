#!/usr/bin/env python3
"""Apply controlled SQLite state changes for english-input-coach."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ALLOWED_TABLES = {
    "schema_meta",
    "sources",
    "segments",
    "sessions",
    "review_items",
    "profile_events",
    "user_actions",
}


def read_payload(input_file: str | None) -> object:
    if input_file:
        raw = Path(input_file).read_text(encoding="utf-8-sig")
    else:
        raw = sys.stdin.read().lstrip("\ufeff")
    return json.loads(raw)


def get_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def ensure_allowed(table: str) -> None:
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Unsupported table: {table}")


def apply_insert(connection: sqlite3.Connection, table: str, data: dict) -> dict:
    columns = get_columns(connection, table)
    payload = dict(data)
    if "id" in columns and "id" not in payload:
        payload["id"] = str(uuid.uuid4())
    keys = [key for key in payload if key in columns]
    placeholders = ", ".join("?" for _ in keys)
    sql = f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders})"
    connection.execute(sql, [payload[key] for key in keys])
    return {"table": table, "id": payload.get("id"), "op": "insert"}


def apply_upsert(connection: sqlite3.Connection, table: str, key_fields: list[str], data: dict) -> dict:
    columns = get_columns(connection, table)
    payload = dict(data)
    if "id" in columns and "id" not in payload and "id" not in key_fields:
        payload["id"] = str(uuid.uuid4())
    keys = [key for key in payload if key in columns]
    update_keys = [key for key in keys if key not in key_fields]
    if update_keys:
        sql = (
            f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)}) "
            f"ON CONFLICT({', '.join(key_fields)}) DO UPDATE SET "
            f"{', '.join(f'{key}=excluded.{key}' for key in update_keys)}"
        )
    else:
        sql = (
            f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)}) "
            f"ON CONFLICT({', '.join(key_fields)}) DO NOTHING"
        )
    connection.execute(sql, [payload[key] for key in keys])
    return {"table": table, "id": payload.get("id"), "op": "upsert"}


def apply_update(connection: sqlite3.Connection, table: str, data: dict, where: dict) -> dict:
    columns = get_columns(connection, table)
    set_keys = [key for key in data if key in columns]
    where_keys = [key for key in where if key in columns]
    if not set_keys or not where_keys:
        raise ValueError("Update requires valid set keys and where keys.")
    sql = (
        f"UPDATE {table} SET {', '.join(f'{key}=?' for key in set_keys)} "
        f"WHERE {' AND '.join(f'{key}=?' for key in where_keys)}"
    )
    values = [data[key] for key in set_keys] + [where[key] for key in where_keys]
    cursor = connection.execute(sql, values)
    return {"table": table, "rows_affected": cursor.rowcount, "op": "update"}


def apply_operation(connection: sqlite3.Connection, operation: dict) -> dict:
    table = operation["table"]
    ensure_allowed(table)
    op = operation["op"]
    if op == "insert":
        return apply_insert(connection, table, operation["data"])
    if op == "upsert":
        return apply_upsert(connection, table, operation["key_fields"], operation["data"])
    if op == "update":
        return apply_update(connection, table, operation["data"], operation["where"])
    raise ValueError(f"Unsupported operation: {op}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply controlled SQLite state changes.")
    parser.add_argument("db", help="Path to state.db")
    parser.add_argument("--input-file", help="Read payload from file instead of stdin.")
    args = parser.parse_args()

    payload = read_payload(args.input_file)
    operations = payload if isinstance(payload, list) else [payload]

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

    json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
