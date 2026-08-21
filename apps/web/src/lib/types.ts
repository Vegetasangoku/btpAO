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

export const LLM_MODEL_TIERS = [
  {
    id: 'economique',
    name: 'Économique — Claude Haiku 4.5',
    pricing: '≈ 1 $ / 5 $ par million de tokens',
    display_label: 'Économique — Claude Haiku 4.5 (≈ 1 $ / 5 $ par million de tokens)',
  },
  {
    id: 'equilibre',
    name: 'Équilibré — Claude Sonnet 5',
    pricing: '≈ 2 $ / 10 $ par million de tokens',
    display_label: 'Équilibré — Claude Sonnet 5 (≈ 2 $ / 10 $ par million de tokens)',
  },
  {
    id: 'avance',
    name: 'Avancé — Claude Opus 5',
    pricing: '≈ 5 $ / 25 $ par million de tokens',
    display_label: 'Avancé — Claude Opus 5 (≈ 5 $ / 25 $ par million de tokens)',
  },
  {
    id: 'maximum',
    name: 'Maximum — Claude Fable 5',
    pricing: '≈ 10 $ / 50 $ par million de tokens',
    display_label: 'Maximum — Claude Fable 5 (≈ 10 $ / 50 $ par million de tokens)',
  },
] as const;

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
  status: 'draft' | 'dce_parsed' | 'decisions_saved' | 'generating' | 'review' | 'validated' | 'exported';
  budget_estimate?: number;
  submission_deadline?: string;
  scoring_notes: {
    technical_weight: number;
    price_weight: number;
  };
  created_at: string;
  updated_at: string;
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
  status: 'generating' | 'generated' | 'edited' | 'validated';
  locked_for_export: boolean;
  updated_at: string;
}

export interface CompanyAsset {
  id: string;
  tenant_id: string;
  category: 'reference_chantier' | 'materiel_engins' | 'certificat_qualibat' | 'cv_encadrement' | 'demarche_rse' | 'securite_ppsps';
  title: string;
  description?: string;
  s3_url?: string;
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
  status: 'passed' | 'warning' | 'failed';
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
  evaluated_by?: string;
  created_at: string;
  updated_at: string;
}

