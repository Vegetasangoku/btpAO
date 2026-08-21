-- ==============================================================================
-- 00012_password_reset_tokens.sql
-- Table et index pour la réinitialisation sécurisée des mots de passe
-- Tokens cryptographiques à usage unique avec expiration & fonction SECURITY DEFINER
-- ==============================================================================

-- 1. Table des tokens de réinitialisation
CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Index pour les lookups ultra-rapides de tokens et emails
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_hash ON public.password_reset_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_email ON public.password_reset_tokens(email, expires_at);

-- 3. Permissions et RLS
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'btp_app_user') THEN
        GRANT ALL ON TABLE public.password_reset_tokens TO btp_app_user;
        GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;
    END IF;
END
$$;

ALTER TABLE public.password_reset_tokens ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS service_password_reset_policy ON public.password_reset_tokens;
CREATE POLICY service_password_reset_policy ON public.password_reset_tokens
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- 4. Fonction SECURITY DEFINER pour appliquer la réinitialisation de mot de passe en toute sécurité
CREATE OR REPLACE FUNCTION public.apply_password_reset(
    p_token_hash TEXT,
    p_new_password_hash TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_user_id UUID;
    v_email TEXT;
BEGIN
    -- 1. Vérification du token actif, non expiré et non encore utilisé
    SELECT user_id, email INTO v_user_id, v_email
    FROM public.password_reset_tokens
    WHERE token_hash = p_token_hash
      AND used_at IS NULL
      AND expires_at > now();

    IF NOT FOUND THEN
        RETURN false;
    END IF;

    -- 2. Mise à jour du mot de passe chiffré dans auth.users
    UPDATE auth.users
    SET encrypted_password = p_new_password_hash,
        updated_at = now()
    WHERE id = v_user_id OR lower(email) = lower(v_email);

    -- 3. Invalidation immédiate du token (anti-rejeu)
    UPDATE public.password_reset_tokens
    SET used_at = now()
    WHERE token_hash = p_token_hash;

    RETURN true;
END;
$$;

GRANT EXECUTE ON FUNCTION public.apply_password_reset(TEXT, TEXT) TO PUBLIC;
