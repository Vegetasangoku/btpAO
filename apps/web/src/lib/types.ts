/**
 * TypeScript Type Definitions for btpAO Frontend
 */

export interface CountryOption {
  country_code: string;
  country_name: string;
  currency?: string | null;
}

export interface CountryDetectionSignal {
  country_code: string;
  marker: string;
  where: string;
  weight: number;
  kind: string;
}

/** Pays du MARCHE applique a un dossier (04/09) -- distinct du pays de l'entreprise. */
export interface ProjectCountryState {
  project_id: string;
  country_code: string | null;
  effective_country_code: string;
  is_tenant_fallback: boolean;
  tenant_country_code: string;
  detection: {
    detected_code?: string | null;
    confidence?: 'high' | 'medium' | 'low' | 'none';
    method?: string;
    reason?: string;
    signals?: CountryDetectionSignal[];
    scores?: Record<string, number>;
    auto_applied?: boolean;
    overridden_by_user?: boolean;
    detected_at?: string;
  };
  available_countries: CountryOption[];
}

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
  monthly_budget_usd?: number | null;
}

/* Paliers de qualité proposés dans l'admin. Repli d'affichage uniquement : la source
   de vérité est le backend (app/services/llm_reference_catalog.py), interrogé via
   /admin/llm-keys → available_tiers. Prix relevés le 2026-09-02 sur les pages
   tarifaires officielles des fournisseurs. */
export const LLM_MODEL_TIERS = [
  {
    id: 'gratuit',
    name: 'Gratuit — Gemini 3.8 Flash',
    pricing: 'inclus dans le palier gratuit du fournisseur',
    display_label: 'Gratuit — Gemini 3.8 Flash (essais et recette, quotas gratuits Google AI Studio)',
    zone: 'US' as ProviderZone,
    is_non_eu: false,
    warning_message: null,
  },
  {
    id: 'economique',
    name: 'Économique — Claude Haiku 4.5',
    pricing: '1.00 $ / 5.00 $ par million de tokens',
    display_label: 'Économique — Claude Haiku 4.5 (extraction rapide des pièces du DCE)',
    zone: 'US' as ProviderZone,
    is_non_eu: false,
    warning_message: null,
  },
  {
    id: 'souverain',
    name: 'Souverain UE — Mistral Large 3',
    pricing: '0.50 $ / 1.50 $ par million de tokens',
    display_label: 'Souverain UE — Mistral Large 3 (marchés publics, données hébergées dans l’Union européenne)',
    zone: 'UE' as ProviderZone,
    is_non_eu: false,
    warning_message: null,
  },
  {
    id: 'equilibre',
    name: 'Équilibré — Claude Sonnet 5',
    pricing: '2.00 $ / 10.00 $ par million de tokens',
    display_label: 'Équilibré — Claude Sonnet 5 (rédaction du mémoire technique au quotidien)',
    zone: 'US' as ProviderZone,
    is_non_eu: false,
    warning_message: null,
  },
  {
    id: 'avance',
    name: 'Avancé — Claude Opus 5',
    pricing: '5.00 $ / 25.00 $ par million de tokens',
    display_label: 'Avancé — Claude Opus 5 (analyse juridique et pièces de marché complexes)',
    zone: 'US' as ProviderZone,
    is_non_eu: false,
    warning_message: null,
  },
  {
    id: 'maximum',
    name: 'Maximum — Claude Fable 5.1',
    pricing: '10.00 $ / 50.00 $ par million de tokens',
    display_label: 'Maximum — Claude Fable 5.1 (dossiers à fort enjeu, raisonnement long)',
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
  llm_fallback_tier?: string;
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
  llm_fallback_tier?: string;
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
  llm_fallback_tier?: string;
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
  output_language?: 'fr' | 'en' | 'ar' | string;
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
  default_fallback_tier?: string;
  available_tiers: Record<string, any>;
  model_tier_overrides?: Record<string, string>;
}

// 29/08 : catalogue de modèles en lecture seule, synchronisé depuis OpenRouter --
// référence (liste à jour, prix, dépréciation), n'affecte pas le chemin d'appel réel.
export interface LlmCatalogModelEntry {
  id: string;
  external_id: string;
  display_name: string | null;
  provider_slug: string | null;
  context_length: number | null;
  pricing_prompt_per_million: number | null;
  pricing_completion_per_million: number | null;
  is_moderated: boolean;
  expiration_date: string | null;
  is_active: boolean;
  first_seen_at: string | null;
  last_seen_at: string | null;
  source?: string | null;
  free_tier?: boolean;
}

/* `source` vaut 'reference_catalog' pour les modèles issus du socle daté relevé sur
   les pages tarifaires officielles ; les autres viennent de la base LiteLLM embarquée
   ou d'OpenRouter, et peuvent donc encore lister des générations retirées. */
export interface LlmCatalogResponse {
  models: LlmCatalogModelEntry[];
  total: number;
  last_synced_at: string | null;
}

export interface LlmCatalogSyncResult {
  synced_at: string;
  total_seen: number;
  created: number;
  updated: number;
  deactivated: number;
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

export interface OrganigrammeNode {
  id: string;
  project_id: string;
  nom: string;
  role: string;
  experience_ans: number;
  presence_hebdo_pct: number;
  qualif: string | null;
  sequence: number;
}





/* ── Plafonds de dépense IA ────────────────────────────────────────────────
   Trois niveaux indépendants : fournisseur d'API, forfait, client. Les montants
   circulent en dollars (devise de facturation des fournisseurs) ; l'équivalent en
   euros est calculé côté serveur avec le taux saisi par l'administrateur. */

export type CostLimitState = 'ok' | 'alerte' | 'bloque' | 'sans_plafond';

export interface CostLimitProviderRow {
  id: string;
  name: string;
  litellm_id: string | null;
  zone: string | null;
  is_non_eu: boolean;
  enabled: boolean;
  has_api_key: boolean;
  cap_usd: number | null;
  cap_eur: number | null;
  spend_usd: number;
  spend_eur: number | null;
  state: CostLimitState;
}

export interface CostLimitPlanRow {
  id: string;
  name: string;
  price_monthly_eur: number;
  included_dossiers_month: number;
  tenant_count: number;
  cap_usd: number | null;
  cap_eur: number | null;
  recommended_cap_usd: number;
  recommended_cap_eur: number | null;
  spend_usd: number;
  is_configured: boolean;
}

export interface CostLimitTenantRow {
  id: string;
  name: string;
  plan_id: string;
  status: string;
  custom_cap_usd: number | null;
  custom_cap_eur: number | null;
  inherited_cap_usd: number | null;
  effective_cap_usd: number | null;
  effective_cap_eur: number | null;
  source: 'client' | 'forfait' | 'aucun';
  spend_usd: number;
  spend_eur: number | null;
  state: CostLimitState;
}

export interface CostLimitsOverview {
  settings: {
    display_currency: 'EUR' | 'USD';
    eur_usd_rate: number;
    eur_usd_rate_updated_at: string | null;
    target_llm_share: number;
    alert_threshold_pct: number;
    rate_source: string;
  };
  period_start: string;
  totals: {
    spend_usd: number;
    spend_eur: number | null;
    providers_without_cap: number;
    plans_without_cap: number;
    tenants_without_cap: number;
    tenants_blocked: number;
  };
  providers: CostLimitProviderRow[];
  plans: CostLimitPlanRow[];
  tenants: CostLimitTenantRow[];
}
