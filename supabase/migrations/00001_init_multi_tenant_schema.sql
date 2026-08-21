-- ==============================================================================
-- btpAO Multi-Tenant Schema with RLS and pgvector
-- Target Supabase Project: boyloyvoy@gmail.com's ProjectBTP
-- Target Org: Appel offre Charb (ppsunidynztbfigzecwu)
-- ==============================================================================

-- 1. Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1.b Application Non-Superuser Role (btp_app_user)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'btp_app_user') THEN
        CREATE ROLE btp_app_user NOLOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO btp_app_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO btp_app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO btp_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO btp_app_user;

-- 2. Tenants Table
CREATE TABLE IF NOT EXISTS public.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    plan TEXT NOT NULL DEFAULT 'enterprise',
    s3_bucket_prefix TEXT,
    branding_config JSONB DEFAULT '{
        "primary_color": "#0ea5e9",
        "secondary_color": "#0f172a",
        "font_family": "Inter",
        "logo_url": null,
        "company_name": "BTP Construction SAS",
        "header_text": "Mémoire Technique Justificatif",
        "footer_text": "Document confidentiel soumis dans le cadre de l''Appel d''Offres"
    }'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Users Table (Mapped to Supabase Auth & Multi-Tenancy)
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'member', -- 'admin', 'conducteur_travaux', 'chiffreur', 'member'
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_tenant_email UNIQUE(tenant_id, email)
);

-- 4. Projects (Dossiers d'Appel d'Offres & Mémoires Techniques)
CREATE TABLE IF NOT EXISTS public.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    reference_code TEXT NOT NULL,
    client_name TEXT NOT NULL,
    location TEXT,
    lot_number TEXT,
    status TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'dce_parsed', 'decisions_saved', 'generating', 'review', 'validated', 'exported'
    budget_estimate NUMERIC(15, 2),
    submission_deadline TIMESTAMPTZ,
    scoring_notes JSONB DEFAULT '{"technical_weight": 60, "price_weight": 40}'::jsonb,
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. DCE Documents (Pièces du dossier de consultation : RC, CCTP, CCAP, BPU, etc.)
CREATE TABLE IF NOT EXISTS public.dce_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    doc_type TEXT NOT NULL DEFAULT 'cctp', -- 'rc', 'cctp', 'ccap', 'bpu', 'plans', 'autre'
    s3_key TEXT NOT NULL,
    file_size_bytes BIGINT DEFAULT 0,
    ocr_status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    parsed_summary TEXT,
    raw_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. DCE Embeddings (Chunks vectorisés pour le RAG DCE)
CREATE TABLE IF NOT EXISTS public.dce_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES public.dce_documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    page_number INT DEFAULT 1,
    section_title TEXT,
    content TEXT NOT NULL,
    metadata_json JSONB DEFAULT '{}'::jsonb,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. DCE Criteria (Grille de notation et exigences extraites du Règlement de Consultation)
