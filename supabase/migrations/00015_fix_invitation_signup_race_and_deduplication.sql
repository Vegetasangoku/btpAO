-- ==============================================================================
-- 00015_fix_invitation_signup_race_and_deduplication.sql
-- Synchronisation bidirectionnelle invitations / trigger d'inscription Supabase Auth
-- Empêche la création d'un tenant en double lorsqu'un utilisateur invité s'inscrit
-- ==============================================================================

CREATE OR REPLACE FUNCTION public.handle_new_user_signup()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    new_tenant_id UUID;
    v_invited_tenant_id UUID;
    v_invited_role TEXT;
    v_company_name TEXT;
    v_full_name TEXT;
    v_role TEXT;
    v_plan TEXT;
    v_slug TEXT;
    v_siret TEXT;
    v_country_code TEXT;
BEGIN
    -- 1. Récupération et normalisation des métadonnées
    v_company_name := COALESCE(NULLIF(NEW.raw_user_meta_data->>'company_name', ''), split_part(NEW.email, '@', 1) || ' Entreprise BTP');
    v_full_name := COALESCE(NULLIF(NEW.raw_user_meta_data->>'full_name', ''), split_part(NEW.email, '@', 1));
    v_plan := COALESCE(NULLIF(NEW.raw_user_meta_data->>'plan', ''), 'starter');
    v_siret := NULLIF(NEW.raw_user_meta_data->>'siret', '');
    v_country_code := COALESCE(NULLIF(NEW.raw_user_meta_data->>'country_code', ''), 'FR');

    -- 2. Cas 0 : Vérifier si l'utilisateur a une invitation active pour cet email (évite collision/doublon de tenant)
    SELECT tenant_id, role INTO v_invited_tenant_id, v_invited_role
    FROM public.tenant_invitations
    WHERE lower(email) = lower(NEW.email) AND status IN ('pending', 'accepted')
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_invited_tenant_id IS NOT NULL THEN
        new_tenant_id := v_invited_tenant_id;
        v_role := COALESCE(v_invited_role, 'member');
        SELECT name INTO v_company_name FROM public.tenants WHERE id = new_tenant_id;

        -- Marquer l'invitation comme acceptée si elle était en attente
        UPDATE public.tenant_invitations
        SET status = 'accepted', updated_at = NOW()
        WHERE lower(email) = lower(NEW.email) AND status = 'pending';

    -- Cas 1 : Utilisateur avec tenant_id explicitement passé en métadonnées
    ELSIF NEW.raw_user_meta_data->>'tenant_id' IS NOT NULL THEN
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
        v_role := COALESCE(NULLIF(NEW.raw_user_meta_data->>'role', ''), 'owner');
        IF v_role = 'admin' THEN
            v_role := 'owner';
        END IF;

        -- Génération d'un slug unique
        v_slug := lower(regexp_replace(v_company_name, '[^a-zA-Z0-9]+', '-', 'g')) || '-' || substr(replace(NEW.id::text, '-', ''), 1, 6);

        -- Création du tenant dans public.tenants
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

        -- Création de l'abonnement initial
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
