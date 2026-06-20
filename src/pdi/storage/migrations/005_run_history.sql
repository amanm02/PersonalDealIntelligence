CREATE TABLE banking_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  status TEXT NOT NULL CHECK (
    status IN ('running', 'succeeded', 'failed', 'blocked')
  ),
  dry_run INTEGER NOT NULL DEFAULT 1 CHECK (dry_run IN (0, 1)),
  source_count INTEGER NOT NULL DEFAULT 0 CHECK (source_count >= 0),
  raw_snapshot_count INTEGER NOT NULL DEFAULT 0 CHECK (raw_snapshot_count >= 0),
  candidate_count INTEGER NOT NULL DEFAULT 0 CHECK (candidate_count >= 0),
  rejected_candidate_count INTEGER NOT NULL DEFAULT 0 CHECK (
    rejected_candidate_count >= 0
  ),
  canonical_deal_count INTEGER NOT NULL DEFAULT 0 CHECK (
    canonical_deal_count >= 0
  ),
  duplicate_merge_count INTEGER NOT NULL DEFAULT 0 CHECK (
    duplicate_merge_count >= 0
  ),
  conflict_count INTEGER NOT NULL DEFAULT 0 CHECK (conflict_count >= 0),
  review_needed_deal_count INTEGER NOT NULL DEFAULT 0 CHECK (
    review_needed_deal_count >= 0
  ),
  scored_deal_count INTEGER NOT NULL DEFAULT 0 CHECK (scored_deal_count >= 0),
  expired_scored_deal_count INTEGER NOT NULL DEFAULT 0 CHECK (
    expired_scored_deal_count >= 0
  ),
  error_count INTEGER NOT NULL DEFAULT 0 CHECK (error_count >= 0),
  errors_json TEXT,
  digest_path TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE banking_run_locks (
  lock_name TEXT PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES banking_runs(id) ON DELETE CASCADE,
  hostname TEXT NOT NULL,
  pid INTEGER NOT NULL,
  lock_owner TEXT NOT NULL,
  acquired_at TEXT NOT NULL,
  stale_after TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_banking_runs_started_at
  ON banking_runs(started_at DESC);

CREATE INDEX idx_banking_runs_status
  ON banking_runs(status);