CREATE TABLE IF NOT EXISTS public.dce_criteria (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    criterion_title TEXT NOT NULL,
    weight_percentage NUMERIC(5, 2) DEFAULT 0,
    description TEXT NOT NULL,
    key_expectations JSONB DEFAULT '[]'::jsonb,
    required_evidence JSONB DEFAULT '[]'::jsonb,
    mandatory BOOLEAN DEFAULT true,
    extracted_from TEXT DEFAULT 'Règlement de Consultation (RC)',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 8. Company Assets (Base de connaissances client : Certificats, Fiches Matériel, Références Chantiers, CVs)
CREATE TABLE IF NOT EXISTS public.company_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    category TEXT NOT NULL, -- 'reference_chantier', 'materiel_engins', 'certificat_qualibat', 'cv_encadrement', 'demarche_rse', 'securite_ppsps'
    title TEXT NOT NULL,
    description TEXT,
    s3_url TEXT,
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 9. Knowledge Vectors (Vectorisation de la base de connaissances entreprise)
CREATE TABLE IF NOT EXISTS public.knowledge_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    asset_id UUID REFERENCES public.company_assets(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json JSONB DEFAULT '{}'::jsonb,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 10. Project Decisions (Formulaire de décisions & choix métiers du conducteur de travaux)
CREATE TABLE IF NOT EXISTS public.project_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    project_id UUID NOT NULL UNIQUE REFERENCES public.projects(id) ON DELETE CASCADE,
    form_data JSONB NOT NULL DEFAULT '{
        "delai_mois": 6,
        "date_demarrage": null,
        "materiel_principal": "Grue à tour Potain 50m, 2 pelles 20t, centrale à béton dédiée",
        "travail_de_nuit": false,
        "gestion_dechets": "Tri 5 flux in situ avec valorisation 85% en filière locale agréée",
        "equipe_cadres": [
            {"nom": "Jean Dupont", "role": "Directeur de Travaux", "experience_ans": 15, "qualif": "Ingénieur ESTP"},
            {"nom": "Marc Martin", "role": "Conducteur de Travaux Principal", "experience_ans": 9, "qualif": "Master Génie Civil"}
        ],
        "mesures_securite": "PPSPS strict, accueil sécurité obligatoire, EPI connectés, 0 accident visé",
        "demarche_rse_environnement": "Béton bas carbone CEM III/A, éclairage LED solaire, charte chantier vert à faibles nuisances",
        "phasage_travaux": [
            {"phase": "Phase 1 : Installation de chantier, terrassement & voirie", "duree_semaines": 4, "jalon": "Plateforme opérationnelle"},
            {"phase": "Phase 2 : Fondations spéciales et superstructure gros oeuvre", "duree_semaines": 12, "jalon": "Hors d''eau / Hors d''air"},
            {"phase": "Phase 3 : Corps d''état secondaires, techniques & finitions", "duree_semaines": 8, "jalon": "OPR & Levée des réserves"}
        ]
    }'::jsonb,
    updated_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 11. Generated Sections (Sections du Mémoire Technique rédigées par l'IA et modifiables en WYSIWYG)
CREATE TABLE IF NOT EXISTS public.generated_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    section_key TEXT NOT NULL, -- 'moyens_humains', 'moyens_materiels', 'methodologie_phasage', 'qse_environnement', 'planning_gantt', etc.
    title TEXT NOT NULL,
    order_index INT NOT NULL DEFAULT 1,
    content_html TEXT NOT NULL DEFAULT '',
    content_json JSONB DEFAULT '{}'::jsonb,
    visual_placeholders JSONB DEFAULT '[]'::jsonb,
    compliance_score NUMERIC(4, 1) DEFAULT 100.0,
    compliance_notes TEXT,
    status TEXT NOT NULL DEFAULT 'generated', -- 'generating', 'generated', 'edited', 'validated'
    locked_for_export BOOLEAN DEFAULT false,
    validated_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    validated_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_project_section UNIQUE(project_id, section_key)
);

-- 12. Export Templates (.docx Jinja2 Templates de charte graphique client)
CREATE TABLE IF NOT EXISTS public.export_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    s3_docx_key TEXT NOT NULL,
    is_default BOOLEAN DEFAULT false,
    styles_config JSONB DEFAULT '{
        "primary_color_hex": "#0F4C81",
        "secondary_color_hex": "#2D3748",
        "font_family_title": "Calibri",
        "font_family_body": "Calibri Light"
    }'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 13. Export Jobs (Suivi des exports Word et PDF)
