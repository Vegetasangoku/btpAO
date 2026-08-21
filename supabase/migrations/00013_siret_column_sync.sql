-- =============================================================================
-- Migration 00013: Synchronization and Consolidation of SIRET in tenants.siret
-- 1. Ensures column `siret VARCHAR(20)` exists on public.tenants
-- 2. Copies branding_config->>'siret' to tenants.siret wherever empty
-- 3. Removes 'siret' key from branding_config JSONB to eliminate dual source of truth
-- =============================================================================

ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS siret VARCHAR(20);

-- Migrate existing SIRET from branding_config to tenants.siret
UPDATE public.tenants
SET siret = branding_config->>'siret'
WHERE (siret IS NULL OR siret = '')
  AND branding_config ? 'siret'
  AND (branding_config->>'siret') IS NOT NULL
  AND (branding_config->>'siret') <> '';

-- Remove redundant 'siret' key from branding_config
UPDATE public.tenants
SET branding_config = branding_config - 'siret'
WHERE branding_config ? 'siret';

-- Add index on siret for fast company lookups
CREATE INDEX IF NOT EXISTS idx_tenants_siret ON public.tenants(siret);
