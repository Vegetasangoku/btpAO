"""
Pydantic v2 Models & Data Transfer Objects (DTOs) for btpAO
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Tenant & Auth Models
# -----------------------------------------------------------------------------
class TenantBranding(BaseModel):
    primary_color: str = "#0ea5e9"
    secondary_color: str = "#0f172a"
    font_family: str = "Inter"
    logo_url: Optional[str] = None
    company_name: str = "BTP Construction SAS"
    header_text: str = "Mémoire Technique Justificatif"
    footer_text: str = "Document confidentiel soumis dans le cadre de l'Appel d'Offres"


class TenantOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    branding_config: TenantBranding = Field(default_factory=TenantBranding)
    created_at: datetime


class UserProfileOut(BaseModel):
    id: str
    tenant_id: str
    email: str
    full_name: Optional[str] = None
    role: str
    avatar_url: Optional[str] = None


class TeamMemberOut(BaseModel):
    id: str
    tenant_id: str
    email: str
    full_name: Optional[str] = None
    role: str
    avatar_url: Optional[str] = None
    created_at: datetime


class TeamMemberUpdateRole(BaseModel):
    role: str  # 'owner', 'member', 'read_only', 'conducteur_travaux', 'chiffreur'


class TeamInvitationCreate(BaseModel):
    email: str
    role: Optional[str] = "member"


class TeamInvitationOut(BaseModel):
    id: str
    tenant_id: str
    email: str
    role: str
    invitation_token: str
    status: str
    invited_by: Optional[str] = None
    expires_at: datetime
    created_at: datetime


class TeamInvitationAccept(BaseModel):
    token: str
    full_name: Optional[str] = None
    password: Optional[str] = None



# -----------------------------------------------------------------------------
# Project Models
# -----------------------------------------------------------------------------
class ProjectCreate(BaseModel):
    title: str = Field(..., example="Construction du Groupe Scolaire & Gymnase HQE")
    reference_code: str = Field(..., example="AO-2026-MGP-089")
    client_name: str = Field(..., example="Métropole du Grand Paris")
    location: Optional[str] = Field(default="Saint-Denis (93)", example="Saint-Denis (93)")
    lot_number: Optional[str] = Field(default="Lot 01 - Gros Œuvre", example="Lot 01 - Gros Œuvre")
    budget_estimate: Optional[float] = Field(default=3500000.0, example=3500000.0)
    submission_deadline: Optional[datetime] = None
    scoring_notes: Dict[str, Any] = Field(
        default_factory=lambda: {"technical_weight": 60, "price_weight": 40}
    )
    strategic_directives: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    reference_code: Optional[str] = None
    client_name: Optional[str] = None
    location: Optional[str] = None
    lot_number: Optional[str] = None
    status: Optional[str] = None
    budget_estimate: Optional[float] = None
    submission_deadline: Optional[datetime] = None
    scoring_notes: Optional[Dict[str, Any]] = None
    strategic_directives: Optional[str] = None


class GoNoGoSummaryOut(BaseModel):
    id: Optional[str] = None
    recommendation: str  # "GO", "RESERVES", "NO_GO"
    score: float
    summary: str
    mandatory_criteria_met: bool = True
    blocking_issues: List[str] = Field(default_factory=list)
    completion_rate: Optional[float] = None
    has_sufficient_data: bool = True


class ProjectOut(BaseModel):
    id: str
    tenant_id: str
    title: str
    reference_code: str
    client_name: str
    location: Optional[str]
    lot_number: Optional[str]
    status: str
    budget_estimate: Optional[float]
    submission_deadline: Optional[datetime]
    scoring_notes: Dict[str, Any]
    strategic_directives: Optional[str] = None
    outcome_status: str = "pending"
    buyer_feedback: Dict[str, Any] = Field(default_factory=dict)
    outcome_recorded_at: Optional[datetime] = None
    go_no_go: Optional[GoNoGoSummaryOut] = None
    created_at: datetime
    updated_at: datetime


class BuyerFeedbackPayload(BaseModel):
    technical_score: Optional[float] = None
    price_score: Optional[float] = None
    points_forts: List[str] = Field(default_factory=list)
    points_faibles: List[str] = Field(default_factory=list)
    general_comments: Optional[str] = None
    winning_bidder: Optional[str] = None
    winning_amount: Optional[float] = None


class ProjectOutcomeRecordPayload(BaseModel):
    outcome_status: str  # 'won', 'lost', 'withdrawn', 'pending'
    buyer_feedback: Optional[BuyerFeedbackPayload] = None
    notes: Optional[str] = None


class TenantLearningOut(BaseModel):
    id: str
    tenant_id: str
    project_id: Optional[str] = None
    category: str
    title: str
    learning_insight: Optional[str] = ""
    actionable_directive: Optional[str] = ""
    section_type: Optional[str] = None
    learned_content: Optional[str] = None
    source_diff: Dict[str, Any] = Field(default_factory=dict)
    source_outcome: str = "manual"
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class CreateTenantLearningRequest(BaseModel):
    title: str
    category: Optional[str] = "methodology"
    section_type: Optional[str] = None
    project_id: Optional[str] = None
    learned_content: str
    actionable_directive: Optional[str] = None
    learning_insight: Optional[str] = None
    source_diff: Optional[Dict[str, Any]] = None
    source_outcome: Optional[str] = "manual"


class TenantLearningUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    learning_insight: Optional[str] = None
    actionable_directive: Optional[str] = None
    is_active: Optional[bool] = None


class ProjectHistoryItemOut(BaseModel):
    id: str
    title: str
    reference_code: str
    client_name: str
    lot_number: Optional[str] = None
    budget_estimate: Optional[float] = None
    submission_deadline: Optional[datetime] = None
    status: str
    outcome_status: str
    buyer_feedback: Dict[str, Any] = Field(default_factory=dict)
    outcome_recorded_at: Optional[datetime] = None
    created_at: datetime


class ProjectsHistoryResponse(BaseModel):
    total_projects: int
    closed_projects: int
    won_count: int
    lost_count: int
    pending_count: int
    win_rate_percentage: Optional[float] = None  # None if closed_projects == 0
    win_rate_display: str  # "Données insuffisantes" or "66.7%"
    projects: List[ProjectHistoryItemOut]



# -----------------------------------------------------------------------------
# DCE & Criteria Models
# -----------------------------------------------------------------------------
class DCECriterion(BaseModel):
    id: Optional[str] = None
    criterion_title: str
    weight_percentage: float = 0.0
    description: str
    key_expectations: List[str] = Field(default_factory=list)
    required_evidence: List[str] = Field(default_factory=list)
    mandatory: bool = True
    extracted_from: str = "Règlement de Consultation (RC)"


class DCEUploadResponse(BaseModel):
    document_id: str
    project_id: str
    filename: str
    s3_key: str
    status: str
    message: str


class DCEParsingResult(BaseModel):
    document_id: str
    status: str
    chunks_indexed: int
    extracted_criteria: List[DCECriterion]
    summary: str


class GoNoGoFactor(BaseModel):
    category: str  # "qualifications", "deadline_workload", "mandatory_criteria", "historical_win_rate"
    title: str
    status: str  # "ok", "warning", "blocking", "missing_data"
    impact: str  # "positive", "neutral", "negative", "critical"
    detail: str
    recommendation: Optional[str] = None


class GoNoGoAnalysisOut(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    recommendation: str  # "GO", "RESERVES", "NO_GO"
    score: float  # 0 to 100
    summary: str
    factors: List[GoNoGoFactor]
    mandatory_criteria_met: bool
    blocking_issues: List[str] = Field(default_factory=list)
    completion_rate: Optional[float] = None
    has_sufficient_data: bool = True
    evaluated_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime



# -----------------------------------------------------------------------------
# Project Decisions (Formulaire Conducteur de Travaux)
# -----------------------------------------------------------------------------
class CadreEquipe(BaseModel):
    nom: str = Field(..., example="Jean-Marc Alibert")
    role: str = Field(..., example="Directeur de Projet / Conducteur Principal")
    experience_ans: int = Field(default=10, example=15)
    presence_hebdo_pct: int = Field(default=100, example=100)
    qualif: Optional[str] = Field(default="Ingénieur ESTP", example="Ingénieur ESTP")


class PhaseChantier(BaseModel):
    phase: str = Field(..., example="1. Installation de chantier, PIC & Terrassements")
    duree_semaines: int = Field(..., example=4)
    jalon: str = Field(..., example="Plateforme opérationnelle")


class ProjectDecisionsForm(BaseModel):
    delai_mois: int = Field(default=6, example=6)
    date_demarrage: Optional[str] = Field(default="2026-10-01", example="2026-10-01")
    materiel_principal: str = Field(
        default="Grue à tour Potain 50m, 2 pelles Liebherr 22t, centrale à coulis et banches manuportables Alphi",
        example="Grue à tour Potain 50m, 2 pelles Liebherr 22t, centrale à coulis et banches manuportables Alphi"
    )
    travail_de_nuit: bool = Field(default=False, example=False)
    gestion_dechets: str = Field(
        default="Tri sélectif 5 flux in situ avec valorisation 88% en filière locale agréée Paprec/Veolia à 12 km",
        example="Tri sélectif 5 flux in situ avec valorisation 88% en filière locale agréée Paprec/Veolia à 12 km"
    )
    equipe_cadres: List[CadreEquipe] = Field(
        default_factory=lambda: [
            CadreEquipe(nom="Jean-Marc Alibert", role="Directeur de Projet & Conducteur Principal", experience_ans=15, presence_hebdo_pct=100),
            CadreEquipe(nom="Sébastien Vasseur", role="Chef de Chantier Gros Œuvre", experience_ans=12, presence_hebdo_pct=100),
            CadreEquipe(nom="Chloé Fontaine", role="Ingénieur QSE & Environnement", experience_ans=7, presence_hebdo_pct=50)
        ]
    )
    mesures_securite: str = Field(
        default="PPSPS strict, accueil sécurité avec badge biométrique, protection collective intégrée sur banches, défibrillateur et 4 SST",
        example="PPSPS strict, accueil sécurité avec badge biométrique, protection collective intégrée sur banches, défibrillateur et 4 SST"
    )
    demarche_rse_environnement: str = Field(
        default="Béton bas carbone CEM III/A (-42% CO2), circuit fermé de recyclage des eaux de lavage toupies, charte chantier vert",
        example="Béton bas carbone CEM III/A (-42% CO2), circuit fermé de recyclage des eaux de lavage toupies, charte chantier vert"
    )
    phasage_travaux: List[PhaseChantier] = Field(
        default_factory=lambda: [
            PhaseChantier(phase="1. Installation de chantier, PIC & Terrassements", duree_semaines=4, jalon="Plateforme opérationnelle"),
            PhaseChantier(phase="2. Fondations profondes et longrines", duree_semaines=4, jalon="Réception plateforme géotechnique"),
            PhaseChantier(phase="3. Infrastructure & Superstructure R+2 Gros Œuvre", duree_semaines=10, jalon="Hors d'eau / Hors d'air structurel"),
            PhaseChantier(phase="4. Réseaux enterrés, VRD & Aménagements extérieurs", duree_semaines=4, jalon="Essais d'étanchéité & OPR"),
            PhaseChantier(phase="5. Repli de chantier, levée des réserves & Livraison", duree_semaines=2, jalon="Parfait Achèvement & Remise des clés")
        ]
    )


# -----------------------------------------------------------------------------
# Section Generation & AI Models
# -----------------------------------------------------------------------------
class GenerateSectionRequest(BaseModel):
    project_id: str
    section_key: str = Field(..., example="moyens_humains") # 'moyens_humains', 'moyens_materiels', 'methodologie_phasage', 'qse_environnement', 'securite_ppsps'
    custom_instructions: Optional[str] = None
    target_word_count: int = Field(default=600, ge=200, le=3000)
    mode: Optional[str] = "standard"  # 'standard', 'prefill_draft'


class GeneratedSectionOut(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    section_key: str
    title: str
    order_index: int
    content_html: str
    content_json: Dict[str, Any]
    visual_placeholders: List[Dict[str, Any]] = Field(default_factory=list)
    compliance_score: float = 100.0
    compliance_notes: Optional[str] = None
    status: str
    prefill_source: List[Dict[str, Any]] = Field(default_factory=list)
    is_prefilled: bool = False
    locked_for_export: bool = False
    updated_at: datetime


class LearningProposal(BaseModel):
    section_type: str
    summary: str
    suggested_content: str
    diff_percentage: float = 0.0


class UpdateSectionResponse(BaseModel):
    success: bool
    section: GeneratedSectionOut
    learning_opportunity: bool = False
    learning_proposal: Optional[LearningProposal] = None


class UpdateSectionContent(BaseModel):
    content_html: str
    content_json: Optional[Dict[str, Any]] = None
    status: Optional[str] = "edited"
    locked_for_export: Optional[bool] = None
    change_summary: Optional[str] = None


class GeneratedSectionVersionOut(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    section_id: str
    version_number: int
    title: str
    content_html: str
    content_json: Dict[str, Any] = Field(default_factory=dict)
    compliance_score: float = 100.0
    compliance_notes: Optional[str] = None
    status: str
    created_by: Optional[str] = None
    created_at: datetime
    change_summary: Optional[str] = None



# -----------------------------------------------------------------------------
# Visuals & Graphics Models
# -----------------------------------------------------------------------------
class GanttGenerationRequest(BaseModel):
    project_id: str
    project_title: Optional[str] = "Chantier BTP"
    phases: Optional[List[PhaseChantier]] = None
    start_date: Optional[str] = "2026-10-01"


# --- Interactive Gantt tasks (Batch 11, cahier des charges majeur) ---
class GanttTaskBase(BaseModel):
    name: str
    start_date: str = Field(..., example="2026-10-01")
    end_date: str = Field(..., example="2026-10-08")
    progress: int = Field(default=0, ge=0, le=100)
    is_milestone: bool = False
    milestone_label: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)


class GanttTaskCreate(GanttTaskBase):
    pass


class GanttTaskUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    is_milestone: Optional[bool] = None
    milestone_label: Optional[str] = None
    depends_on: Optional[List[str]] = None


class GanttTaskOut(GanttTaskBase):
    id: str
    project_id: str
    sequence: int
    is_critical: bool = False


class DiagramGenerationRequest(BaseModel):
    project_id: str
    diagram_type: str = "organigramme" # 'organigramme', 'traffic_flow', 'waste_management'
    title: Optional[str] = "Organigramme d'Encadrement Chantier"
    nodes: Optional[List[Dict[str, Any]]] = None


# -----------------------------------------------------------------------------
# Export Models
# -----------------------------------------------------------------------------
class ExportDocumentRequest(BaseModel):
    project_id: str
    format: str = Field(default="docx", example="docx") # 'docx', 'pdf', 'both'
    template_id: Optional[str] = None
    include_gantt: bool = True
    include_organigramme: bool = True


class ExportJobOut(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    format: str
    status: str
    s3_docx_url: Optional[str] = None
    s3_pdf_url: Optional[str] = None
    file_size_bytes: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Knowledge Base Models
# -----------------------------------------------------------------------------
class CompanyAssetCreate(BaseModel):
    category: str # 'reference_chantier', 'materiel_engins', 'certificat_qualibat', 'cv_encadrement', 'demarche_rse'
    title: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class CompanyAssetOut(BaseModel):
    id: str
    tenant_id: str
    category: str
    title: str
    description: Optional[str]
    s3_url: Optional[str]
    source_type: str = "manual_upload"
    collected_at: Optional[datetime] = None
    validated_by_user: bool = True
    tags: List[str] = Field(default_factory=list)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class KnowledgeWebSourceInput(BaseModel):
    url: str
    title: Optional[str] = None
    category: Optional[str] = "web_source"


class KnowledgeUploadResponse(BaseModel):
    success: bool
    asset_id: str
    title: str
    category: str
    status: str
    file_size_bytes: int
    word_count: int
    message: str


class KnowledgeStatsOut(BaseModel):
    total_assets: int
    max_allowed: Optional[int]
    plan: str
    category_counts: Dict[str, int]


# -----------------------------------------------------------------------------
# Company Profile Bootstrap & Reference URLs Models
# -----------------------------------------------------------------------------
class CompanyBootstrapTriggerRequest(BaseModel):
    company_name: str
    siret: Optional[str] = None
    reference_urls: List[str] = Field(default_factory=list)


class CompanyBootstrapRunOut(BaseModel):
    id: str
    tenant_id: str
    status: str
    triggered_by: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    sources_found: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None
    created_at: datetime
    extracted_assets: List[CompanyAssetOut] = Field(default_factory=list)


class CompanyAssetValidationRequest(BaseModel):
    validated: bool = True
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None


class TenantReferenceUrlCreate(BaseModel):
    url: str
    label: Optional[str] = None


class TenantReferenceUrlOut(BaseModel):
    id: str
    tenant_id: str
    url: str
    label: Optional[str] = None
    added_by: Optional[str] = None
    added_at: datetime
    last_fetched_at: Optional[datetime] = None
    status: str = "active"


