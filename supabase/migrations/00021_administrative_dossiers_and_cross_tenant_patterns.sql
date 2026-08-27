-- Migration 00021: Cross-Tenant Anonymized Structural Patterns & Regulatory Profiles Expansion

-- 1. Create global anonymized structural patterns table (cross-tenant, zero PII)
CREATE TABLE IF NOT EXISTS public.dce_structural_patterns_global (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_sector TEXT NOT NULL DEFAULT 'btp_general',
    detected_section_key TEXT NOT NULL,
    typical_title TEXT NOT NULL,
    frequency_score INTEGER NOT NULL DEFAULT 1,
    typical_subsections JSONB DEFAULT '[]'::jsonb,
    is_public_learning BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS: Read-only for all authenticated tenants, write for service_role/superadmin
ALTER TABLE public.dce_structural_patterns_global ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS dce_patterns_global_read ON public.dce_structural_patterns_global;
CREATE POLICY dce_patterns_global_read ON public.dce_structural_patterns_global
    FOR SELECT 
    USING (true);

DROP POLICY IF EXISTS dce_patterns_global_write ON public.dce_structural_patterns_global;
CREATE POLICY dce_patterns_global_write ON public.dce_structural_patterns_global
    FOR ALL 
    USING (auth.role() = 'service_role' OR is_superadmin())
    WITH CHECK (auth.role() = 'service_role' OR is_superadmin());

GRANT SELECT ON TABLE public.dce_structural_patterns_global TO btp_app_user;
