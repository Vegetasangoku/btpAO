-- ==============================================================================
-- 00016b_add_embedding_and_retention_to_company_assets.sql
-- Ajout colonne embedding vector(1536), statut et champ obsolete_at pour rétention
-- Indexation HNSW pour recherche sémantique cosinus ultra-rapide
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE public.company_assets 
ADD COLUMN IF NOT EXISTS embedding vector(1536);

ALTER TABLE public.company_assets 
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'indexed';

ALTER TABLE public.company_assets 
ADD COLUMN IF NOT EXISTS obsolete_at TIMESTAMPTZ NULL;

CREATE INDEX IF NOT EXISTS idx_company_assets_embedding_hnsw 
ON public.company_assets USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_company_assets_obsolete 
ON public.company_assets (status, obsolete_at) 
WHERE status = 'obsolete';
