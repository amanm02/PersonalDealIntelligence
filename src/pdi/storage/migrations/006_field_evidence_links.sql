CREATE TABLE banking_field_evidence_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  deal_id INTEGER NOT NULL REFERENCES banking_deals(id) ON DELETE CASCADE,
  candidate_id INTEGER REFERENCES banking_deal_candidates(id) ON DELETE SET NULL,
  raw_snapshot_id INTEGER NOT NULL REFERENCES raw_deal_snapshots(id) ON DELETE CASCADE,
  source_link_id INTEGER REFERENCES banking_deal_source_links(id) ON DELETE CASCADE,
  field_name TEXT NOT NULL,
  extracted_value_json TEXT,
  evidence_text TEXT NOT NULL,
  excerpt TEXT,
  start_offset INTEGER CHECK (start_offset IS NULL OR start_offset >= 0),
  end_offset INTEGER CHECK (end_offset IS NULL OR end_offset >= 0),
  confidence_score REAL CHECK (
    confidence_score IS NULL
    OR (confidence_score >= 0 AND confidence_score <= 1)
  ),
  extraction_method TEXT,
  extraction_version TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (source_link_id, field_name, start_offset, end_offset)
);

CREATE INDEX idx_banking_field_evidence_links_deal_id
  ON banking_field_evidence_links(deal_id);

CREATE INDEX idx_banking_field_evidence_links_candidate_id
  ON banking_field_evidence_links(candidate_id);

CREATE INDEX idx_banking_field_evidence_links_raw_snapshot_id
  ON banking_field_evidence_links(raw_snapshot_id);

CREATE INDEX idx_banking_field_evidence_links_field_name
  ON banking_field_evidence_links(field_name);
