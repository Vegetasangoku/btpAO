-- ==============================================================================
-- 00004_superadmin_seed_and_rbac.sql
-- Configuration du compte Super Admin et Politiques RBAC
-- ==============================================================================

-- 1. Inscription ou mise à jour du Super Admin charbelakl@gmail.com
DO $$
DECLARE
    superadmin_uid UUID;
    system_tenant_id UUID;
BEGIN
    -- Vérification si le tenant système existe
    SELECT id INTO system_tenant_id FROM public.tenants WHERE slug = 'btpao-system' LIMIT 1;
    
    IF system_tenant_id IS NULL THEN
        INSERT INTO public.tenants (
            id,
            name,
            slug,
            plan,
            is_active,
            branding_config,
            created_at,
            updated_at
        ) VALUES (
            '00000000-0000-0000-0000-000000000000',
            'Plateforme btpAO (Administration)',
            'btpao-system',
            'enterprise',
            true,
            jsonb_build_object(
                'company_name', 'btpAO SaaS',
                'primary_color', '#0284c7'
            ),
            NOW(),
            NOW()
        )
        RETURNING id INTO system_tenant_id;
    END IF;

    -- Création / Mise à jour dans auth.users si possible
    SELECT id INTO superadmin_uid FROM auth.users WHERE email = 'charbelakl@gmail.com' LIMIT 1;

    IF superadmin_uid IS NOT NULL THEN
        -- Mise à jour du rôle en superadmin
        UPDATE auth.users
        SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) || 
            jsonb_build_object(
                'role', 'superadmin',
                'tenant_id', system_tenant_id::text,
                'company_name', 'btpAO SaaS'
            )
        WHERE id = superadmin_uid;

        -- Mise à jour dans public.users
        INSERT INTO public.users (
            id,
            tenant_id,
            email,
            full_name,
            role,
            is_active,
            created_at,
            updated_at
        ) VALUES (
            superadmin_uid,
            system_tenant_id,
            'charbelakl@gmail.com',
            'Charbel Akl (Super Admin)',
            'superadmin',
            true,
            NOW(),
            NOW()
        )
        ON CONFLICT (id) DO UPDATE
        SET role = 'superadmin',
            full_name = 'Charbel Akl (Super Admin)',
            tenant_id = system_tenant_id;
    END IF;
END $$;

-- 2. Fonction RPC pour vérifier si l'utilisateur courant est superadmin
CREATE OR REPLACE FUNCTION public.is_superadmin()
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
STABLE
AS $$
    SELECT COALESCE((auth.jwt() -> 'app_metadata' ->> 'role') = 'superadmin', false);
$$;

-- 3. Mise à jour des politiques RLS pour donner accès global au Super Admin
CREATE OR REPLACE FUNCTION public.apply_superadmin_rls()
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    tbl text;
BEGIN
    FOR tbl IN 
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN (
            'tenants', 'users', 'projects', 'dce_documents', 'dce_criteria', 
            'company_assets', 'generated_sections', 'export_jobs', 'tenant_ai_configs'
        )
    LOOP
        EXECUTE format('
            DROP POLICY IF EXISTS "%s_superadmin_all" ON public.%I;
            CREATE POLICY "%s_superadmin_all" ON public.%I
            FOR ALL
            USING (public.is_superadmin());
        ', tbl, tbl, tbl, tbl);
    END LOOP;
END $$;

SELECT public.apply_superadmin_rls();
