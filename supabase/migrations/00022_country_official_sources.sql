-- Migration 00022: Country Official Sources & Regulatory Watch Engine
-- Stores authenticated public procurement, building code, and regulatory portals per country.

CREATE TABLE IF NOT EXISTS country_official_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code VARCHAR(2) NOT NULL,
    portal_name TEXT NOT NULL,
    portal_url TEXT NOT NULL,
    portal_type TEXT NOT NULL, -- 'procurement_portal', 'building_code', 'legal_gazette', 'tax_authority', 'qualification_board'
    reference_law TEXT,
    last_checked_at TIMESTAMPTZ,
    last_known_hash TEXT,
    last_summary TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_country_official_sources_code ON country_official_sources (country_code);
CREATE INDEX IF NOT EXISTS idx_country_official_sources_type ON country_official_sources (portal_type);

-- RLS Configuration
ALTER TABLE country_official_sources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "country_official_sources_read_all" ON country_official_sources;
CREATE POLICY "country_official_sources_read_all"
    ON country_official_sources FOR SELECT
    TO authenticated, anon, service_role, btp_app_user
    USING (true);

DROP POLICY IF EXISTS "country_official_sources_superadmin_write" ON country_official_sources;
CREATE POLICY "country_official_sources_superadmin_write"
    ON country_official_sources FOR ALL
    TO authenticated, service_role, btp_app_user
    USING (is_superadmin());

GRANT ALL ON country_official_sources TO btp_app_user;
GRANT ALL ON country_official_sources TO service_role;
