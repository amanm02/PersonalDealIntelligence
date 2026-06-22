CREATE TABLE banking_score_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  deal_id INTEGER NOT NULL REFERENCES banking_deals(id) ON DELETE CASCADE,
  banking_run_id INTEGER REFERENCES banking_runs(id) ON DELETE SET NULL,
  scoring_version TEXT NOT NULL,
  scoring_config_hash TEXT NOT NULL,
  scored_as_of TEXT NOT NULL,
  estimated_net_value_cents INTEGER NOT NULL,
  score_0_to_100 INTEGER NOT NULL CHECK (
    score_0_to_100 >= 0 AND score_0_to_100 <= 100
  ),
  score_band TEXT NOT NULL,
  recommended_action TEXT NOT NULL,
  score_components_json TEXT NOT NULL,
  missing_data_warnings_json TEXT NOT NULL,
  score_explanation TEXT NOT NULL,
  expiration_urgency TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_banking_score_records_deal_id
  ON banking_score_records(deal_id, created_at DESC, id DESC);

CREATE INDEX idx_banking_score_records_banking_run_id
  ON banking_score_records(banking_run_id);
