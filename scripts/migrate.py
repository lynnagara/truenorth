#!/usr/bin/env python3
"""Run pending database migrations from the migrations/ directory."""

import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def run(database_url: str) -> None:
    with psycopg.connect(database_url) as conn:
        _ensure_migrations_table(conn)
        applied = _applied_migrations(conn)
        pending = _pending_migrations(applied)

        if not pending:
            print("No pending migrations.")
            return

        for path in pending:
            print(f"Applying {path.name}...")
            conn.execute(path.read_text())  # type: ignore[arg-type]
            conn.execute("INSERT INTO migrations (name) VALUES (%s)", (path.name,))
            conn.commit()
            print(f"  ✓ {path.name}")


def _ensure_migrations_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id         BIGSERIAL PRIMARY KEY,
            name       TEXT NOT NULL UNIQUE,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.commit()


def _applied_migrations(conn) -> set[str]:
    rows = conn.execute("SELECT name FROM migrations").fetchall()
    return {row[0] for row in rows}


def _pending_migrations(applied: set[str]) -> list[Path]:
    all_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    return [f for f in all_files if f.name not in applied]


if __name__ == "__main__":
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable not set", file=sys.stderr)
        sys.exit(1)
    run(database_url)
