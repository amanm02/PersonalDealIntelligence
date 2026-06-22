ALTER TABLE banking_deal_source_links
  ADD COLUMN link_type TEXT NOT NULL DEFAULT 'candidate_source';

ALTER TABLE banking_deal_source_links
  ADD COLUMN trust_tier TEXT;

ALTER TABLE banking_deal_source_links
  ADD COLUMN official_source INTEGER CHECK (
    official_source IS NULL OR official_source IN (0, 1)
  );

ALTER TABLE banking_deal_source_links
  ADD COLUMN notes TEXT;
