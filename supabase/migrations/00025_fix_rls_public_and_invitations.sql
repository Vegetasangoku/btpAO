-- Migration 00025: Fix RLS Policies for Country Regulatory Profiles, Platform Settings, Tenant Invitations & Project Go/No-Go Analyses

-- 1. Table project_go_no_go_analyses
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

CREATE INDEX IF NOT EXISTS idx_go_no_go_project_id ON public.project_go_no_go_analyses(project_id);
CREATE INDEX IF NOT EXISTS idx_go_no_go_tenant_id ON public.project_go_no_go_analyses(tenant_id);

GRANT ALL ON TABLE public.project_go_no_go_analyses TO btp_app_user;
GRANT ALL ON TABLE public.project_go_no_go_analyses TO authenticated;
GRANT ALL ON TABLE public.project_go_no_go_analyses TO service_role;

ALTER TABLE public.project_go_no_go_analyses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_project_go_no_go ON public.project_go_no_go_analyses;
CREATE POLICY tenant_isolation_project_go_no_go ON public.project_go_no_go_analyses
    FOR ALL
    TO authenticated, btp_app_user, service_role
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
        OR tenant_id = current_tenant_id()
        OR auth.role() = 'service_role'
        OR is_superadmin()
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
        OR tenant_id = current_tenant_id()
        OR auth.role() = 'service_role'
        OR is_superadmin()
    );

DROP POLICY IF EXISTS project_go_no_go_superadmin_all ON public.project_go_no_go_analyses;
CREATE POLICY project_go_no_go_superadmin_all ON public.project_go_no_go_analyses
    FOR ALL
    USING (is_superadmin())
    WITH CHECK (is_superadmin());

-- 2. Country Regulatory Profiles RLS & Grants
GRANT SELECT ON public.country_regulatory_profiles TO btp_app_user;
GRANT ALL ON public.country_regulatory_profiles TO service_role;

DROP POLICY IF EXISTS read_country_regulatory_profiles ON public.country_regulatory_profiles;
CREATE POLICY read_country_regulatory_profiles ON public.country_regulatory_profiles
    FOR SELECT
    TO authenticated, anon, service_role, btp_app_user
    USING (is_active = true);

DROP POLICY IF EXISTS write_country_regulatory_profiles ON public.country_regulatory_profiles;
CREATE POLICY write_country_regulatory_profiles ON public.country_regulatory_profiles
    FOR ALL
    TO authenticated, service_role, btp_app_user
    USING (is_superadmin());

-- 3. Tenant Invitations RLS
DROP POLICY IF EXISTS tenant_isolation_tenant_invitations ON public.tenant_invitations;
CREATE POLICY tenant_isolation_tenant_invitations ON public.tenant_invitations
    FOR ALL
    TO authenticated, service_role, btp_app_user
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
        OR (status = 'pending')
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
    );

-- 4. Platform Settings RLS
DROP POLICY IF EXISTS platform_settings_read ON public.platform_settings;
CREATE POLICY platform_settings_read ON public.platform_settings
    FOR SELECT
    TO authenticated, anon, service_role, btp_app_user
    USING (true);

DROP POLICY IF EXISTS platform_settings_write ON public.platform_settings;
CREATE POLICY platform_settings_write ON public.platform_settings
    FOR ALL
    TO authenticated, service_role, btp_app_user
    USING (is_superadmin());
