-- =============================================================================
-- Migration 00006: Version History & Audit Trail for Generated Memo Sections
-- Standard Multi-Tenant PostgreSQL RLS (Strict tenant isolation)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.generated_section_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    section_id UUID NOT NULL REFERENCES public.generated_sections(id) ON DELETE CASCADE,
    version_number INT NOT NULL DEFAULT 1,
    title TEXT NOT NULL,
    content_html TEXT NOT NULL,
    content_json JSONB DEFAULT '{}'::jsonb,
    compliance_score NUMERIC(4, 1) DEFAULT 100.0,
    compliance_notes TEXT,
    status TEXT NOT NULL DEFAULT 'edited',
    created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    change_summary TEXT DEFAULT 'Modification éditeur'
);

-- Performance and query indexes
CREATE INDEX IF NOT EXISTS idx_section_versions_section_id ON public.generated_section_versions(section_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_section_versions_tenant_id ON public.generated_section_versions(tenant_id, section_id);

-- Permissions
GRANT ALL ON TABLE public.generated_section_versions TO btp_app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;

-- Enable Row Level Security
ALTER TABLE public.generated_section_versions ENABLE ROW LEVEL SECURITY;

-- Strict Multi-Tenant Isolation Policy (No fallback: requires explicit tenant context)
DROP POLICY IF EXISTS tenant_isolation_generated_section_versions ON public.generated_section_versions;
CREATE POLICY tenant_isolation_generated_section_versions ON public.generated_section_versions
    FOR ALL
    TO btp_app_user
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
    );
