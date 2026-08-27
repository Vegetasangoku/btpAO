-- Migration 00020: Phase B & Phase C - Prefill Metadata & Tenant Learnings Expansion

-- 1. Add prefill tracking columns to generated_sections
ALTER TABLE public.generated_sections 
    ADD COLUMN IF NOT EXISTS prefill_source JSONB DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS is_prefilled BOOLEAN DEFAULT false;

-- 2. Expand tenant_learnings table columns for continuous consent-based learning
ALTER TABLE public.tenant_learnings 
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES public.projects(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'general',
    ADD COLUMN IF NOT EXISTS title TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS learning_insight TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS actionable_directive TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS source_outcome TEXT NOT NULL DEFAULT 'lost',
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS section_type TEXT,
    ADD COLUMN IF NOT EXISTS learned_content TEXT,
    ADD COLUMN IF NOT EXISTS source_diff JSONB DEFAULT '{}'::jsonb;

-- 3. Ensure clean standard RLS isolation policies on tenant_learnings
DROP POLICY IF EXISTS tenant_isolation_tenant_learnings ON public.tenant_learnings;
DROP POLICY IF EXISTS tenant_learnings_superadmin_all ON public.tenant_learnings;

CREATE POLICY tenant_isolation_tenant_learnings ON public.tenant_learnings
    FOR ALL 
    USING (tenant_id = current_tenant_id() OR auth.role() = 'service_role')
    WITH CHECK (tenant_id = current_tenant_id() OR auth.role() = 'service_role');

CREATE POLICY tenant_learnings_superadmin_all ON public.tenant_learnings
    FOR ALL 
    USING (is_superadmin())
    WITH CHECK (is_superadmin());
