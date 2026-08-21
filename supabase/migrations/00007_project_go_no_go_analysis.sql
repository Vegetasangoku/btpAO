-- =============================================================================
-- Migration 00007: Go/No-Go Decision Matrix Analysis for Tenders
-- Standard Multi-Tenant PostgreSQL RLS (Strict tenant isolation)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.project_go_no_go_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    recommendation TEXT NOT NULL CHECK (recommendation IN ('GO', 'RESERVES', 'NO_GO')),
    score NUMERIC(5, 2) NOT NULL CHECK (score >= 0 AND score <= 100),
    summary TEXT NOT NULL,
    factors JSONB NOT NULL DEFAULT '[]'::jsonb,
    mandatory_criteria_met BOOLEAN NOT NULL DEFAULT true,
    blocking_issues JSONB NOT NULL DEFAULT '[]'::jsonb,
    evaluated_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_project_go_no_go UNIQUE (tenant_id, project_id)
);

-- Query and performance indexes
CREATE INDEX IF NOT EXISTS idx_go_no_go_project_id ON public.project_go_no_go_analyses(project_id);
CREATE INDEX IF NOT EXISTS idx_go_no_go_tenant_id ON public.project_go_no_go_analyses(tenant_id);

-- Permissions
GRANT ALL ON TABLE public.project_go_no_go_analyses TO btp_app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;

-- Enable Row Level Security
ALTER TABLE public.project_go_no_go_analyses ENABLE ROW LEVEL SECURITY;

-- Strict Multi-Tenant Isolation Policy (No fallback: requires explicit tenant context)
DROP POLICY IF EXISTS tenant_isolation_project_go_no_go ON public.project_go_no_go_analyses;
CREATE POLICY tenant_isolation_project_go_no_go ON public.project_go_no_go_analyses
    FOR ALL
    TO btp_app_user
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
    );
