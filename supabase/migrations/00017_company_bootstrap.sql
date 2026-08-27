-- ─────────────────────────────────────────────────────────────────────────────
--  btpAO — Migration 00017: Company Profile Auto-Bootstrap & Reference URLs
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Table des runs d'auto-bootstrap d'entreprise
CREATE TABLE IF NOT EXISTS public.company_bootstrap_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    triggered_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    sources_found JSONB DEFAULT '[]'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Ajout des colonnes de source et validation sur company_assets
ALTER TABLE public.company_assets 
    ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'manual_upload',
    ADD COLUMN IF NOT EXISTS collected_at TIMESTAMPTZ DEFAULT now(),
    ADD COLUMN IF NOT EXISTS validated_by_user BOOLEAN DEFAULT TRUE;

-- Marquer les assets existants créés manuellement comme validés
UPDATE public.company_assets 
SET validated_by_user = TRUE, source_type = 'manual_upload' 
WHERE validated_by_user IS NULL OR source_type IS NULL;

-- 3. Table des URLs de confiance / référence fournies par le client
CREATE TABLE IF NOT EXISTS public.tenant_reference_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    label TEXT,
    added_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_fetched_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'active' -- 'active', 'broken', 'fetching'
);

-- 4. Activation et application des politiques RLS
ALTER TABLE public.company_bootstrap_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_company_bootstrap_runs" ON public.company_bootstrap_runs;
CREATE POLICY "tenant_isolation_company_bootstrap_runs" ON public.company_bootstrap_runs
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

ALTER TABLE public.tenant_reference_urls ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_tenant_reference_urls" ON public.tenant_reference_urls;
CREATE POLICY "tenant_isolation_tenant_reference_urls" ON public.tenant_reference_urls
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- Index pour la performance des requêtes tenant-scoped
CREATE INDEX IF NOT EXISTS idx_company_bootstrap_runs_tenant ON public.company_bootstrap_runs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_reference_urls_tenant ON public.tenant_reference_urls(tenant_id);
CREATE INDEX IF NOT EXISTS idx_company_assets_validated ON public.company_assets(tenant_id, validated_by_user);

-- Droits d'accès
GRANT ALL ON public.company_bootstrap_runs TO postgres, authenticated, anon, service_role, btp_app_user;
GRANT ALL ON public.tenant_reference_urls TO postgres, authenticated, anon, service_role, btp_app_user;


