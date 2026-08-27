-- ==============================================================================
-- 00023_platform_admin_config_and_trigger_cleanup.sql
-- Externalisation du magic string platform_admin (charbelakl@gmail.com)
-- vers une table de configuration dédiée.
-- Unification définitive du trigger handle_new_user_signup.
-- ==============================================================================

-- 1. Table de configuration des administrateurs plateforme SaaS
CREATE TABLE IF NOT EXISTS public.platform_admins (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT NOT NULL UNIQUE,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    added_by    TEXT,
    notes       TEXT
);

-- Seed de l'admin initial (remplace le magic string hard-codé dans le trigger)
INSERT INTO public.platform_admins (email, notes)
VALUES ('charbelakl@gmail.com', 'Fondateur btpAO — accès Platform Admin SaaS')
ON CONFLICT (email) DO NOTHING;

-- RLS : seul le service role peut lire/modifier cette table
ALTER TABLE public.platform_admins ENABLE ROW LEVEL SECURITY;
CREATE POLICY "platform_admins_service_only" ON public.platform_admins
    FOR ALL USING (false); -- Bloque tous les accès client-side ; accès via SECURITY DEFINER uniquement


-- 2. Remplacement définitif du trigger handle_new_user_signup
--    (unifie 00011 / 00015 / 00016 en une version propre et sans magic string)
CREATE OR REPLACE FUNCTION public.handle_new_user_signup()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    new_tenant_id       UUID;
    v_invited_tenant_id UUID;
    v_invited_role      TEXT;
    v_company_name      TEXT;
    v_full_name         TEXT;
    v_role              TEXT;
    v_plan              TEXT;
    v_slug              TEXT;
    v_siret             TEXT;
    v_country_code      TEXT;
    v_is_platform_admin BOOLEAN := FALSE;
BEGIN
    -- Récupération et normalisation des métadonnées envoyées par supabase.auth.signUp()
    v_company_name := COALESCE(
        NULLIF(NEW.raw_user_meta_data->>'company_name', ''),
        split_part(NEW.email, '@', 1) || ' Entreprise BTP'
    );
    v_full_name    := COALESCE(NULLIF(NEW.raw_user_meta_data->>'full_name', ''), split_part(NEW.email, '@', 1));
    v_plan         := COALESCE(NULLIF(NEW.raw_user_meta_data->>'plan', ''), 'pro');
    v_siret        := NULLIF(NEW.raw_user_meta_data->>'siret', '');
    v_country_code := COALESCE(NULLIF(NEW.raw_user_meta_data->>'country_code', ''), 'FR');

    -- Vérification si l'email est un admin plateforme (via table, plus de magic string)
    SELECT EXISTS(
        SELECT 1 FROM public.platform_admins WHERE lower(email) = lower(NEW.email)
    ) INTO v_is_platform_admin;

    -- CAS A : Platform Admin SaaS
    IF v_is_platform_admin THEN
        v_role         := 'platform_admin';
        new_tenant_id  := NULL;
        v_company_name := 'btpAO Plateforme SaaS';

    -- CAS B : Utilisateur invité — invitation active détectée
    ELSIF EXISTS (
        SELECT 1 FROM public.tenant_invitations
        WHERE lower(email) = lower(NEW.email)
          AND status IN ('pending', 'accepted')
    ) THEN
        SELECT tenant_id, role
        INTO v_invited_tenant_id, v_invited_role
        FROM public.tenant_invitations
        WHERE lower(email) = lower(NEW.email) AND status IN ('pending', 'accepted')
        ORDER BY created_at DESC
        LIMIT 1;

        new_tenant_id  := v_invited_tenant_id;
        v_role         := COALESCE(v_invited_role, 'member');
        SELECT name INTO v_company_name FROM public.tenants WHERE id = new_tenant_id;

        -- Marquer l'invitation comme acceptée
        UPDATE public.tenant_invitations
        SET status = 'accepted', updated_at = NOW()
        WHERE lower(email) = lower(NEW.email) AND status = 'pending';

    -- CAS C : Tenant_id explicitement fourni dans les métadonnées
    ELSIF NEW.raw_user_meta_data->>'tenant_id' IS NOT NULL THEN
        new_tenant_id := (NEW.raw_user_meta_data->>'tenant_id')::UUID;
        v_role        := COALESCE(NULLIF(NEW.raw_user_meta_data->>'role', ''), 'member');
        SELECT name INTO v_company_name FROM public.tenants WHERE id = new_tenant_id;

    -- CAS D : Nouveau client — création du tenant (Tenant Owner)
    ELSE
        v_role := 'owner';

        -- Slug unique
        v_slug := lower(regexp_replace(v_company_name, '[^a-zA-Z0-9]+', '-', 'g'))
               || '-' || substr(replace(NEW.id::text, '-', ''), 1, 6);

        -- Création du tenant
        INSERT INTO public.tenants (
            name, slug, plan, country_code, siret, contact_email,
            branding_config, created_at, updated_at
        )
        VALUES (
            v_company_name, v_slug, v_plan, v_country_code, v_siret, NEW.email,
            jsonb_build_object(
                'company_name',    v_company_name,
                'siret',           v_siret,
                'contact_email',   NEW.email,
                'primary_color',   '#0284c7',
                'secondary_color', '#0f172a',
                'font_family',     'Inter',
                'header_text',     v_company_name || ' — Mémoire Technique',
                'footer_text',     'Document confidentiel — Réponse Appel d''Offres'
            ),
            NOW(), NOW()
        )
        RETURNING id INTO new_tenant_id;

        -- Abonnement initial (essai gratuit 30 jours)
        IF EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'tenant_subscriptions'
        ) THEN
            INSERT INTO public.tenant_subscriptions (
                tenant_id, plan_id, status, billing_mode,
                custom_quota_dossiers, allow_overage,
                current_period_start, current_period_end, created_at, updated_at
            )
            VALUES (
                new_tenant_id, v_plan, 'active', 'free_trial',
                CASE WHEN v_plan = 'enterprise' THEN 50 WHEN v_plan = 'pro' THEN 15 ELSE 3 END,
                true,
                NOW(), NOW() + INTERVAL '30 days',
                NOW(), NOW()
            )
            ON CONFLICT (tenant_id) DO NOTHING;
        END IF;
    END IF;

    -- Création / Mise à jour de la fiche utilisateur dans public.users
    IF new_tenant_id IS NOT NULL THEN
        INSERT INTO public.users (
            id, tenant_id, email, full_name, role, status, created_at, updated_at
        )
        VALUES (
            NEW.id, new_tenant_id, NEW.email, v_full_name, v_role, 'active', NOW(), NOW()
        )
        ON CONFLICT (id) DO UPDATE
            SET tenant_id  = EXCLUDED.tenant_id,
                email      = EXCLUDED.email,
                full_name  = EXCLUDED.full_name,
                role       = EXCLUDED.role,
                status     = 'active',
                updated_at = NOW();
    END IF;

    -- Injection des JWT claims sécurisés dans raw_app_meta_data
    UPDATE auth.users
    SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) ||
        jsonb_build_object(
            'tenant_id',       CASE WHEN new_tenant_id IS NOT NULL THEN new_tenant_id::text ELSE NULL END,
            'role',            v_role,
            'is_platform_admin', v_is_platform_admin,
            'company_name',    v_company_name
        )
    WHERE id = NEW.id;

    RETURN NEW;
END;
$$;

-- 3. S'assurer que le trigger est bien attaché (idempotent)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user_signup();
