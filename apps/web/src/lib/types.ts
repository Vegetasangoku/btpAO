/**
 * TypeScript Type Definitions for btpAO Frontend
 */

export interface TenantBranding {
  primary_color: string;
  secondary_color: string;
  font_family: string;
  logo_url?: string;
  company_name: string;
  header_text: string;
  footer_text: string;
}

export type ProviderZone = 'UE' | 'US' | 'Chine' | 'autre' | 'non-verifie';

export const RGPD_NON_EU_WARNING = "Hébergement hors UE — conformité RGPD non confirmée, voir avec un juriste avant usage sur des données clients réelles";

export interface CustomLLMProvider {
  id: string;
  name: string;
  litellm_id: string;
  api_key?: string;
  api_base?: string;
  zone: ProviderZone;
  is_non_eu?: boolean;
  warning_message?: string | null;
  enabled: boolean;
  test_status?: 'success' | 'error' | 'untested';
  last_tested_at?: string | null;
  last_latency_ms?: number | null;
  last_error_message?: string | null;
}

export const LLM_MODEL_TIERS = [
  {
    id: 'economique',
    name: 'Économique — Claude Haiku 4.5',
    pricing: '≈ 1 $ / 5 $ par million de tokens',
    display_label: 'Économique — Claude Haiku 4.5 (≈ 1 $ / 5 $ par million de tokens)',
    zone: 'US' as ProviderZone,
    is_non_eu: false,
    warning_message: null,
  },
  {
    id: 'equilibre',
    name: 'Équilibré — Claude Sonnet 5',
    pricing: '≈ 2 $ / 10 $ par million de tokens',
    display_label: 'Équilibré — Claude Sonnet 5 (≈ 2 $ / 10 $ par million de tokens)',
    zone: 'US' as ProviderZone,
    is_non_eu: false,
    warning_message: null,
  },
  {
    id: 'avance',
    name: 'Avancé — Claude Opus 5',
    pricing: '≈ 5 $ / 25 $ par million de tokens',
    display_label: 'Avancé — Claude Opus 5 (≈ 5 $ / 25 $ par million de tokens)',
    zone: 'US' as ProviderZone,
    is_non_eu: false,
    warning_message: null,
  },
  {
    id: 'maximum',
    name: 'Maximum — Claude Fable 5',
    pricing: '≈ 10 $ / 50 $ par million de tokens',
    display_label: 'Maximum — Claude Fable 5 (≈ 10 $ / 50 $ par million de tokens)',
    zone: 'US' as ProviderZone,
    is_non_eu: false,
    warning_message: null,
  },
];



export interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  country_code?: string;
  siret?: string;
  contact_email?: string;
  llm_provider?: string;
  llm_model?: string;
  llm_model_tier?: string;
  users_count?: number;
  projects_count?: number;
  active_projects_count?: number;
  used_this_month?: number;
  monthly_limit?: number;
  branding_config?: any;
  created_at: string;
  updated_at?: string;
}

export interface CreateTenantInput {
  name: string;
  slug?: string;
  siret?: string;
  contact_email?: string;
  plan?: string;
  country_code?: string;
  llm_provider?: string;
  llm_model?: string;
  llm_model_tier?: string;
  model_routing_config?: any;
  branding_config?: any;
}

export interface UpdateTenantInput {
  name?: string;
  siret?: string;
  contact_email?: string;
  plan?: string;
  country_code?: string;
  llm_provider?: string;
  llm_model?: string;
  llm_model_tier?: string;
  branding_config?: any;
}



export interface UserProfile {
  id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  role: string;
  avatar_url?: string;
}

export interface Project {
  id: string;
  tenant_id: string;
  title: string;
  reference_code: string;
  client_name: string;
  location?: string;
  lot_number?: string;
  status: 'draft' | 'dce_parsed' | 'decisions_saved' | 'generating' | 'review' | 'validated' | 'exported' | 'in_progress' | 'completed' | string;
  outcome_status?: 'pending' | 'submitted' | 'won' | 'lost' | string;
  budget_estimate?: number;
  estimated_budget?: number;
  submission_deadline?: string;
  scoring_notes?: {
    technical_weight: number;
    price_weight: number;
  };
  strategic_directives?: string;
  go_no_go?: GoNoGoAnalysis | null;
  created_at: string;
  updated_at?: string;
}

export interface DCECriterion {
  id?: string;
  criterion_title: string;
  weight_percentage: number;
  description: string;
  key_expectations: string[];
  required_evidence: string[];
  mandatory: boolean;
  extracted_from: string;
}

