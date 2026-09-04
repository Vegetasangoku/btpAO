-- Migration 00035: expose WHY a reference-site fetch failed, not just the resulting
-- 'broken' status (03/09, demande client explicite : "qu'on sache quand un site
-- repond pas ausi"). Avant ce correctif, company_bootstrap_service.fetch_page_content
-- journalisait la cause reelle (timeout, code HTTP, contenu vide...) uniquement cote
-- serveur (logger.warning) -- invisible du client, qui ne voyait qu'un badge "Erreur"
-- muet dans Mon Entreprise > Sites de Reference, sans aucun moyen de savoir si le
-- probleme venait d'une protection anti-robots, d'un site hors ligne ou d'une URL mal
-- saisie.
ALTER TABLE tenant_reference_urls
    ADD COLUMN IF NOT EXISTS last_fetch_error text;

COMMENT ON COLUMN tenant_reference_urls.last_fetch_error IS
    'Human-readable reason the last fetch attempt failed (timeout, HTTP status, empty/JS-only content, blocked by bot protection...). Populated by company_bootstrap_service.fetch_page_content_verbose via add_reference_url / refresh_reference_url. NULL when status is not broken, or when the failure predates this column (existing broken rows backfill on next Actualiser click). Cleared automatically on the next successful fetch.';
