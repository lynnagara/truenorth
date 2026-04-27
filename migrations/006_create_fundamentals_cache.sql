CREATE TABLE fundamentals_cache (
    ticker TEXT PRIMARY KEY,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    data JSONB NOT NULL
);
