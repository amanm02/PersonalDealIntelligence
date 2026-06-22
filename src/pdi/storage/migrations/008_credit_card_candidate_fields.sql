ALTER TABLE banking_deal_candidates
  ADD COLUMN issuer_name TEXT;

ALTER TABLE banking_deal_candidates
  ADD COLUMN card_name TEXT;

ALTER TABLE banking_deal_candidates
  ADD COLUMN product_family TEXT;

ALTER TABLE banking_deal_candidates
  ADD COLUMN customer_type TEXT CHECK (
    customer_type IS NULL OR customer_type IN ('personal', 'business', 'unknown')
  );

ALTER TABLE banking_deal_candidates
  ADD COLUMN card_network TEXT;

ALTER TABLE banking_deal_candidates
  ADD COLUMN offer_currency TEXT CHECK (
    offer_currency IS NULL OR offer_currency IN (
      'cash',
      'points',
      'miles',
      'statement_credit',
      'mixed',
      'unknown'
    )
  );

ALTER TABLE banking_deal_candidates
  ADD COLUMN headline_bonus_amount_json TEXT;

ALTER TABLE banking_deal_candidates
  ADD COLUMN headline_bonus_value_cents INTEGER CHECK (
    headline_bonus_value_cents IS NULL OR headline_bonus_value_cents >= 0
  );

ALTER TABLE banking_deal_candidates
  ADD COLUMN point_mile_valuation_assumption_id TEXT;

ALTER TABLE banking_deal_candidates
  ADD COLUMN minimum_spend_cents INTEGER CHECK (
    minimum_spend_cents IS NULL OR minimum_spend_cents >= 0
  );

ALTER TABLE banking_deal_candidates
  ADD COLUMN spend_window_days INTEGER CHECK (
    spend_window_days IS NULL OR spend_window_days >= 0
  );

ALTER TABLE banking_deal_candidates
  ADD COLUMN annual_fee_cents INTEGER CHECK (
    annual_fee_cents IS NULL OR annual_fee_cents >= 0
  );

ALTER TABLE banking_deal_candidates
  ADD COLUMN first_year_annual_fee_waived INTEGER CHECK (
    first_year_annual_fee_waived IS NULL OR first_year_annual_fee_waived IN (0, 1)
  );

ALTER TABLE banking_deal_candidates
  ADD COLUMN statement_credit_amount_cents INTEGER CHECK (
    statement_credit_amount_cents IS NULL OR statement_credit_amount_cents >= 0
  );

ALTER TABLE banking_deal_candidates
  ADD COLUMN statement_credit_requirements TEXT;

ALTER TABLE banking_deal_candidates
  ADD COLUMN bonus_payout_timing TEXT;

ALTER TABLE banking_deal_candidates
  ADD COLUMN targeted INTEGER CHECK (
    targeted IS NULL OR targeted IN (0, 1)
  );

ALTER TABLE banking_deal_candidates
  ADD COLUMN eligibility_restriction_notes_json TEXT;

ALTER TABLE banking_deal_candidates
  ADD COLUMN source_confidence REAL CHECK (
    source_confidence IS NULL
    OR (source_confidence >= 0 AND source_confidence <= 1)
  );

CREATE INDEX idx_banking_deal_candidates_card_name
  ON banking_deal_candidates(card_name);

CREATE INDEX idx_banking_deal_candidates_offer_currency
  ON banking_deal_candidates(offer_currency);
