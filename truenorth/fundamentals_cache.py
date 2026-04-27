import json
from dataclasses import asdict

import psycopg

from truenorth.massive import Fundamentals


class FundamentalsCache:
    def __init__(self, database_url: str, ttl_hours: int = 24):
        self._database_url = database_url
        self._ttl_hours = ttl_hours

    def get(self, ticker: str) -> Fundamentals | None:
        with psycopg.connect(self._database_url) as conn:
            row = conn.execute(
                "SELECT data FROM fundamentals_cache WHERE ticker = %s AND fetched_at > NOW() - %s * INTERVAL '1 hour'",
                (ticker, self._ttl_hours),
            ).fetchone()
        if row:
            return Fundamentals(**row[0])
        return None

    def set(self, ticker: str, fundamentals: Fundamentals) -> None:
        with psycopg.connect(self._database_url) as conn:
            conn.execute(
                """
                INSERT INTO fundamentals_cache (ticker, data)
                VALUES (%s, %s)
                ON CONFLICT (ticker) DO UPDATE SET
                    fetched_at = NOW(),
                    data = EXCLUDED.data
                """,
                (ticker, json.dumps(asdict(fundamentals))),
            )
            conn.commit()
