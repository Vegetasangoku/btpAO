"""
SQLAlchemy 2 ORM Models for btpAO Schema.
Directly maps to the tables defined in 00001_init_multi_tenant_schema.sql.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None
from app.core.db import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    slug = Column(Text, unique=True, nullable=False)
    siret = Column(String(20), nullable=True)
    country_code = Column(String(2), default="FR", nullable=False)
    plan = Column(Text, nullable=False, default="enterprise")
    s3_bucket_prefix = Column(Text, nullable=True)
    branding_config = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)



class CountryRegulatoryProfile(Base):
    __tablename__ = "country_regulatory_profiles"

    country_code = Column(String(2), primary_key=True)
    country_name = Column(Text, nullable=False)
    procurement_framework = Column(Text, nullable=True)
    key_regulations = Column(JSONB, default=list)
    standard_requirements = Column(JSONB, default=list)
    mandatory_certifications = Column(JSONB, default=list)
    currency = Column(Text, default="EUR")
    tender_document_structure = Column(JSONB, default=dict)
    is_active = Column(Boolean, default=True, nullable=False)
    technical_standards_reference = Column(Text, nullable=True)
    environmental_regulation = Column(Text, nullable=True)
    public_procurement_regime = Column(Text, nullable=True)
    recognized_qualifications = Column(JSONB, default=list)
    waste_tracking_regime = Column(Text, nullable=True)
    safety_plan_regime = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class CountryOfficialSource(Base):
    __tablename__ = "country_official_sources"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_code = Column(String(2), nullable=False, index=True)
    portal_name = Column(Text, nullable=False)
    portal_url = Column(Text, nullable=False)
    portal_type = Column(Text, nullable=False, index=True)
    reference_law = Column(Text, nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_known_hash = Column(Text, nullable=True)
    last_summary = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)



class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    email = Column(Text, nullable=False)
    full_name = Column(Text, nullable=True)
    role = Column(Text, nullable=False, default="member")
    status = Column(Text, nullable=False, default="active")
    avatar_url = Column(Text, nullable=True)
    deletion_requested_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_purge_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)



class TenantInvitation(Base):
    __tablename__ = "tenant_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    email = Column(Text, nullable=False)
    role = Column(Text, nullable=False, default="member")
    invitation_token = Column(Text, unique=True, nullable=False)
    status = Column(Text, nullable=False, default="pending")
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Project(Base):

    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    reference_code = Column(Text, nullable=False)
    client_name = Column(Text, nullable=False)
    location = Column(Text, nullable=True)
    lot_number = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="draft")
    budget_estimate = Column(Numeric(15, 2), nullable=True)
    submission_deadline = Column(DateTime(timezone=True), nullable=True)
    scoring_notes = Column(JSONB, default=lambda: {"technical_weight": 60, "price_weight": 40})
    strategic_directives = Column(Text, nullable=True)
    output_language = Column(Text, nullable=False, default="fr")  # 'fr' | 'en' | 'ar' -- CHECK constraint en base (30/08)
    metadata_json = Column(JSONB, default=dict)
    outcome_status = Column(Text, default="pending", nullable=False)
    buyer_feedback = Column(JSONB, default=dict)
    outcome_recorded_at = Column(DateTime(timezone=True), nullable=True)
    outcome_recorded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TenantLearning(Base):
    __tablename__ = "tenant_learnings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    category = Column(Text, nullable=False, default="general")
    title = Column(Text, nullable=False)
    learning_insight = Column(Text, nullable=False)
    actionable_directive = Column(Text, nullable=False)
    source_outcome = Column(Text, nullable=False, default="lost")
    section_type = Column(Text, nullable=True)
    learned_content = Column(Text, nullable=True)
    source_diff = Column(JSONB, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ProjectGanttTask(Base):
    """
    Interactive Gantt task (Batch 11, cahier des charges majeur). Separate from
    ProjectDecision.form_data['phasage_travaux'] -- see migration 00026 for why the
    two are kept apart rather than merged.
    """
    __tablename__ = "project_gantt_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    sequence = Column(Integer, nullable=False, default=0)
    is_milestone = Column(Boolean, nullable=False, default=False)
    milestone_label = Column(Text, nullable=True)
    depends_on = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class DCEDocument(Base):

    __tablename__ = "dce_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename = Column(Text, nullable=False)
    doc_type = Column(Text, nullable=False, default="cctp")
    s3_key = Column(Text, nullable=False)
    file_size_bytes = Column(Numeric, default=0)
    file_hash = Column(Text, nullable=True)  # 03/09 : dedup anti-doublon/anti-abus, miroir de company_assets
    ocr_status = Column(Text, default="uploaded")
    parsed_summary = Column(Text, nullable=True)
    raw_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    @property
    def status(self):
        return self.ocr_status

    @status.setter
    def status(self, val):
        self.ocr_status = val

    @property
    def metadata_json(self):
        return self.raw_metadata

    @metadata_json.setter
    def metadata_json(self, val):
        self.raw_metadata = val


class DCECriterionEntity(Base):
    __tablename__ = "dce_criteria"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    criterion_title = Column(Text, nullable=False)
    weight_percentage = Column(Numeric(5, 2), nullable=False)
    description = Column(Text, nullable=True)
    key_expectations = Column(JSONB, default=list)
    required_evidence = Column(JSONB, default=list)
    mandatory = Column(String, default="true")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class ProjectPricingLine(Base):
    """BT01 -- ligne de chiffrage (métré simplifié). Voir apps/api/app/api/pricing.py."""
    __tablename__ = "project_pricing_lines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    lot = Column(Text, nullable=True)
    designation = Column(Text, nullable=False)
    unite = Column(Text, nullable=False, default="u")
    quantite = Column(Numeric(14, 3), nullable=False)
    prix_unitaire_ht = Column(Numeric(14, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class DCEEmbedding(Base):
    __tablename__ = "dce_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("dce_documents.id", ondelete="CASCADE"), nullable=True)
    chunk_index = Column(Numeric, nullable=False, default=0)
    page_number = Column(Numeric, nullable=False, default=1)
    section_title = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536) if Vector is not None else Text, nullable=True)
    metadata_json = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class ProjectDecision(Base):
    __tablename__ = "project_decisions"

    # 29/08 (fin de journée) : ce modèle déclarait un `created_at` qui n'existe PAS dans la
    # vraie table (et lui manquait `updated_by`, qui existe réellement) -- trouvé en testant
    # une génération de section pour de vrai, qui échouait pour TOUS les projets avec
    # "UndefinedColumnError: column project_decisions.created_at does not exist". Corrigé
    # pour correspondre exactement au schéma réel (voir information_schema.columns).
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False)
    form_data = Column(JSONB, nullable=False, default=dict)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class GeneratedSection(Base):
    __tablename__ = "generated_sections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    section_key = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    order_index = Column(Numeric, nullable=False, default=1)
    content_html = Column(Text, nullable=False, default="")
    content_json = Column(JSONB, default=dict)
    visual_placeholders = Column(JSONB, default=list)
    compliance_score = Column(Numeric(4, 1), default=100.0)
    compliance_notes = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="generated")
    prefill_source = Column(JSONB, default=list)
    is_prefilled = Column(Boolean, default=False)
    locked_for_export = Column(Boolean, default=False)
    validated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class GeneratedSectionVersion(Base):
    __tablename__ = "generated_section_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(UUID(as_uuid=True), ForeignKey("generated_sections.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False, default=1)
    title = Column(Text, nullable=False)
    content_html = Column(Text, nullable=False)
    content_json = Column(JSONB, default=dict)
    compliance_score = Column(Numeric(4, 1), default=100.0)
    compliance_notes = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="edited")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    change_summary = Column(Text, default="Modification éditeur")


class ProjectGoNoGoAnalysis(Base):
    __tablename__ = "project_go_no_go_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    recommendation = Column(Text, nullable=False)
    score = Column(Numeric(5, 2), nullable=False)
    summary = Column(Text, nullable=False)
    factors = Column(JSONB, default=list, nullable=False)
    mandatory_criteria_met = Column(Boolean, default=True, nullable=False)
    blocking_issues = Column(JSONB, default=list, nullable=False)
    completion_rate = Column(Numeric(5, 2), nullable=True)
    has_sufficient_data = Column(Boolean, default=True, nullable=False)
    evaluated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


from pgvector.sqlalchemy import Vector


class CompanyAsset(Base):
    __tablename__ = "company_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    category = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    s3_url = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="indexed")
    source_type = Column(Text, nullable=False, default="manual_upload")  # 'manual_upload', 'web_auto_bootstrap', 'learned_adjustment', 'tenant_provided_url'
    collected_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    validated_by_user = Column(Boolean, default=True, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    obsolete_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class KnowledgeVector(Base):
    """
    Fragments (chunks) du texte COMPLET de chaque company_asset, un embedding par
    fragment -- miroir de DCEEmbedding mais pour la base de connaissances
    entreprise. Corrige le plafond `extracted_text[:4000]` de l'ancien pipeline
    (app/api/knowledge.py), qui ne rendait recherchable que les ~2 premières pages
    de tout document déposé, quelle que soit sa longueur réelle (mémoires
    techniques, réponses à appels d'offres passées...). La table
    `knowledge_vectors`, son index HNSW (idx_knowledge_vectors_hnsw) et sa policy
    RLS (tenant_isolation_knowledge_vectors) existaient déjà depuis la migration
    00001_init_multi_tenant_schema.sql -- jamais mappés côté ORM ni jamais utilisés
    par le code applicatif. Réutilisés ici tels quels (aucune nouvelle migration de
    schéma nécessaire) plutôt que de créer une table parallèle redondante. (30/08)
    """
    __tablename__ = "knowledge_vectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("company_assets.id", ondelete="CASCADE"), nullable=True)
    category = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSONB, default=dict)
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class CompanyBootstrapRun(Base):
    __tablename__ = "company_bootstrap_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    status = Column(Text, nullable=False, default="pending")  # 'pending', 'running', 'completed', 'failed'
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    sources_found = Column(JSONB, default=list, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class TenantReferenceUrl(Base):
    __tablename__ = "tenant_reference_urls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    url = Column(Text, nullable=False)
    label = Column(Text, nullable=True)
    added_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    added_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Text, nullable=False, default="active")  # 'active', 'broken', 'fetching'


class TenantSettings(Base):
    __tablename__ = "tenants_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False)
    custom_system_prompt = Column(Text, nullable=True)
    system_prompt_memory = Column(Text, nullable=True)
    taux_inflation_pct = Column(Numeric(5, 2), default=3.5)
    marge_cible_pct = Column(Numeric(5, 2), default=12.0)
    taux_horaires = Column(JSONB, default=dict)
    economic_settings = Column(JSONB, default=dict)
    cree_le = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    mis_a_jour_le = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)




class ExportTemplate(Base):
    __tablename__ = "export_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    s3_docx_key = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("export_templates.id", ondelete="SET NULL"), nullable=True)
    format = Column(Text, nullable=False, default="docx")
    status = Column(Text, nullable=False, default="pending")
    s3_docx_url = Column(Text, nullable=True)
    s3_pdf_url = Column(Text, nullable=True)
    file_size_bytes = Column(Numeric, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class PlatformSettings(Base):
    __tablename__ = "platform_settings"

    id = Column(Text, primary_key=True, default="global")
    settings = Column(JSONB, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class LlmCatalogModel(Base):
    """Catalogue de modèles LLM en lecture seule, synchronisé depuis OpenRouter (29/08).
    Sert de référence (liste à jour, prix, dépréciation) pour l'admin -- ne remplace PAS
    le chemin d'appel réel (LiteLLM + clés propres du tenant/plateforme, inchangé)."""
    __tablename__ = "llm_catalog_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(Text, nullable=False, unique=True)
    canonical_slug = Column(Text, nullable=True)
    display_name = Column(Text, nullable=True)
    provider_slug = Column(Text, nullable=True)
    context_length = Column(Integer, nullable=True)
    pricing_prompt_per_million = Column(Numeric(14, 4), nullable=True)
    pricing_completion_per_million = Column(Numeric(14, 4), nullable=True)
    is_moderated = Column(Boolean, nullable=False, default=False)
    expiration_date = Column(DateTime(timezone=True), nullable=True)
    raw_metadata = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    first_seen_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class LlmUsageLog(Base):
    """Journal de consommation LLM (30/08) -- une ligne par appel LiteLLM reel (chemin
    principal ou repli resilient), avec tokens et cout estime (via les prix de
    LlmCatalogModel quand le modele y est reference). Reponse a une demande explicite de
    l'utilisateur : aucun suivi de consommation ni limite parametrable n'existait avant
    cette table, malgre l'usage reel de LiteLLM. Alimentee depuis app/workers/tasks.py ;
    le plafond mensuel optionnel par fournisseur est verifie dans
    model_routing_service.get_credentials_for_model() avant chaque appel."""
    __tablename__ = "llm_usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    provider_id = Column(Text, nullable=True)
    model_string = Column(Text, nullable=False)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Numeric(12, 6), nullable=True)
    was_fallback = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSONB, default=dict)
    ip_address = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Text, primary_key=True)  # 'starter', 'pro', 'enterprise', 'custom'
    name = Column(Text, nullable=False)
    price_monthly_cents = Column(Integer, nullable=False, default=0)
    included_dossiers_month = Column(Integer, nullable=False, default=3)
    extra_dossier_price_cents = Column(Integer, nullable=False, default=9900)
    monthly_llm_cost_cap_usd = Column(Numeric(10, 2), nullable=True)  # 02/09 : plafond de cout LLM reel par defaut pour ce forfait (USD), voir billing_service.get_effective_cost_cap_usd
    # 03/09 : verrous de volume/cout complementaires (voir migration 00032) -- protegent
    # la marge sur les axes qui ne sont PAS deja couverts par le plafond de cout LLM :
    # pages ingerees (charge Postgres/pgvector), cout OCR Azure (jamais journalise avant),
    # et frequence d'usage du chat / du connecteur SharePoint.
    included_pages_month = Column(Integer, nullable=True)
    extra_pages_price_cents_per_1000 = Column(Integer, nullable=False, default=500)
    monthly_ocr_cost_cap_usd = Column(Numeric(10, 2), nullable=True)
    included_questions_month = Column(Integer, nullable=True)
    extra_questions_price_cents_per_100 = Column(Integer, nullable=False, default=300)
    included_sharepoint_files_month = Column(Integer, nullable=True)
    extra_sharepoint_files_price_cents_per_100 = Column(Integer, nullable=False, default=400)
    features = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan_id = Column(Text, ForeignKey("subscription_plans.id"), nullable=False)
    status = Column(Text, nullable=False, default="active")  # 'active', 'past_due', 'canceled', 'suspended'
    billing_mode = Column(Text, nullable=False, default="stripe")  # 'stripe', 'manual_enterprise', 'free_trial'
    stripe_customer_id = Column(Text, nullable=True)
    stripe_subscription_id = Column(Text, nullable=True)
    custom_quota_dossiers = Column(Integer, nullable=True)
    custom_llm_cost_cap_usd = Column(Numeric(10, 2), nullable=True)  # 02/09 : surcharge par-tenant du plafond de cout LLM (prioritaire sur SubscriptionPlan.monthly_llm_cost_cap_usd)
    allow_overage = Column(Boolean, default=True, nullable=False)
    # 03/09 : surcharges par-tenant des verrous de volume (miroir de custom_llm_cost_cap_usd)
    custom_pages_month = Column(Integer, nullable=True)
    custom_ocr_cost_cap_usd = Column(Numeric(10, 2), nullable=True)
    custom_questions_month = Column(Integer, nullable=True)
    custom_sharepoint_files_month = Column(Integer, nullable=True)
    allow_page_overage = Column(Boolean, nullable=False, default=True)
    allow_question_overage = Column(Boolean, nullable=False, default=True)
    allow_sharepoint_overage = Column(Boolean, nullable=False, default=True)
    current_period_start = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TenantUsageCounter(Base):
    __tablename__ = "tenant_usage_counters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    dossiers_generated = Column(Integer, default=0, nullable=False)
    sections_generated = Column(Integer, default=0, nullable=False)
    exports_count = Column(Integer, default=0, nullable=False)
    web_searches_count = Column(Integer, default=0, nullable=False)
    # 03/09 : compteurs de volume complementaires (voir migration 00032)
    pages_ingested = Column(Integer, default=0, nullable=False)
    questions_asked = Column(Integer, default=0, nullable=False)
    ocr_pages_azure = Column(Integer, default=0, nullable=False)
    ocr_pages_local = Column(Integer, default=0, nullable=False)
    sharepoint_files_indexed = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class OcrUsageLog(Base):
    """Journal de consommation OCR reelle (03/09, miroir de LlmUsageLog) -- avant cette
    table, aucun cout Azure Document Intelligence n'etait jamais journalise ni plafonne,
    alors que c'est un cout variable reel independant du plafond LLM (voir
    app/services/ocr_cost_service.py)."""
    __tablename__ = "ocr_usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(UUID(as_uuid=True), nullable=True)
    source = Column(Text, nullable=False, default="dce")  # 'dce' | 'knowledge' | 'sharepoint'
    provider = Column(Text, nullable=False)  # 'azure_doc_intelligence' | 'local_pdf_parser'
    pages_local = Column(Integer, nullable=False, default=0)
    pages_azure = Column(Integer, nullable=False, default=0)
    estimated_cost_usd = Column(Numeric(12, 6), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class SharePointConnection(Base):
    """Un connecteur SharePoint par tenant (03/09, Microsoft Graph, client-credentials
    flow). delta_link porte le curseur de synchronisation incrementale -- voir
    app/services/sharepoint_service.py. Les identifiants Azure AD (client_id/secret)
    sont fournis par l'IT du CLIENT, jamais par btpAO."""
    __tablename__ = "sharepoint_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False)
    ms_tenant_id = Column(Text, nullable=False)
    client_id = Column(Text, nullable=False)
    client_secret_encrypted = Column(Text, nullable=False)
    site_url = Column(Text, nullable=False)
    drive_id = Column(Text, nullable=True)
    selected_folder_path = Column(Text, nullable=False, default="/")
    allowed_extensions = Column(ARRAY(Text), nullable=False, default=lambda: ["pdf", "docx", "xlsx"])
    max_file_size_bytes = Column(Numeric, nullable=False, default=52428800)
    status = Column(Text, nullable=False, default="pending_verification")
    last_error = Column(Text, nullable=True)
    delta_link = Column(Text, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SharePointSyncItem(Base):
    """Un enregistrement par fichier SharePoint deja traite (03/09) -- permet de ne
    reindexer QUE les fichiers nouveaux ou dont le contenu a change (comparaison
    file_hash), meme si Microsoft Graph renvoie l'item dans un delta."""
    __tablename__ = "sharepoint_sync_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("sharepoint_connections.id", ondelete="CASCADE"), nullable=False)
    graph_item_id = Column(Text, nullable=False)
    filename = Column(Text, nullable=False)
    file_hash = Column(Text, nullable=True)
    size_bytes = Column(Numeric, nullable=True)
    company_asset_id = Column(UUID(as_uuid=True), ForeignKey("company_assets.id", ondelete="SET NULL"), nullable=True)
    status = Column(Text, nullable=False, default="indexed")
    status_detail = Column(Text, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email = Column(Text, nullable=False)
    token_hash = Column(Text, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)