export interface CadreEquipe {
  nom: string;
  role: string;
  experience_ans: number;
  presence_hebdo_pct: number;
  qualif?: string;
}

export interface PhaseChantier {
  phase: string;
  duree_semaines: number;
  jalon: string;
}

export interface ProjectDecisionsForm {
  delai_mois: number;
  date_demarrage?: string;
  materiel_principal: string;
  travail_de_nuit: boolean;
  gestion_dechets: string;
  equipe_cadres: CadreEquipe[];
  mesures_securite: string;
  demarche_rse_environnement: string;
  phasage_travaux: PhaseChantier[];
}

export interface GeneratedSection {
  id: string;
  tenant_id: string;
  project_id: string;
  section_key: string;
  title: string;
  order_index: number;
  content_html: string;
  content_json: Record<string, any>;
  visual_placeholders: string[];
  compliance_score: number;
  compliance_notes?: string;
  status: 'generating' | 'generated' | 'edited' | 'validated' | 'processing' | 'missing_data' | 'prefilled_draft' | 'restored' | 'failed' | string;
  locked_for_export: boolean;
  updated_at: string;
}

export interface CompanyAsset {
  id: string;
  tenant_id: string;
  category: 'reference_chantier' | 'materiel_engins' | 'certificat_qualibat' | 'cv_encadrement' | 'demarche_rse' | 'securite_ppsps' | 'web_source' | 'general' | string;
  title: string;
  description?: string;
  s3_url?: string;
  source_type?: 'manual_upload' | 'web_auto_bootstrap' | 'learned_adjustment' | 'tenant_provided_url' | string;
  collected_at?: string;
  validated_by_user?: boolean;
  tags: string[];
  metadata_json: Record<string, any>;
  created_at: string;
}


export interface ExportJob {
  id: string;
  tenant_id: string;
  project_id: string;
  format: 'docx' | 'pdf' | 'both';
  status: 'pending' | 'generating' | 'completed' | 'failed';
  s3_docx_url?: string;
  s3_pdf_url?: string;
  file_size_bytes: number;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface GoNoGoFactor {
  category: string;
  title: string;
  status: 'ok' | 'warning' | 'blocking' | 'missing_data' | string;
  impact: 'positive' | 'neutral' | 'negative' | 'critical';
  detail: string;
  recommendation?: string;
}

export interface GoNoGoAnalysis {
  id: string;
  tenant_id: string;
  project_id: string;
  recommendation: 'GO' | 'RESERVES' | 'NO-GO' | 'RÉSERVES';
  score: number;
  summary: string;
  factors: GoNoGoFactor[];
  mandatory_criteria_met: boolean;
  blocking_issues: string[];
  completion_rate?: number;
  has_sufficient_data?: boolean;
  evaluated_by?: string;
  created_at: string;
  updated_at: string;
}

export interface PlatformLLMKeys {

  anthropic_api_key_configured: boolean;
  anthropic_api_key_masked: string;
  openai_api_key_configured: boolean;
  openai_api_key_masked: string;
  mistral_api_key_configured: boolean;
  mistral_api_key_masked: string;
  custom_providers?: CustomLLMProvider[];
  encryption_status?: string;
  embedding_model: string;
  default_llm_tier: string;
  available_tiers: Record<string, any>;
}

export type TeamRole = 'owner' | 'conducteur_travaux' | 'chiffreur' | 'member' | 'read_only';

export interface TeamMember {
  id: string;
  tenant_id: string;
  email: string;
  full_name?: string;
  name?: string;
  role: TeamRole;
  avatar_url?: string;
  created_at: string;
  activeProjects?: number;
}

export interface TeamInvitation {
  id: string;
  tenant_id: string;
  email: string;
  role: TeamRole;
  invitation_token: string;
  token?: string;
  status: 'pending' | 'accepted' | 'revoked' | 'expired';
  invited_by?: string;
  expires_at: string;
  created_at: string;
}

export interface SuggestedTemplate {
  has_template: boolean;
  source_type?: 'export_template' | 'recent_dossier' | 'reference_document' | null;
  source?: string;
  name?: string | null;
  title?: string | null;
  description?: string | null;
  reason?: string | null;
  id?: string | null;
  created_at?: string | null;
}

// Interactive Gantt task (Batch 11, cahier des charges majeur)
export interface GanttTask {
  id: string;
  project_id: string;
  name: string;
  start_date: string;
  end_date: string;
  progress: number;
  sequence: number;
  is_milestone: boolean;
  milestone_label: string | null;
  depends_on: string[];
  is_critical: boolean;
}



