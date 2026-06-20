PRAGMA foreign_keys = OFF;

CREATE TABLE banking_deals_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_key TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  institution_name TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'banking' CHECK (category = 'banking'),
  subcategory TEXT NOT NULL CHECK (
    subcategory IN (
      'checking_bonus',
      'savings_bonus',
      'checking_savings_bundle',
      'brokerage_bonus',
      'money_market_bonus',
      'cd_bonus',
      'credit_card_signup_bonus'
    )
  ),
  bonus_amount_cents INTEGER CHECK (
    bonus_amount_cents IS NULL OR bonus_amount_cents >= 0
  ),
  estimated_net_value_cents INTEGER,
  currency TEXT NOT NULL DEFAULT 'USD',
  source_url TEXT,
  source_name TEXT,
  discovered_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  expires_at TEXT,
  application_deadline TEXT,
  status TEXT NOT NULL DEFAULT 'new' CHECK (
    status IN (
      'new',
      'needs_review',
      'watching',
      'interested',
      'in_progress',
      'applied',
      'completed',
      'skipped',
      'expired',
      'rejected'
    )
  ),
  confidence_score REAL CHECK (
    confidence_score IS NULL
    OR (confidence_score >= 0 AND confidence_score <= 1)
  ),
  raw_snapshot_id INTEGER REFERENCES raw_deal_snapshots(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO banking_deals_new (
  id,
  canonical_key,
  title,
  institution_name,
  category,
  subcategory,
  bonus_amount_cents,
  estimated_net_value_cents,
  currency,
  source_url,
  source_name,
  discovered_at,
  last_seen_at,
  expires_at,
  application_deadline,
  status,
  confidence_score,
  raw_snapshot_id,
  created_at,
  updated_at
)
SELECT
  id,
  canonical_key,
  title,
  institution_name,
  category,
  subcategory,
  bonus_amount_cents,
  estimated_net_value_cents,
  currency,
  source_url,
  source_name,
  discovered_at,
  last_seen_at,
  expires_at,
  application_deadline,
  status,
  confidence_score,
  raw_snapshot_id,
  created_at,
  updated_at
FROM banking_deals;

DROP TABLE banking_deals;
ALTER TABLE banking_deals_new RENAME TO banking_deals;

CREATE INDEX idx_banking_deals_subcategory
  ON banking_deals(subcategory);

CREATE INDEX idx_banking_deals_status
  ON banking_deals(status);

CREATE TABLE deal_status_events_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  deal_id INTEGER NOT NULL REFERENCES banking_deals(id) ON DELETE CASCADE,
  old_status TEXT CHECK (
    old_status IS NULL
    OR old_status IN (
      'new',
      'needs_review',
      'watching',
      'interested',
      'in_progress',
      'applied',
      'completed',
      'skipped',
      'expired',
      'rejected'
    )
  ),
  new_status TEXT NOT NULL CHECK (
    new_status IN (
      'new',
      'needs_review',
      'watching',
      'interested',
      'in_progress',
      'applied',
      'completed',
      'skipped',
      'expired',
      'rejected'
    )
  ),
  note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO deal_status_events_new (
  id,
  deal_id,
  old_status,
  new_status,
  note,
  created_at
)
SELECT
  id,
  deal_id,
  old_status,
  new_status,
  note,
  created_at
FROM deal_status_events;

DROP TABLE deal_status_events;
ALTER TABLE deal_status_events_new RENAME TO deal_status_events;

CREATE INDEX idx_deal_status_events_deal_id
  ON deal_status_events(deal_id);

PRAGMA foreign_keys = ON;
