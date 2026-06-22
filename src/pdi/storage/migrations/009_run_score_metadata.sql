ALTER TABLE banking_runs
  ADD COLUMN score_record_count INTEGER NOT NULL DEFAULT 0 CHECK (
    score_record_count >= 0
  );

ALTER TABLE banking_runs
  ADD COLUMN score_record_ids_json TEXT;
