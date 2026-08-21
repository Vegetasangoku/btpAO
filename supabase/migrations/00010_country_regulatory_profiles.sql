-- =============================================================================
-- Migration 00010: Extensible Multi-Country Regulatory Profiles
-- Default: France (FR) - Active
-- Zero hardcoded country norms in business logic
-- =============================================================================

-- 1. Add country_code to tenants table (ISO 3166-1 alpha-2)
ALTER TABLE public.tenants 
    ADD COLUMN IF NOT EXISTS country_code VARCHAR(2) NOT NULL DEFAULT 'FR';

-- 2. Reference Table: country_regulatory_profiles
CREATE TABLE IF NOT EXISTS public.country_regulatory_profiles (
    country_code VARCHAR(2) PRIMARY KEY,
    country_name TEXT NOT NULL,
    technical_standards_reference TEXT NOT NULL,
    environmental_regulation TEXT NOT NULL,
    public_procurement_regime TEXT NOT NULL,
    recognized_qualifications JSONB NOT NULL DEFAULT '["QUALIBAT", "FNTP", "QUALIFELEC"]'::jsonb,
    waste_tracking_regime TEXT NOT NULL,
    safety_plan_regime TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Permissions
GRANT SELECT ON TABLE public.country_regulatory_profiles TO btp_app_user;

-- Enable RLS (Read-only policy for application users)
ALTER TABLE public.country_regulatory_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS read_country_regulatory_profiles ON public.country_regulatory_profiles;
CREATE POLICY read_country_regulatory_profiles ON public.country_regulatory_profiles
    FOR SELECT
    TO btp_app_user
    USING (is_active = true);

-- 3. Seed France (FR) as the single currently active regulatory profile
INSERT INTO public.country_regulatory_profiles (
    country_code,
    country_name,
    technical_standards_reference,
    environmental_regulation,
    public_procurement_regime,
    recognized_qualifications,
    waste_tracking_regime,
    safety_plan_regime,
    is_active
) VALUES (
    'FR',
    'France',
    'DTU / Eurocodes / Normes NF BTP',
    'RE2020 / FDES / Base INIES',
    'Code de la Commande Publique & CCAG Travaux',
    '["QUALIBAT", "FNTP", "QUALIFELEC", "OPQIBI"]'::jsonb,
    'Trackdéchets / BSD dématérialisé (Bordereau de Suivi des Déchets)',
    'PPSPS (Plan Particulier de Sécurité et de Protection de la Santé) & PAQ',
    true
)
ON CONFLICT (country_code) DO UPDATE SET
    technical_standards_reference = EXCLUDED.technical_standards_reference,
    environmental_regulation = EXCLUDED.environmental_regulation,
    public_procurement_regime = EXCLUDED.public_procurement_regime,
    recognized_qualifications = EXCLUDED.recognized_qualifications,
    waste_tracking_regime = EXCLUDED.waste_tracking_regime,
    safety_plan_regime = EXCLUDED.safety_plan_regime,
    is_active = EXCLUDED.is_active,
    updated_at = now();
