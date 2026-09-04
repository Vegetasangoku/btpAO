-- Persists fetched page content for tenant-added reference URLs (buyer/client site,
-- professional federations, etc.) so it can be reused as a RAG source during memo
-- generation, not just for the one-off company-profile bootstrap scan or the
-- "Mon Entreprise" chat assistant. Content stays capped application-side (~6000 chars
-- by fetch_page_content, then re-bounded to a small prompt budget at generation time)
-- so a large or numerous set of sites can never blow up LLM cost.
ALTER TABLE tenant_reference_urls
    ADD COLUMN IF NOT EXISTS content_title text,
    ADD COLUMN IF NOT EXISTS content_excerpt text;

COMMENT ON COLUMN tenant_reference_urls.content_excerpt IS
    'Extracted page text (already capped at ~6000 chars by company_bootstrap_service.fetch_page_content). Re-injected into memo generation via a small dedicated budget (CONTEXT_LIMITS["client_sites"]).';

COMMENT ON COLUMN tenant_reference_urls.content_title IS
    'Page <title> captured at last successful fetch, used as the citation label in generated content.';
