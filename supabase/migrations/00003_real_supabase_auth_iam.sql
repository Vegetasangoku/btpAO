-- ==============================================================================
-- 00003_real_supabase_auth_iam.sql
-- Intégration IAM Complète Supabase Auth -> public.users & public.tenants
-- Trigger automatique à l'inscription + Sync App Metadata dans le JWT
-- ==============================================================================

-- 1. Fonction Trigger appelée à la création d'un utilisateur Supabase Auth (auth.users)
CREATE OR REPLACE FUNCTION public.handle_new_user_signup()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    new_tenant_id UUID;
    v_company_name TEXT;
    v_full_name TEXT;
    v_role TEXT;
    v_plan TEXT;
    v_slug TEXT;
BEGIN
    -- Récupération des metadata passées lors du supabase.auth.signUp()
    v_company_name := COALESCE(NEW.raw_user_meta_data->>'company_name', split_part(NEW.email, '@', 1) || ' Entreprise BTP');
    v_full_name := COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1));
    v_role := COALESCE(NEW.raw_user_meta_data->>'role', 'admin');
    v_plan := COALESCE(NEW.raw_user_meta_data->>'plan', 'starter');
    
    -- Création d'un slug unique pour le tenant
    v_slug := lower(regexp_replace(v_company_name, '[^a-zA-Z0-9]+', '-', 'g')) || '-' || substr(NEW.id::text, 1, 6);

    -- 1. Création automatique de l'organisation Tenant pour ce nouvel inscrit
    INSERT INTO public.tenants (
        name,
        slug,
        plan,
        is_active,
        branding_config,
        created_at,
        updated_at
    )
    VALUES (
        v_company_name,
        v_slug,
        v_plan,
        true,
        jsonb_build_object(
            'company_name', v_company_name,
            'primary_color', '#0284c7',
            'secondary_color', '#0f172a',
            'font_family', 'Inter',
            'header_text', v_company_name || ' — Mémoire Technique',
            'footer_text', 'Document confidentiel — Réponse Appel d''Offres'
        ),
        NOW(),
        NOW()
    )
    RETURNING id INTO new_tenant_id;

    -- 2. Création de la fiche utilisateur dans public.users liée à auth.users.id
    INSERT INTO public.users (
        id,
        tenant_id,
        email,
        full_name,
        role,
        is_active,
        created_at,
        updated_at
    )
    VALUES (
        NEW.id,
        new_tenant_id,
        NEW.email,
        v_full_name,
        v_role,
        true,
        NOW(),
        NOW()
    );

    -- 3. Mise à jour de raw_app_meta_data dans auth.users pour injecter tenant_id & role dans le JWT
    UPDATE auth.users
    SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) || 
        jsonb_build_object(
            'tenant_id', new_tenant_id::text,
            'role', v_role,
            'company_name', v_company_name
        )
    WHERE id = NEW.id;

    RETURN NEW;
END;
$$;

-- 2. Association du trigger à auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user_signup();

-- 3. Configuration AI / OCR par tenant (pour paramétrer et tester l'OCR en direct)
CREATE TABLE IF NOT EXISTS public.tenant_ai_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    ocr_provider TEXT NOT NULL DEFAULT 'auto', -- 'azure_doc_intelligence', 'pdfplumber_local', 'auto'
    azure_endpoint TEXT,
    azure_api_key TEXT,
    llm_primary_provider TEXT NOT NULL DEFAULT 'claude-3-5-sonnet',
    anthropic_api_key TEXT,
    mistral_api_key TEXT,
    openai_api_key TEXT,
    custom_prompt_rules TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tenant_ai_config UNIQUE (tenant_id)
);

ALTER TABLE public.tenant_ai_configs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_ai_config_isolation"
    ON public.tenant_ai_configs
    FOR ALL
    USING (
        tenant_id::text = (auth.jwt() -> 'app_metadata' ->> 'tenant_id')
        OR tenant_id::text = current_setting('app.current_tenant_id', true)
        OR auth.role() = 'service_role'
    );
