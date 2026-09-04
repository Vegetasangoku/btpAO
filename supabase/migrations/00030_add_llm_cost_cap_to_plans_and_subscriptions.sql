-- ==============================================================================
-- 00030_add_llm_cost_cap_to_plans_and_subscriptions.sql
-- Plafond mensuel de cout LLM reel, parametrable par forfait et par tenant.
--
-- Contexte (02/09) : demande explicite et chiffree de l'utilisateur -- aucun
-- mecanisme ne garantissait que le cout LLM reel consomme par un tenant reste
-- sous ce que l'operateur est pret a tolerer au regard du prix de son forfait
-- (protection de marge). Exemple donne par l'utilisateur : un forfait a 10
-- dossiers inclus facture environ 450-499 EUR/mois ne doit jamais couter plus
-- qu'un plafond choisi (ex. 120-150 USD) en consommation LLM reelle, quel que
-- soit le volume de questions posees par le client.
--
-- Miroir exact du mecanisme deja existant pour le quota de dossiers
-- (subscription_plans.included_dossiers_month + tenant_subscriptions.
-- custom_quota_dossiers) : une valeur par defaut au niveau du forfait,
-- surchargeable individuellement par tenant. NULL = aucun plafond configure
-- (non applique -- jamais bloquant tant qu'un admin n'a pas choisi une valeur
-- explicitement, y compris pour les tenants existants avant cette migration).
--
-- Applique via mcp__Supabase__apply_migration ET conserve ici en fichier
-- versionne, selon la convention du projet (voir supabase/migrations/00019+).
-- Voir app/services/billing_service.py (get_effective_cost_cap_usd,
-- check_and_enforce_cost_cap, is_cost_cap_exceeded,
-- get_tenant_current_month_spend_usd, estimate_llm_cost_usd, log_llm_usage)
-- pour le cablage complet, et app/workers/tasks.py + les points d'appel LLM
-- reels (chat entreprise, chat projet, chat DCE, analyse de chiffrage,
-- extraction de criteres, bootstrap entreprise) pour l'application du
-- controle avant chaque appel facturable.
-- ==============================================================================

ALTER TABLE public.subscription_plans
    ADD COLUMN IF NOT EXISTS monthly_llm_cost_cap_usd NUMERIC(10, 2);

ALTER TABLE public.tenant_subscriptions
    ADD COLUMN IF NOT EXISTS custom_llm_cost_cap_usd NUMERIC(10, 2);

COMMENT ON COLUMN public.subscription_plans.monthly_llm_cost_cap_usd IS
'Plafond mensuel par defaut (USD reels estimes, voir llm_usage_logs.estimated_cost_usd) de cout LLM pour les tenants sur ce forfait. NULL = aucun plafond (non applique). Protege la marge de l''operateur en bloquant (402) les appels LLM facturables au-dela de ce montant, avant appel.';

COMMENT ON COLUMN public.tenant_subscriptions.custom_llm_cost_cap_usd IS
'Surcharge par-tenant du plafond mensuel de cout LLM (prioritaire sur subscription_plans.monthly_llm_cost_cap_usd si definie). NULL = herite du forfait. Miroir exact de custom_quota_dossiers.';
