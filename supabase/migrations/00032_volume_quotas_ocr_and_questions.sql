-- ==============================================================================
-- 00032_volume_quotas_ocr_and_questions.sql
-- Trois nouveaux verrous de cout, en miroir exact des mecanismes deja en place
-- pour les dossiers (included_dossiers_month / custom_quota_dossiers) et le cout
-- LLM (monthly_llm_cost_cap_usd / custom_llm_cost_cap_usd, migration 00030) :
--
--   1. Volume de pages ingerees / mois (DCE + base de connaissances confondus).
--      Sans ce verrou, un client qui deverse des centaines de dossiers volumineux
--      (SharePoint compris) peut faire grossir indefiniment dce_embeddings /
--      knowledge_vectors -- ce qui degrade les perfs de recherche vectorielle ET
--      finit par pousser la facture de calcul/stockage Supabase au-dela du forfait
--      qu'il paye, sans qu'aucun signal ne le bloque avant coup.
--   2. Cout OCR Azure Document Intelligence reel, jusqu'ici totalement absent de
--      llm_usage_logs et de tout plafond -- un cout variable invisible qui peut
--      deraper independamment du plafond LLM existant.
--   3. Nombre de questions posees au chat assistant (endpoint /projects/{id}/ask)
--      par mois -- le plafond de cout LLM (00030) protege deja le $ reel consomme,
--      mais un nombre de questions illimite reste un signal d'abus a plafonner
--      separement (Go/No-Go, latence, charge), avec dépassement payant comme pour
--      les dossiers.
--
-- Convention : NULL = aucun plafond configure (non applique), valeur par forfait
-- surchargeable par tenant, jamais code en dur cote application.
-- ==============================================================================

-- ── 1. Quota de pages ingerees, par forfait et par tenant ────────────────────
ALTER TABLE public.subscription_plans
    ADD COLUMN IF NOT EXISTS included_pages_month INTEGER,
    ADD COLUMN IF NOT EXISTS extra_pages_price_cents_per_1000 INTEGER NOT NULL DEFAULT 500,
    ADD COLUMN IF NOT EXISTS monthly_ocr_cost_cap_usd NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS included_questions_month INTEGER,
    ADD COLUMN IF NOT EXISTS extra_questions_price_cents_per_100 INTEGER NOT NULL DEFAULT 300,
    ADD COLUMN IF NOT EXISTS included_sharepoint_files_month INTEGER,
    ADD COLUMN IF NOT EXISTS extra_sharepoint_files_price_cents_per_100 INTEGER NOT NULL DEFAULT 400;

ALTER TABLE public.tenant_subscriptions
    ADD COLUMN IF NOT EXISTS custom_pages_month INTEGER,
    ADD COLUMN IF NOT EXISTS custom_ocr_cost_cap_usd NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS custom_questions_month INTEGER,
    ADD COLUMN IF NOT EXISTS custom_sharepoint_files_month INTEGER,
    ADD COLUMN IF NOT EXISTS allow_page_overage BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS allow_question_overage BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS allow_sharepoint_overage BOOLEAN NOT NULL DEFAULT true;

ALTER TABLE public.tenant_usage_counters
    ADD COLUMN IF NOT EXISTS pages_ingested INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS questions_asked INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ocr_pages_azure INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ocr_pages_local INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS sharepoint_files_indexed INTEGER NOT NULL DEFAULT 0;

-- ── 2. Journal de consommation OCR reelle (miroir de llm_usage_logs) ─────────
CREATE TABLE IF NOT EXISTS public.ocr_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    document_id UUID NULL,
    source TEXT NOT NULL DEFAULT 'dce',           -- 'dce' | 'knowledge' | 'sharepoint'
    provider TEXT NOT NULL,                        -- 'azure_doc_intelligence' | 'local_pdf_parser'
    pages_local INTEGER NOT NULL DEFAULT 0,
    pages_azure INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd NUMERIC(12, 6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.ocr_usage_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_ocr_usage_logs" ON public.ocr_usage_logs;
CREATE POLICY "tenant_isolation_ocr_usage_logs" ON public.ocr_usage_logs
    FOR ALL USING (
        tenant_id = public.current_tenant_id()
        OR auth.role() = 'service_role'
    );

CREATE INDEX IF NOT EXISTS idx_ocr_usage_logs_tenant_created ON public.ocr_usage_logs(tenant_id, created_at);

GRANT ALL ON public.ocr_usage_logs TO postgres, authenticated, anon, service_role, btp_app_user;

-- ── 3. Empreinte de fichier pour les DCE (deduplication anti-doublon/anti-abus,
--      miroir de company_assets.metadata_json->>'file_hash' deja utilise dans
--      knowledge.py mais absent du pipeline DCE) ────────────────────────────
ALTER TABLE public.dce_documents
    ADD COLUMN IF NOT EXISTS file_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_dce_documents_tenant_file_hash ON public.dce_documents(tenant_id, file_hash);

COMMENT ON COLUMN public.subscription_plans.included_pages_month IS
'Volume de pages ingerees inclus par mois (DCE + base de connaissances + SharePoint), tous documents confondus. NULL = illimite (non applique).';
COMMENT ON COLUMN public.subscription_plans.monthly_ocr_cost_cap_usd IS
'Plafond mensuel de cout OCR Azure Document Intelligence reel (USD estimes, voir ocr_usage_logs). NULL = aucun plafond.';
COMMENT ON COLUMN public.subscription_plans.included_questions_month IS
'Nombre de questions au chat assistant (/projects/{id}/ask) incluses par mois. NULL = illimite.';
COMMENT ON COLUMN public.subscription_plans.included_sharepoint_files_month IS
'Nombre de fichiers SharePoint (nouveaux ou modifies) indexes automatiquement par mois via la synchronisation delta. NULL = illimite.';
