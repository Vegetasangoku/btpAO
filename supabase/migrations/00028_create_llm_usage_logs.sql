-- ==============================================================================
-- 00028_create_llm_usage_logs.sql
-- Suivi de consommation LLM (tokens + cout estime) par appel reel, base pour un
-- plafond mensuel optionnel par fournisseur.
--
-- Contexte (30/08) : l'utilisateur a fait remarquer, a juste titre, qu'aucun
-- suivi de consommation ni aucune limite parametrable n'existait nulle part
-- dans le code malgre l'usage reel de LiteLLM (verifie par grep exhaustif sur
-- apps/api/app avant cette migration : 0 resultat pertinent, seuls des faux
-- positifs sur le budget euro du PROJET BTP client, sans rapport). Cette table
-- capture chaque appel LiteLLM reel (chemin principal ou repli resilient) avec
-- ses tokens et un cout estime (base sur les prix du catalogue
-- llm_catalog_models quand le modele y est reference). Voir
-- app/services/llm_generator.py (capture de response.usage sur les 2 chemins
-- d'appel) et app/workers/tasks.py (ecriture de la ligne + verification du
-- plafond mensuel avant resolution des identifiants) pour le cablage complet.
--
-- Appliquee en direct sur le projet le 30/08 (Claude, via
-- mcp__Supabase__apply_migration). Ce fichier existe pour que le correctif
-- soit suivi en controle de version et reproductible sur tout environnement
-- neuf, selon la convention du projet (voir supabase/migrations/00019+).
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.llm_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    project_id UUID REFERENCES public.projects(id) ON DELETE SET NULL,
    provider_id TEXT,
    model_string TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost_usd NUMERIC(12,6),
    was_fallback BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_logs_tenant_created ON public.llm_usage_logs(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_llm_usage_logs_provider_created ON public.llm_usage_logs(provider_id, created_at);

ALTER TABLE public.llm_usage_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_isolation_llm_usage_logs" ON public.llm_usage_logs
    FOR ALL USING (
        tenant_id = public.current_tenant_id()
        OR auth.role() = 'service_role'
    );

COMMENT ON TABLE public.llm_usage_logs IS
'Journal de consommation LLM (tokens + cout estime) par appel reel, alimente depuis app/workers/tasks.py apres chaque generation. Ajoutee le 30/08 en reponse a une demande explicite de suivi de consommation utilisateur.';
