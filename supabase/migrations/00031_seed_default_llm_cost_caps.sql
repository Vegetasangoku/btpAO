-- ═══════════════════════════════════════════════════════════════════════════════
-- 00031 — Plafonds de dépense IA : valeurs de départ par forfait
--
-- La migration 00030 a créé les colonnes (subscription_plans.monthly_llm_cost_cap_usd
-- et tenant_subscriptions.custom_llm_cost_cap_usd) mais les a laissées à NULL, c'est-à-
-- dire « aucun plafond appliqué ». Résultat : un client pouvait consommer sans limite
-- des appels facturés au fournisseur alors que son abonnement, lui, est fixe.
--
-- Cette migration pose une valeur de départ, calculée pour que la dépense IA reste
-- autour de 15 % du prix de vente HT — la marge restante couvrant hébergement, support
-- et bénéfice. Conversion appliquée : 1 € = 1,08 $.
--
--   starter    199 € →  215 $ × 15 % ≈  32 $   → 32 $
--   pro        499 € →  539 $ × 15 % ≈  81 $   → 80 $
--   enterprise sur devis, volume négocié       → 400 $ (à réviser au contrat)
--
-- Ces montants sont un point de départ, pas une règle figée : ils se modifient dans
-- l'administration (Budgets & plafonds IA) ou par API (PUT /api/admin/cost-limits/...),
-- et un client peut recevoir un plafond nominatif prioritaire.
--
-- Le UPDATE ne touche que les lignes encore à NULL : une valeur déjà choisie par un
-- administrateur n'est jamais écrasée par une migration.
-- ═══════════════════════════════════════════════════════════════════════════════

UPDATE public.subscription_plans SET monthly_llm_cost_cap_usd = 32.00
  WHERE id = 'starter' AND monthly_llm_cost_cap_usd IS NULL;

UPDATE public.subscription_plans SET monthly_llm_cost_cap_usd = 80.00
  WHERE id = 'pro' AND monthly_llm_cost_cap_usd IS NULL;

UPDATE public.subscription_plans SET monthly_llm_cost_cap_usd = 400.00
  WHERE id = 'enterprise' AND monthly_llm_cost_cap_usd IS NULL;

-- Tout autre forfait créé depuis (sur-mesure) : 15 % du prix de vente, plancher 25 $.
UPDATE public.subscription_plans
   SET monthly_llm_cost_cap_usd = GREATEST(ROUND((price_monthly_cents / 100.0) * 1.08 * 0.15), 25)
 WHERE monthly_llm_cost_cap_usd IS NULL
   AND price_monthly_cents > 0;

COMMENT ON COLUMN public.subscription_plans.monthly_llm_cost_cap_usd IS
'Plafond mensuel de cout LLM reel (USD) applique par defaut a tout client de ce forfait. Valeurs de depart posees par la migration 00031 (environ 15 % du prix de vente HT), modifiables dans l''administration ou par API. NULL = aucun plafond applique.';
