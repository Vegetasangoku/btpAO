-- ==============================================================================
-- 00011_fix_auth_signup_trigger_and_default_owner_role.sql
-- Correction définitive du trigger Supabase Auth d'inscription
-- Rôle 'owner' par défaut pour les créateurs de tenant + Sync App Metadata
-- ==============================================================================

-- 0. Schema auth si non existant (environnements locaux)
CREATE SCHEMA IF NOT EXISTS auth;

-- 1. Colonne country_code, siret, contact_email sur tenants si non existantes
ALTER TABLE public.tenants 
    ADD COLUMN IF NOT EXISTS country_code VARCHAR(2) NOT NULL DEFAULT 'FR';
ALTER TABLE public.tenants 
    ADD COLUMN IF NOT EXISTS siret TEXT;
ALTER TABLE public.tenants 
    ADD COLUMN IF NOT EXISTS contact_email TEXT;



-- 2. Mise à jour de la contrainte check_user_role sur public.users
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS check_user_role;
ALTER TABLE public.users ADD CONSTRAINT check_user_role 
    CHECK (role IN ('owner', 'member', 'read_only', 'conducteur_travaux', 'chiffreur', 'admin', 'platform_admin', 'super_admin'));

-- 3. Fonction Trigger robuste pour la création automatique du tenant & user
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
    v_siret TEXT;
    v_country_code TEXT;
BEGIN
    -- Récupération et normalisation des métadonnées envoyées par supabase.auth.signUp()
    v_company_name := COALESCE(NULLIF(NEW.raw_user_meta_data->>'company_name', ''), split_part(NEW.email, '@', 1) || ' Entreprise BTP');
    v_full_name := COALESCE(NULLIF(NEW.raw_user_meta_data->>'full_name', ''), split_part(NEW.email, '@', 1));
    v_plan := COALESCE(NULLIF(NEW.raw_user_meta_data->>'plan', ''), 'starter');
    v_siret := NULLIF(NEW.raw_user_meta_data->>'siret', '');
    v_country_code := COALESCE(NULLIF(NEW.raw_user_meta_data->>'country_code', ''), 'FR');

    -- Attribution du rôle : les nouveaux créateurs de tenant sont toujours 'owner' (pas 'admin')
    v_role := COALESCE(NULLIF(NEW.raw_user_meta_data->>'role', ''), 'owner');
    IF v_role = 'admin' THEN
        v_role := 'owner';
    END IF;

    -- Cas 1 : Utilisateur invité rattaché à un tenant existant
    IF NEW.raw_user_meta_data->>'tenant_id' IS NOT NULL THEN
        new_tenant_id := (NEW.raw_user_meta_data->>'tenant_id')::UUID;
        v_role := COALESCE(NULLIF(NEW.raw_user_meta_data->>'role', ''), 'member');
        SELECT name INTO v_company_name FROM public.tenants WHERE id = new_tenant_id;
    
    -- Cas 2 : Super Administrateur SaaS
    ELSIF NEW.email = 'charbelakl@gmail.com' THEN
        v_role := 'platform_admin';
        new_tenant_id := NULL;
        v_company_name := 'btpAO Plateforme SaaS';

    -- Cas 3 : Nouveau client créant sa propre entreprise (Tenant Owner)
    ELSE
        v_role := 'owner';
        -- Génération d'un slug unique
        v_slug := lower(regexp_replace(v_company_name, '[^a-zA-Z0-9]+', '-', 'g')) || '-' || substr(replace(NEW.id::text, '-', ''), 1, 6);

        -- Création du tenant dans public.tenants avec schéma à jour
        INSERT INTO public.tenants (
            name,
            slug,
            plan,
            country_code,
            siret,
            contact_email,
            branding_config,
            created_at,
            updated_at
        )
        VALUES (
            v_company_name,
            v_slug,
            v_plan,
            v_country_code,
            v_siret,
            NEW.email,
            jsonb_build_object(
                'company_name', v_company_name,
                'siret', v_siret,
                'contact_email', NEW.email,
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

        -- Création de l'abonnement initial si la table existe
        IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'tenant_subscriptions') THEN
            INSERT INTO public.tenant_subscriptions (
                tenant_id,
                plan_id,
                status,
                billing_mode,
                custom_quota_dossiers,
                allow_overage,
                current_period_start,
                current_period_end,
                created_at,
                updated_at
            )
            VALUES (
                new_tenant_id,
                v_plan,
                'active',
                'free_trial',
                CASE WHEN v_plan = 'enterprise' THEN 50 WHEN v_plan = 'pro' THEN 15 ELSE 3 END,
                true,
                NOW(),
                NOW() + INTERVAL '30 days',
                NOW(),
                NOW()
            )
            ON CONFLICT (tenant_id) DO NOTHING;
        END IF;
    END IF;

    -- Création / Mise à jour de la fiche utilisateur dans public.users
    IF new_tenant_id IS NOT NULL THEN
        INSERT INTO public.users (
            id,
            tenant_id,
            email,
            full_name,
            role,
            created_at,
            updated_at
        )
        VALUES (
            NEW.id,
            new_tenant_id,
            NEW.email,
            v_full_name,
            v_role,
            NOW(),
            NOW()
        )
        ON CONFLICT (id) DO UPDATE
        SET tenant_id = EXCLUDED.tenant_id,
            email = EXCLUDED.email,
            full_name = EXCLUDED.full_name,
            role = EXCLUDED.role,
            updated_at = NOW();
    END IF;

    -- Injection des claims sécurisés (tenant_id, role, company_name) dans raw_app_meta_data
    UPDATE auth.users
    SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) || 
        jsonb_build_object(
            'tenant_id', CASE WHEN new_tenant_id IS NOT NULL THEN new_tenant_id::text ELSE NULL END,
            'role', v_role,
            'is_platform_admin', (v_role = 'platform_admin' OR v_role = 'super_admin'),
            'company_name', v_company_name
        )
    WHERE id = NEW.id;

    RETURN NEW;
END;
$$;

-- 4. Nettoyage des anciens triggers et rattachement exclusif du nouveau trigger
DROP TRIGGER IF EXISTS on_auth_user_created_master ON auth.users;
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS public.handle_user_signup_master();

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user_signup();
