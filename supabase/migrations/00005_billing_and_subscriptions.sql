-- ==============================================================================
-- 00005_billing_and_subscriptions.sql
-- Module Facturation Hybride B2B : Plans, Abonnements et Compteurs de Quota
-- ==============================================================================

-- 1. Table des Forfaits & Plans
CREATE TABLE IF NOT EXISTS public.subscription_plans (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price_monthly_cents INTEGER NOT NULL DEFAULT 0,
    included_dossiers_month INTEGER NOT NULL DEFAULT 3,
    extra_dossier_price_cents INTEGER NOT NULL DEFAULT 9900,
    features JSONB DEFAULT '[]'::jsonb,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed des forfaits officiels
INSERT INTO public.subscription_plans (id, name, price_monthly_cents, included_dossiers_month, extra_dossier_price_cents, features)
VALUES 
('starter', 'Forfait PME & Artisan', 19900, 3, 9900, '["Générateur IA & RAG", "Extraction DCE", "Export Word .docx"]'::jsonb),
('pro', 'Forfait Entreprise Générale', 49900, 10, 7900, '["Tout Starter", "Organigrammes & Gantt", "Base connaissances illimitée", "Support dédié"]'::jsonb),
('enterprise', 'Grand Compte / Sur Devis', 0, 50, 0, '["Volume sur-mesure", "Facturation personnalisée", "Modèles IA dédiés", "SLA garanti"]'::jsonb)
ON CONFLICT (id) DO UPDATE SET 
    price_monthly_cents = EXCLUDED.price_monthly_cents,
    included_dossiers_month = EXCLUDED.included_dossiers_month,
    extra_dossier_price_cents = EXCLUDED.extra_dossier_price_cents,
    features = EXCLUDED.features;

-- 2. Table des Abonnements par Tenant
CREATE TABLE IF NOT EXISTS public.tenant_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE UNIQUE,
    plan_id TEXT NOT NULL REFERENCES public.subscription_plans(id),
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'past_due', 'canceled', 'suspended'
    billing_mode TEXT NOT NULL DEFAULT 'stripe', -- 'stripe', 'manual_enterprise', 'free_trial'
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    custom_quota_dossiers INTEGER,
    allow_overage BOOLEAN DEFAULT true,
    current_period_start TIMESTAMPTZ NOT NULL DEFAULT now(),
    current_period_end TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '1 month'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Table des Compteurs de Consommation Mensuelle par Tenant
CREATE TABLE IF NOT EXISTS public.tenant_usage_counters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    dossiers_generated INTEGER DEFAULT 0,
    sections_generated INTEGER DEFAULT 0,
    exports_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_tenant_usage_period UNIQUE(tenant_id, period_start)
);

-- 4. Permissions pour le rôle applicatif
GRANT USAGE ON SCHEMA public TO btp_app_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO btp_app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;

-- 5. Row Level Security (RLS) STRICT : ZÉRO visibilité par défaut si app.current_tenant_id est vide
ALTER TABLE public.subscription_plans ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_read_plans ON public.subscription_plans;
CREATE POLICY tenant_read_plans ON public.subscription_plans
    FOR SELECT TO btp_app_user
    USING (true);

ALTER TABLE public.tenant_subscriptions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_tenant_subscriptions ON public.tenant_subscriptions;
CREATE POLICY tenant_isolation_tenant_subscriptions ON public.tenant_subscriptions
    FOR ALL TO btp_app_user
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
        OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
        OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
    );

ALTER TABLE public.tenant_usage_counters ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_tenant_usage_counters ON public.tenant_usage_counters;
CREATE POLICY tenant_isolation_tenant_usage_counters ON public.tenant_usage_counters
    FOR ALL TO btp_app_user
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
        OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
        OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::UUID
    );
