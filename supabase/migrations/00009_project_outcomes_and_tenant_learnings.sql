-- =============================================================================
-- Migration 00009: Project Outcomes, Buyer Feedback & Tenant Learnings Loop
-- Standard Multi-Tenant PostgreSQL RLS (Strict tenant isolation)
-- =============================================================================

-- 1. Add outcome and buyer feedback columns to public.projects
ALTER TABLE public.projects 
    ADD COLUMN IF NOT EXISTS outcome_status TEXT DEFAULT 'pending' 
    CHECK (outcome_status IN ('pending', 'won', 'lost', 'withdrawn', 'in_progress')),
    ADD COLUMN IF NOT EXISTS buyer_feedback JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS outcome_recorded_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS outcome_recorded_by UUID REFERENCES public.users(id) ON DELETE SET NULL;

-- 2. Tenant Continuous Learning Memory Table
CREATE TABLE IF NOT EXISTS public.tenant_learnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    project_id UUID REFERENCES public.projects(id) ON DELETE SET NULL,
    category TEXT NOT NULL DEFAULT 'general' CHECK (category IN ('methodology', 'planning', 'qse', 'safety', 'pricing', 'general')),
    title TEXT NOT NULL,
    learning_insight TEXT NOT NULL,
    actionable_directive TEXT NOT NULL,
    source_outcome TEXT NOT NULL DEFAULT 'lost' CHECK (source_outcome IN ('lost', 'won', 'manual', 'debrief')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Performance and query indexes
CREATE INDEX IF NOT EXISTS idx_tenant_learnings_tenant_id ON public.tenant_learnings(tenant_id, is_active);
CREATE INDEX IF NOT EXISTS idx_tenant_learnings_project_id ON public.tenant_learnings(project_id);
CREATE INDEX IF NOT EXISTS idx_projects_outcome ON public.projects(tenant_id, outcome_status);

-- Permissions
GRANT ALL ON TABLE public.tenant_learnings TO btp_app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;

-- Enable Row Level Security
ALTER TABLE public.tenant_learnings ENABLE ROW LEVEL SECURITY;

-- Strict Multi-Tenant Isolation Policy (No fallback: requires explicit tenant context)
DROP POLICY IF EXISTS tenant_isolation_tenant_learnings ON public.tenant_learnings;
CREATE POLICY tenant_isolation_tenant_learnings ON public.tenant_learnings
    FOR ALL
    TO btp_app_user
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
    );
