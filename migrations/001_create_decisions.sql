CREATE TABLE decisions (
    id          BIGSERIAL PRIMARY KEY,
    ticker      TEXT NOT NULL,
    signal      FLOAT NOT NULL CHECK (signal >= -1.0 AND signal <= 1.0),
    reasoning   TEXT NOT NULL,
    macro_context JSONB,
    model       TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
