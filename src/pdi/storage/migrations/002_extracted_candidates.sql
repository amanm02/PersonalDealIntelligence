CREATE TABLE banking_deal_candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  raw_snapshot_id INTEGER NOT NULL REFERENCES raw_deal_snapshots(id) ON DELETE CASCADE,
  title TEXT,
  institution_name TEXT,
  category TEXT NOT NULL DEFAULT 'banking' CHECK (category = 'banking'),
  subcategory TEXT CHECK (
    subcategory IS NULL OR subcategory IN (
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
  currency TEXT NOT NULL DEFAULT 'USD',
  source_url TEXT,
  source_name TEXT,
  retrieved_at TEXT,
  expires_at TEXT,
  application_deadline TEXT,
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
  state_restrictions_json TEXT,
  new_customer_only INTEGER CHECK (
    new_customer_only IS NULL OR new_customer_only IN (0, 1)
  ),
  household_limit TEXT,
  hard_pull_risk INTEGER CHECK (
    hard_pull_risk IS NULL OR hard_pull_risk IN (0, 1)
  ),
  soft_pull_only INTEGER CHECK (
    soft_pull_only IS NULL OR soft_pull_only IN (0, 1)
  ),
  evidence_spans_json TEXT,
  missing_fields_json TEXT,
  extraction_notes_json TEXT,
  tiered_bonus_json TEXT,
  raw_pattern_matches_json TEXT,
  confidence_score REAL CHECK (
    confidence_score IS NULL
    OR (confidence_score >= 0 AND confidence_score <= 1)
  ),
  rejected INTEGER NOT NULL DEFAULT 0 CHECK (rejected IN (0, 1)),
  rejection_reason TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_banking_deal_candidates_raw_snapshot_id
  ON banking_deal_candidates(raw_snapshot_id);

CREATE INDEX idx_banking_deal_candidates_subcategory
  ON banking_deal_candidates(subcategory);

CREATE INDEX idx_banking_deal_candidates_rejected
  ON banking_deal_candidates(rejected);
