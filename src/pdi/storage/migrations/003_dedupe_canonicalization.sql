ALTER TABLE banking_deal_candidates
  ADD COLUMN canonical_deal_id INTEGER REFERENCES banking_deals(id) ON DELETE SET NULL;

ALTER TABLE banking_deal_candidates
  ADD COLUMN canonicalized_at TEXT;

ALTER TABLE banking_deal_candidates
  ADD COLUMN canonicalization_status TEXT CHECK (
    canonicalization_status IS NULL
    OR canonicalization_status IN ('created', 'matched', 'updated', 'skipped')
  );

CREATE TABLE banking_deal_source_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  deal_id INTEGER NOT NULL REFERENCES banking_deals(id) ON DELETE CASCADE,
  candidate_id INTEGER NOT NULL REFERENCES banking_deal_candidates(id) ON DELETE CASCADE,
  raw_snapshot_id INTEGER NOT NULL REFERENCES raw_deal_snapshots(id) ON DELETE CASCADE,
  source_name TEXT NOT NULL,
  source_url TEXT,
  source_authority TEXT NOT NULL DEFAULT 'unknown' CHECK (
    source_authority IN ('official', 'secondary', 'unknown')
  ),
  retrieved_at TEXT,
  confidence_score REAL CHECK (
    confidence_score IS NULL
    OR (confidence_score >= 0 AND confidence_score <= 1)
  ),
  evidence_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (deal_id, candidate_id)
);

CREATE INDEX idx_banking_deal_candidates_canonical_deal_id
  ON banking_deal_candidates(canonical_deal_id);

CREATE INDEX idx_banking_deal_candidates_canonicalization_status
  ON banking_deal_candidates(canonicalization_status);

CREATE INDEX idx_banking_deal_source_links_deal_id
  ON banking_deal_source_links(deal_id);

CREATE INDEX idx_deal_change_events_deal_id
  ON deal_change_events(deal_id);
