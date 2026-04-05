CREATE TABLE analysis (
    id           BIGSERIAL PRIMARY KEY,
    ticker       TEXT NOT NULL,
    signal       FLOAT NOT NULL CHECK (signal >= -1.0 AND signal <= 1.0),
    entry_price  FLOAT,
    target_price FLOAT,
    last_price   FLOAT NOT NULL,
    reasoning    TEXT NOT NULL,
    fundamentals JSONB NOT NULL,
    macro        JSONB NOT NULL,
    model        TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    price_at_1w  FLOAT,
    price_at_2w  FLOAT,
    price_at_4w  FLOAT,
    price_at_8w  FLOAT,
    price_at_12w FLOAT
);
