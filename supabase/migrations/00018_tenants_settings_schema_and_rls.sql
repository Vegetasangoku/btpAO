-- ─────────────────────────────────────────────────────────────────────────────
--  btpAO — Migration 00018: Tenants Settings Schema & Multi-Tenant RLS Policy
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.tenants_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    custom_system_prompt TEXT,
    system_prompt_memory TEXT,
    taux_inflation_pct NUMERIC(5, 2) DEFAULT 3.5,
    marge_cible_pct NUMERIC(5, 2) DEFAULT 12.0,
    taux_horaires JSONB DEFAULT '{}'::jsonb,
    economic_settings JSONB DEFAULT '{}'::jsonb,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT now(),
    mis_a_jour_le TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_tenants_settings_tenant UNIQUE (tenant_id)
);

-- Activation du Row Level Security
ALTER TABLE public.tenants_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_tenants_settings" ON public.tenants_settings;
CREATE POLICY "tenant_isolation_tenants_settings" ON public.tenants_settings
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

CREATE INDEX IF NOT EXISTS idx_tenants_settings_tenant ON public.tenants_settings(tenant_id);

-- Droits d'accès
GRANT ALL ON public.tenants_settings TO postgres, authenticated, anon, service_role, btp_app_user;


