CREATE TABLE source_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_name TEXT NOT NULL,
  source_url TEXT,
  source_type TEXT NOT NULL,
  collection_method TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
  max_frequency TEXT,
  compliance_notes TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE raw_deal_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_record_id INTEGER REFERENCES source_records(id) ON DELETE SET NULL,
  source_url TEXT,
  source_name TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  raw_text TEXT NOT NULL,
  raw_html_path TEXT,
  raw_payload_json TEXT,
  http_status INTEGER,
  collector_name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE banking_deals (
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

CREATE TABLE banking_deal_terms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  deal_id INTEGER NOT NULL UNIQUE REFERENCES banking_deals(id) ON DELETE CASCADE,
  minimum_deposit_amount_cents INTEGER CHECK (
    minimum_deposit_amount_cents IS NULL OR minimum_deposit_amount_cents >= 0
  ),
  direct_deposit_required INTEGER CHECK (
    direct_deposit_required IS NULL OR direct_deposit_required IN (0, 1)
  ),
  direct_deposit_minimum_cents INTEGER CHECK (
    direct_deposit_minimum_cents IS NULL OR direct_deposit_minimum_cents >= 0
  ),
  minimum_balance_required_cents INTEGER CHECK (
    minimum_balance_required_cents IS NULL OR minimum_balance_required_cents >= 0
  ),
  balance_hold_days INTEGER CHECK (
    balance_hold_days IS NULL OR balance_hold_days >= 0
  ),
  monthly_fee_cents INTEGER CHECK (
    monthly_fee_cents IS NULL OR monthly_fee_cents >= 0
  ),
  monthly_fee_waiver_terms TEXT,
  early_closure_fee_cents INTEGER CHECK (
    early_closure_fee_cents IS NULL OR early_closure_fee_cents >= 0
  ),
  hard_pull_risk INTEGER CHECK (
    hard_pull_risk IS NULL OR hard_pull_risk IN (0, 1)
  ),
  soft_pull_only INTEGER CHECK (
    soft_pull_only IS NULL OR soft_pull_only IN (0, 1)
  ),
  state_restrictions TEXT,
  new_customer_only INTEGER CHECK (
    new_customer_only IS NULL OR new_customer_only IN (0, 1)
  ),
  household_limit TEXT,
  terms_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE deal_status_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  deal_id INTEGER NOT NULL REFERENCES banking_deals(id) ON DELETE CASCADE,
  old_status TEXT CHECK (
    old_status IS NULL
    OR old_status IN (
      'new',
      'needs_review',
      'watching',
      'interested',
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

CREATE TABLE deal_change_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  deal_id INTEGER NOT NULL REFERENCES banking_deals(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  changed_fields_json TEXT,
  note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_raw_deal_snapshots_content_hash
  ON raw_deal_snapshots(content_hash);

CREATE INDEX idx_banking_deals_subcategory
  ON banking_deals(subcategory);

CREATE INDEX idx_banking_deals_status
  ON banking_deals(status);

CREATE INDEX idx_deal_status_events_deal_id
  ON deal_status_events(deal_id);
