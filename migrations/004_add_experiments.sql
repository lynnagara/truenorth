CREATE TABLE experiment (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO experiment (id, name, description) VALUES (1, 'default', 'price + fundamentals + macro');

ALTER TABLE analysis ADD COLUMN experiment_id INTEGER REFERENCES experiment(id);

UPDATE analysis SET experiment_id = 1;