CREATE TABLE IF NOT EXISTS public.export_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    template_id UUID REFERENCES public.export_templates(id) ON DELETE SET NULL,
    format TEXT NOT NULL DEFAULT 'docx', -- 'docx', 'pdf', 'both'
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'generating', 'completed', 'failed'
    s3_docx_url TEXT,
    s3_pdf_url TEXT,
    file_size_bytes BIGINT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- 14. Audit Logs (Traçabilité juridique des modifications et validations)
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID,
    details JSONB DEFAULT '{}'::jsonb,
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ==============================================================================
-- INDEXES & PERFORMANCE (B-tree & pgvector HNSW)
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_users_tenant ON public.users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_projects_tenant ON public.projects(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dce_docs_project ON public.dce_documents(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_dce_criteria_project ON public.dce_criteria(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_company_assets_tenant ON public.company_assets(tenant_id, category);
CREATE INDEX IF NOT EXISTS idx_generated_sections_project ON public.generated_sections(tenant_id, project_id);
CREATE INDEX IF NOT EXISTS idx_export_jobs_project ON public.export_jobs(tenant_id, project_id);

-- HNSW Vector Indexes for Fast Cosine Similarity
CREATE INDEX IF NOT EXISTS idx_dce_embeddings_hnsw 
ON public.dce_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_hnsw 
ON public.knowledge_vectors USING hnsw (embedding vector_cosine_ops);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dce_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dce_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dce_criteria ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_vectors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.generated_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.export_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.export_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Helper function to extract tenant_id from auth.jwt() or session setting
CREATE OR REPLACE FUNCTION public.current_tenant_id()
RETURNS UUID AS $$
BEGIN
    RETURN COALESCE(
        NULLIF(current_setting('app.current_tenant_id', true), '')::UUID,
        (auth.jwt() -> 'app_metadata' ->> 'tenant_id')::UUID
    );
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

-- Macro RLS Policies
-- Tenants
CREATE POLICY "tenant_isolation_tenants" ON public.tenants
    FOR ALL USING (
        id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- Users
CREATE POLICY "tenant_isolation_users" ON public.users
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- Projects
CREATE POLICY "tenant_isolation_projects" ON public.projects
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- DCE Documents
CREATE POLICY "tenant_isolation_dce_documents" ON public.dce_documents
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- DCE Embeddings
CREATE POLICY "tenant_isolation_dce_embeddings" ON public.dce_embeddings
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- DCE Criteria
CREATE POLICY "tenant_isolation_dce_criteria" ON public.dce_criteria
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- Company Assets
CREATE POLICY "tenant_isolation_company_assets" ON public.company_assets
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- Knowledge Vectors
CREATE POLICY "tenant_isolation_knowledge_vectors" ON public.knowledge_vectors
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- Project Decisions
CREATE POLICY "tenant_isolation_project_decisions" ON public.project_decisions
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- Generated Sections
CREATE POLICY "tenant_isolation_generated_sections" ON public.generated_sections
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- Export Templates
CREATE POLICY "tenant_isolation_export_templates" ON public.export_templates
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- Export Jobs
CREATE POLICY "tenant_isolation_export_jobs" ON public.export_jobs
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- Audit Logs
CREATE POLICY "tenant_isolation_audit_logs" ON public.audit_logs
    FOR ALL USING (
        tenant_id = public.current_tenant_id() 
        OR auth.role() = 'service_role'
    );

-- ==============================================================================
-- VECTOR SEARCH RPC FUNCTIONS (Strictly Scoped by Tenant & Project)
-- ==============================================================================

-- 1. Match DCE Chunks
CREATE OR REPLACE FUNCTION public.match_dce_chunks(
    p_tenant_id UUID,
    p_project_id UUID,
    p_query_embedding vector(1536),
    p_match_threshold FLOAT DEFAULT 0.4,
    p_match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    chunk_index INT,
    page_number INT,
    section_title TEXT,
    content TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.document_id,
        d.chunk_index,
        d.page_number,
        d.section_title,
        d.content,
        1 - (d.embedding <=> p_query_embedding) AS similarity
    FROM public.dce_embeddings d
    WHERE d.tenant_id = p_tenant_id
      AND d.project_id = p_project_id
      AND (1 - (d.embedding <=> p_query_embedding)) > p_match_threshold
    ORDER BY d.embedding <=> p_query_embedding
    LIMIT p_match_count;
END;
$$;

-- 2. Match Company Knowledge Vectors
CREATE OR REPLACE FUNCTION public.match_company_knowledge(
    p_tenant_id UUID,
    p_category TEXT,
    p_query_embedding vector(1536),
    p_match_threshold FLOAT DEFAULT 0.4,
    p_match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    asset_id UUID,
    category TEXT,
    content TEXT,
    metadata_json JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        k.id,
        k.asset_id,
        k.category,
        k.content,
        k.metadata_json,
        1 - (k.embedding <=> p_query_embedding) AS similarity
    FROM public.knowledge_vectors k
    WHERE k.tenant_id = p_tenant_id
      AND (p_category IS NULL OR k.category = p_category)
      AND (1 - (k.embedding <=> p_query_embedding)) > p_match_threshold
    ORDER BY k.embedding <=> p_query_embedding
    LIMIT p_match_count;
END;
$$;
