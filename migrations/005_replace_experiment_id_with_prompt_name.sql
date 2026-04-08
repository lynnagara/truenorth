ALTER TABLE analysis ADD COLUMN prompt_name TEXT;

UPDATE analysis SET prompt_name = e.name
FROM experiment e
WHERE analysis.experiment_id = e.id;

-- remap legacy 'default' to the canonical prompt name
UPDATE analysis SET prompt_name = 'basic_fundamentals' WHERE prompt_name = 'default';

ALTER TABLE analysis ALTER COLUMN prompt_name SET NOT NULL;

ALTER TABLE analysis DROP COLUMN experiment_id;

DROP TABLE experiment;
