import { resoudreEspace } from '@/lib/espace-actif';
/**
 * Typed API Client for btpAO FastAPI Backend
 */
import {
  CompanyAsset,
  DCECriterion,
  ExportJob,
  GeneratedSection,
  GoNoGoAnalysis,
  Project,
  ProjectDecisionsForm,
  Tenant,
  CreateTenantInput,
  UserProfile,
  PlatformLLMKeys,
  CustomLLMProvider,
  LlmCatalogResponse,
  LlmCatalogSyncResult,
  CostLimitsOverview,
  TeamMember,
  TeamInvitation,
  SuggestedTemplate,
  GanttTask,
  GanttSettings,
  GanttDetailReport,
  CadreRapport,
  PiecesRapport,
  OrganigrammeNode,
  ProjectCountryState,
} from './types';




import { supabase } from './supabase/client';

/** Error thrown by fetcher()/fetchAuthenticatedBlobUrl() that preserves the real HTTP
 *  status code alongside the human-readable message. Before this, fetcher() discarded
 *  the numeric status whenever the backend response body had a `detail` field (the
 *  normal FastAPI error shape), so callers could never reliably tell "not authenticated"
 *  (401) apart from "server/permission error" (403/500/...) -- every failure collapsed
 *  into the same generic Error(message). That is how a real backend 500 (e.g. a missing
 *  Postgres GRANT) could only ever be displayed as a hedged "session expired or service
 *  unavailable" message instead of the precise one each case deserves. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

const rawApiUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_BASE_URL = rawApiUrl.endsWith('/api') ? rawApiUrl : `${rawApiUrl}/api`;
const DEMO_TENANT_ID = '11111111-1111-1111-1111-111111111111';


/**
 * URL absolue vers une route de l'API, a partir d'un chemin SANS le prefixe "/api".
 *
 * Corrige une classe de bug constatee le 04/09 : NEXT_PUBLIC_API_URL contient deja "/api"
 * dans ce deploiement, et les composants qui concatenaient "/api/visuals/file/..." a la
 * main produisaient "/api/api/visuals/file/..." -> 404. Le PNG etait pourtant bien genere
 * (179 Ko ecrits, cle de stockage correcte) : seule l'URL de relecture etait fausse, ce qui
 * faisait croire a une panne de stockage. Le meme defaut touchait l'organigramme ET le Gantt.
 * Passer par ce helper garantit une seule facon de composer ces URLs.
 */
export function buildApiUrl(path: string): string {
  const clean = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${clean}`;
}


/**
 * URL absolue a partir d'un chemin RENVOYE PAR LE BACKEND (ex. s3_docx_url =
 * "/api/export/download/<id>"). Ces chemins portent deja le prefixe "/api".
 *
 * Bug du 11/09 (« Le telechargement n'a pas abouti — HTTP 404 », Word ET PDF) :
 * sous docker-compose, NEXT_PUBLIC_API_URL vaut "http://localhost:8000/api" ; la
 * page d'export concatenait `${NEXT_PUBLIC_API_URL}${s3_docx_url}` et appelait
 * donc "/api/api/export/download/<id>" -> 404, alors que le fichier etait bien
 * compile et stocke. Meme famille que le bug du 04/09 sur les visuels.
 * Toute URL issue d'une reponse API doit passer par ici.
 */
export function resolveBackendPath(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  let clean = path.startsWith('/') ? path : `/${path}`;
  if (clean === '/api' || clean.startsWith('/api/')) clean = clean.slice(4) || '/';
  return buildApiUrl(clean);
}


/**
 * Espace client utilisé quand le jeton de session ne porte aucun tenant.
 *
 * Cet identifiant était écrit en dur à six endroits de ce fichier et à deux
 * endroits de l'API (core/security.py). Conséquence constatée le 10/09 : un
 * compte sans `tenant_id` dans ses claims — typiquement le compte
 * d'administration de la plateforme — atterrissait SILENCIEUSEMENT dans les
 * données du premier client, et tout ce qu'il y faisait s'y écrivait. C'est
 * ce qui donnait l'impression d'un « duplicata » entre deux comptes : il n'y
 * en avait qu'un seul, vu sous deux étiquettes.
 *
 * Le repli est conservé pour ne rien casser en développement, mais il est
 * désormais nommé, commenté, paramétrable par variable d'environnement, et
 * il n'existe qu'ici.
 */
// Plus AUCUN identifiant d'espace écrit en dur. Un compte sans espace n'est
// plus rabattu en silence sur celui du premier client : l'API refuse et le dit.
// Voir lib/espace-actif.ts pour l'historique de ce défaut.

async function fetcher<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  
  // Real Supabase Auth Token Injection
  try {
    const { data } = await supabase.auth.getSession();
    if (data?.session?.access_token) {
      headers.set('Authorization', `Bearer ${data.session.access_token}`);
      const tenantDuJeton = (data.session.user.app_metadata as any)?.tenant_id || (data.session.user.user_metadata as any)?.tenant_id;
      const espace = resoudreEspace(tenantDuJeton);
      if (espace) headers.set('X-Tenant-ID', espace);
    } else if (typeof document !== 'undefined' && process.env.NODE_ENV !== 'production') {
      // E2E test runner sets this cookie deliberately before running tests (non-production only).
      // No hardcoded-secret fallback here: an unauthenticated request must simply stay unauthenticated.
      const match = document.cookie.match(/btp_e2e_secret=([^;]+)/);
      const e2eSecret = match ? match[1] : undefined;
      if (e2eSecret) {
        headers.set('x-e2e-secret', e2eSecret);
        const espaceE2E = resoudreEspace(null);
        if (espaceE2E) headers.set('X-Tenant-ID', espaceE2E);
      }
    }

    if (!headers.has('Authorization') && typeof window !== 'undefined') {
      const stored = localStorage.getItem('btp_auth_token') || localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      if (stored) {
        headers.set('Authorization', `Bearer ${stored}`);
        const espaceStocke = resoudreEspace(null);
        if (espaceStocke) headers.set('X-Tenant-ID', espaceStocke);
      }
    }
  } catch (error) {
    // Ignore error for unauthenticated requests or allow backend to respond
  }





  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const url = `${API_BASE_URL}${endpoint}`;
  try {
    let res = await fetch(url, {
      ...options,
      headers,
    });

    // Le rattachement à un espace vit dans les claims du jeton. Quand il change
    // côté serveur (création de l'espace d'un compte, changement d'entreprise),
    // le jeton déjà en main est périmé et l'API répond « aucun espace rattaché ».
    // Un rafraîchissement suffit : on le tente une fois, puis on rejoue l'appel.
    // Sans cela, l'utilisateur resterait bloqué jusqu'à l'expiration naturelle
    // de son jeton, sans comprendre pourquoi.
    if (res.status === 400 && !headers.has('X-Tenant-ID')) {
      try {
        const { data: rafraichi } = await supabase.auth.refreshSession();
        const nouveauJeton = rafraichi?.session?.access_token;
        const nouvelEspace = resoudreEspace(
          (rafraichi?.session?.user?.app_metadata as any)?.tenant_id
            || (rafraichi?.session?.user?.user_metadata as any)?.tenant_id
        );
        if (nouveauJeton && nouvelEspace) {
          headers.set('Authorization', `Bearer ${nouveauJeton}`);
          headers.set('X-Tenant-ID', nouvelEspace);
          res = await fetch(url, { ...options, headers });
        }
      } catch {
        // Rafraîchissement impossible : on laisse la réponse d'origine parler.
      }
    }

    if (!res.ok) {
      let detail = `API error ${res.status}: ${res.statusText}`;
      try {
        const body = await res.json();
        if (body && typeof body.detail === 'string' && body.detail.trim()) {
          detail = body.detail;
        }
      } catch {
        // Response body wasn't JSON — keep the generic message.
      }
      throw new ApiError(detail, res.status);
    }
    return await res.json();
  } catch (err) {
    console.warn(`[API Client] Error on ${endpoint}:`, err);
    throw err;
  }
}

// Charge une ressource protégée (ex. /api/visuals/file/...) via un fetch authentifié et
// retourne une blob: URL locale. Nécessaire pour tout <img src> pointant vers une route
// gardée par get_current_tenant_user : une balise <img> ne peut pas transporter d'en-tête
// Authorization, donc un accès direct y échoue systématiquement en 401 (image "cassée"
// silencieuse) même quand la génération a réellement réussi côté serveur. Copie volontairement
// la même logique d'auth que fetcher() ci-dessus plutôt que de la partager, pour ne pas avoir
// à toucher au corps de fetcher().
/**
 * Envoie un fichier (multipart) et recupere un fichier en retour, avec les memes
 * en-tetes d'authentification et d'espace que fetchAuthenticatedBlobUrl. Sert au
 * remplissage du cadre de reponse de l'acheteur (11/09).
 */
export async function postFormForBlob(path: string, form: FormData): Promise<{ blob: Blob; headers: Headers }> {
  const probe = await authHeadersForBlob();
  const res = await fetch(buildApiUrl(path), { method: 'POST', headers: probe, body: form });
  if (!res.ok) {
    let detail = '';
    try { const b = await res.clone().json(); detail = typeof b?.detail === 'string' ? b.detail : ''; } catch { /* non JSON */ }
    throw new ApiError(detail ? `HTTP ${res.status} — ${detail}` : `HTTP ${res.status}`, res.status);
  }
  return { blob: await res.blob(), headers: res.headers };
}

async function authHeadersForBlob(): Promise<Headers> {
  const headers = new Headers();
  try {
    const { data } = await supabase.auth.getSession();
    if (data?.session?.access_token) {
      headers.set('Authorization', `Bearer ${data.session.access_token}`);
      const tenantDuJeton = (data.session.user.app_metadata as any)?.tenant_id || (data.session.user.user_metadata as any)?.tenant_id;
      const espace = resoudreEspace(tenantDuJeton);
      if (espace) headers.set('X-Tenant-ID', espace);
    }
  } catch {
    /* sans session : l'API repondra 401 et l'appelant l'affichera */
  }
  return headers;
}

export async function fetchAuthenticatedBlobUrl(absoluteUrl: string): Promise<string> {
  const headers = new Headers();
  try {
    const { data } = await supabase.auth.getSession();
    if (data?.session?.access_token) {
      headers.set('Authorization', `Bearer ${data.session.access_token}`);
      const tenantDuJeton = (data.session.user.app_metadata as any)?.tenant_id || (data.session.user.user_metadata as any)?.tenant_id;
      const espace = resoudreEspace(tenantDuJeton);
      if (espace) headers.set('X-Tenant-ID', espace);
    } else if (typeof document !== 'undefined' && process.env.NODE_ENV !== 'production') {
      const match = document.cookie.match(/btp_e2e_secret=([^;]+)/);
      const e2eSecret = match ? match[1] : undefined;
      if (e2eSecret) {
        headers.set('x-e2e-secret', e2eSecret);
        const espaceE2E = resoudreEspace(null);
        if (espaceE2E) headers.set('X-Tenant-ID', espaceE2E);
      }
    }
    if (!headers.has('Authorization') && typeof window !== 'undefined') {
      const stored = localStorage.getItem('btp_auth_token') || localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      if (stored) {
        headers.set('Authorization', `Bearer ${stored}`);
        const espaceStocke = resoudreEspace(null);
        if (espaceStocke) headers.set('X-Tenant-ID', espaceStocke);
      }
    }
  } catch (error) {
    // Requête envoyée sans en-tête Authorization : le backend renverra 401 et l'appelant
    // affichera son état "non authentifié / non généré" au lieu d'une image cassée muette.
  }
  const res = await fetch(absoluteUrl, { headers });
  if (!res.ok) {
    // Un "HTTP 404" nu ne permet aucun diagnostic (11/09) : on remonte le `detail`
    // FastAPI quand il existe, et l'URL appelée pour qu'un doublon "/api/api" se voie.
    let detail = '';
    try {
      const body = await res.clone().json();
      detail = typeof body?.detail === 'string' ? body.detail : '';
    } catch { /* corps non JSON */ }
    const chemin = (() => { try { return new URL(absoluteUrl).pathname; } catch { return absoluteUrl; } })();
    throw new ApiError(detail ? `HTTP ${res.status} — ${detail}` : `HTTP ${res.status} (${chemin})`, res.status);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}


export const api = {
  // Auth & Password Reset



  getProfile: () => fetcher<UserProfile>('/auth/me'),
  // Charte graphique (10/09). Le formulaire de charte n'appelait AUCUNE API : il
  // simulait un enregistrement avec un setTimeout de 400 ms puis affichait
  // « enregistré ». Rien n'était jamais écrit.
  proposerCharte: () => fetcher<{
    proposition: Record<string, unknown>;
    provenance: Record<string, string>;
    champs_non_trouves: Record<string, string>;
    documents_analyses: string[];
    logo?: { present: boolean; apercu_data_url?: string; nom?: string };
  }>('/knowledge/charte/proposition'),
  appliquerCharte: (charte: Record<string, string>) =>
    fetcher<{ applique: string[]; branding_config: Record<string, string> }>('/knowledge/charte/appliquer', {
      method: 'POST',
      body: JSON.stringify(charte),
    }),
  getTenant: () => fetcher<Tenant>('/auth/tenant'),

  // Pays du marche applique au dossier (04/09) : lecture, detection sur les pieces du DCE,
  // et correction manuelle (country_code null = repli explicite sur le pays du tenant).
  getProjectCountry: (projectId: string) =>
    fetcher<ProjectCountryState>(`/projects/${projectId}/country`),
  detectProjectCountry: (projectId: string) =>
    fetcher<ProjectCountryState>(`/projects/${projectId}/country/detect`, { method: 'POST' }),
  setProjectCountry: (projectId: string, countryCode: string | null) =>
    fetcher<ProjectCountryState>(`/projects/${projectId}/country`, {
      method: 'PATCH',
      body: JSON.stringify({ country_code: countryCode }),
    }),
  requestPasswordReset: (email: string) =>
    fetcher<{ success: boolean; message: string; reset_url_dev?: string }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  verifyResetToken: (token: string) =>
    fetcher<{ valid: boolean; email: string }>('/auth/verify-reset-token', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),
  resetPassword: (token: string, new_password: string) =>
    fetcher<{ success: boolean; message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password }),
    }),


  // Projects
  getProjects: (status?: string) =>
    fetcher<Project[]>(`/projects${status ? `?status_filter=${status}` : ''}`),
  getProject: (id: string) => fetcher<Project>(`/projects/${id}`),
  createProject: (data: Partial<Project>) =>
    fetcher<Project>('/projects', { method: 'POST', body: JSON.stringify(data) }),
  updateProject: (id: string, data: Partial<Project>) =>
    fetcher<Project>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  // DCE & Criteria
  getCriteria: (projectId: string) =>
    fetcher<DCECriterion[]>(`/dce/criteria/${projectId}`),
  // État réel des pièces déposées (10/09) : le seul moyen de voir qu'une pièce est
  // restée bloquée en analyse et que la rédaction se fait sans le marché.
  getDceDocuments: (projectId: string) =>
    fetcher<{
      documents: {
        id: string; filename: string; doc_type?: string; statut: string;
        fragments_indexes: number; message?: string;
      }[];
      total_fragments: number;
      exploitable: boolean;
      avertissement?: string | null;
    }>(`/dce/documents/${projectId}`),
  reanalyserDceDocument: (documentId: string) =>
    fetcher<{ relance: boolean; document_id: string; filename: string }>(
      `/dce/documents/${documentId}/reanalyser`, { method: 'POST' },
    ),
  uploadDCE: async (projectId: string, docType: string, file: File) => {
    const formData = new FormData();
    formData.append('project_id', projectId);
    formData.append('doc_type', docType);
    formData.append('file', file);
    return fetcher<{ document_id: string; s3_key: string; status: string; message: string }>('/dce/upload', {
      method: 'POST',
      body: formData,
    });
  },

  // Go / No-Go Analysis
  getGoNoGo: (projectId: string) =>
    fetcher<GoNoGoAnalysis>(`/dce/go-no-go/${projectId}`),
  runGoNoGo: (projectId: string) =>
    fetcher<GoNoGoAnalysis>(`/dce/go-no-go/${projectId}`, {
      method: 'POST',
    }),


  getSubscription: () =>
    fetcher<{
      has_subscription: boolean;
      plan_name: string;
      plan_id: string;
      status: string;
      billing_mode: string;
      quota_dossiers: number;
      dossiers_used: number;
      exports_used: number;
      sections_used: number;
      current_period_start?: string;
      current_period_end?: string;
    }>('/billing/subscription'),

  getPlans: () => fetcher<any[]>('/billing/plans'),

  // Decisions Form
  getDecisions: (projectId: string) =>
    fetcher<ProjectDecisionsForm>(`/decisions/${projectId}`),
  saveDecisions: (projectId: string, data: ProjectDecisionsForm) =>
    fetcher<ProjectDecisionsForm>(`/decisions/${projectId}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // AI Sections Generation & WYSIWYG
  getSections: (projectId: string) =>
    fetcher<GeneratedSection[]>(`/generate/sections/${projectId}`),
  generateSection: (projectId: string, sectionKey: string, customInstructions?: string) =>
    fetcher<GeneratedSection>('/generate/section', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        section_key: sectionKey,
        custom_instructions: customInstructions,
      }),
    }),
  /**
   * Rédaction en mode de secours : exécutée dans le processus API, sans passer par
   * le worker Celery. Utilisée quand le worker est arrêté ou exécute une version
   * périmée du code — sinon l'utilisateur clique dans le vide, ou pire, obtient un
   * résultat produit par l'ancien code sans le savoir. La requête reste ouverte
   * pendant toute la rédaction (jusqu'à trois minutes) : l'appelant doit le prévoir.
   */
  generateSectionSync: (projectId: string, sectionKey: string, customInstructions?: string) =>
    fetcher<GeneratedSection>('/generate/section/sync', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        section_key: sectionKey,
        custom_instructions: customInstructions,
      }),
    }),
  updateSection: (sectionId: string, contentHtml: string, status = 'edited', locked?: boolean) =>
    fetcher<{
      success: boolean;
      section: GeneratedSection;
      learning_opportunity: boolean;
      learning_proposal?: {
        section_type: string;
        summary: string;
        suggested_content: string;
        diff_percentage: number;
      } | null;
    }>(`/generate/section/${sectionId}`, {
      method: 'PUT',
      body: JSON.stringify({
        content_html: contentHtml,
        status,
        locked_for_export: locked,
      }),
    }),
  createLearning: (payload: {
    title: string;
    category?: string;
    section_type?: string;
    project_id?: string;
    learned_content: string;
    actionable_directive?: string;
    learning_insight?: string;
    source_diff?: Record<string, any>;
    source_outcome?: string;
  }) =>
    fetcher<any>('/generate/learnings', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Visuals (Gantt & Organigramme)
  generateGantt: (projectId: string, projectTitle: string, phases: any[]) =>
    fetcher<{ s3_key: string; url: string; total_weeks: number; completion_date: string; critical_task_count?: number }>('/visuals/gantt', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, project_title: projectTitle, phases }),
    }),

  // Interactive Gantt tasks (Batch 11, cahier des charges majeur)
  listGanttTasks: (projectId: string) =>
    fetcher<GanttTask[]>(`/visuals/gantt-tasks/${projectId}`),
  checkGanttLearning: (projectId: string) =>
    fetcher<{
      learning_opportunity: boolean;
      learning_proposal?: {
        section_type: string;
        summary: string;
        suggested_content: string;
        diff_percentage: number;
      } | null;
    }>(`/visuals/gantt-tasks/${projectId}/learning-check`),
  createGanttTask: (
    projectId: string,
    payload: {
      name: string;
      start_date: string;
      end_date: string;
      progress?: number;
      is_milestone?: boolean;
      milestone_label?: string | null;
      depends_on?: string[];
      parent_id?: string | null;
      lot?: string | null;
      color?: string | null;
    }
  ) =>
    fetcher<GanttTask>(`/visuals/gantt-tasks/${projectId}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateGanttTask: (
    projectId: string,
    taskId: string,
    payload: Partial<{
      name: string;
      start_date: string;
      end_date: string;
      progress: number;
      is_milestone: boolean;
      milestone_label: string | null;
      depends_on: string[];
      parent_id: string;
      lot: string;
      color: string;
    }>
  ) =>
    fetcher<GanttTask>(`/visuals/gantt-tasks/${projectId}/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteGanttTask: (projectId: string, taskId: string) =>
    fetcher<{ success: boolean }>(`/visuals/gantt-tasks/${projectId}/${taskId}`, {
      method: 'DELETE',
    }),
  // Planning detaille (11/09) : decomposition des phases en taches / sous-taches.
  detailGantt: (projectId: string, niveau: 'taches' | 'sous_taches', remplacer = false) =>
    fetcher<GanttDetailReport>(`/visuals/gantt-tasks/${projectId}/detail`, {
      method: 'POST',
      body: JSON.stringify({ niveau, remplacer }),
    }),
  getGanttSettings: (projectId: string) =>
    fetcher<{ settings: GanttSettings; palettes: Record<string, string[]>; brand_color: string | null; projet_personnalise: boolean }>(
      `/visuals/gantt-settings/${projectId}`
    ),
  verifierPieces: (projectId: string) =>
    fetcher<PiecesRapport>(`/dossiers/${projectId}/pieces`, { method: 'POST' }),
  analyserCadreAcheteur: (projectId: string, fichier: File) => {
    const fd = new FormData();
    fd.append('file', fichier);
    return fetcher<CadreRapport>(`/client-templates/${projectId}/analyze-completeness`, { method: 'POST', body: fd });
  },
  saveGanttSettings: (projectId: string, settings: GanttSettings, portee: 'projet' | 'entreprise' = 'projet') =>
    fetcher<{ settings: GanttSettings; portee: string }>(`/visuals/gantt-settings/${projectId}`, {
      method: 'PUT',
      body: JSON.stringify({ ...settings, portee }),
    }),
  generateOrganigramme: (projectId: string, title: string, nodes: any[]) =>
    fetcher<{ s3_key: string; url: string }>('/visuals/organigramme', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, title, nodes }),
    }),

  // Interactive organigramme nodes (03/09, boucle d'apprentissage "schemas/tableaux")
  listOrganigrammeNodes: (projectId: string) =>
    fetcher<OrganigrammeNode[]>(`/visuals/organigramme-nodes/${projectId}`),
  checkOrganigrammeLearning: (projectId: string) =>
    fetcher<{
      learning_opportunity: boolean;
      learning_proposal?: {
        section_type: string;
        summary: string;
        suggested_content: string;
        diff_percentage: number;
      } | null;
    }>(`/visuals/organigramme-nodes/${projectId}/learning-check`),
  createOrganigrammeNode: (
    projectId: string,
    payload: {
      nom: string;
      role: string;
      experience_ans?: number;
      presence_hebdo_pct?: number;
      qualif?: string | null;
    }
  ) =>
    fetcher<OrganigrammeNode>(`/visuals/organigramme-nodes/${projectId}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateOrganigrammeNode: (
    projectId: string,
    nodeId: string,
    payload: Partial<{
      nom: string;
      role: string;
      experience_ans: number;
      presence_hebdo_pct: number;
      qualif: string | null;
    }>
  ) =>
    fetcher<OrganigrammeNode>(`/visuals/organigramme-nodes/${projectId}/${nodeId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteOrganigrammeNode: (projectId: string, nodeId: string) =>
    fetcher<{ success: boolean }>(`/visuals/organigramme-nodes/${projectId}/${nodeId}`, {
      method: 'DELETE',
    }),

  // Export Word / PDF (unified helper used by export page). Correctif tâche #66
  // (02/09) : renvoyait auparavant un type inventé (docx_url/pdf_url/filename/
  // file_size_kb/sections_count) qui ne correspondait à AUCUN champ réellement
  // renvoyé par /export/compile (voir ExportJobOut côté backend) -- la carte de
  // résultat ne pouvait donc jamais s'afficher correctement. Réutilise
  // désormais le même type ExportJob que compileExport ci-dessous.
  exportProject: (projectId: string, opts: { format: 'docx' | 'pdf'; include_visuals?: boolean; include_cover_page?: boolean }) =>
    fetcher<ExportJob>('/export/compile', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        format: opts.format,
        include_gantt: opts.include_visuals ?? true,
        include_organigramme: opts.include_visuals ?? true,
        include_cover_page: opts.include_cover_page ?? true,
      }),
    }),
  // /export/compile ne fait que déclencher la génération en tâche de fond et répond
  // immédiatement avec status "processing" -- ceci permet d'interroger l'état réel
  // jusqu'à ce que le worker Celery ait fini (ou échoué).
  /**
   * Compilation en mode de secours, exécutée dans le processus API. Même raison
   * d'être que generateSectionSync : quand le worker de fond est arrêté ou périmé,
   * l'export part en file et n'en revient jamais. La réponse est le job TERMINÉ.
   */
  exportProjectSync: (projectId: string, opts: { format: 'docx' | 'pdf'; include_visuals?: boolean; include_cover_page?: boolean }) =>
    fetcher<ExportJob>('/export/compile/sync', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        format: opts.format,
        include_gantt: opts.include_visuals ?? true,
        include_organigramme: opts.include_visuals ?? true,
        include_cover_page: opts.include_cover_page ?? true,
      }),
    }),
  getExportJob: (jobId: string) => fetcher<ExportJob>(`/export/job/${jobId}`),

  // Legacy export helper (kept for backward compat)
  compileExport: (projectId: string, format: 'docx' | 'pdf' | 'both', includeVisuals = true) =>
    fetcher<ExportJob>('/export/compile', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        format,
        include_gantt: includeVisuals,
        include_organigramme: includeVisuals,
      }),
    }),

  // Knowledge Base
  getKnowledgeAssets: (category?: string) =>
    fetcher<CompanyAsset[]>(`/knowledge/assets${category ? `?category=${category}` : ''}`),
  getAssets: (category?: string) =>
    fetcher<CompanyAsset[]>(`/knowledge/assets${category ? `?category=${category}` : ''}`),
  getKnowledgeStats: () =>
    fetcher<{ total_assets: number; max_allowed: number | null; plan: string; category_counts: Record<string, number> }>('/knowledge/stats'),

  uploadKnowledgeDocument: (formData: FormData) =>
    fetcher<{
      success: boolean;
      asset_id: string;
      title: string;
      category: string;
      status: string;
      file_size_bytes: number;
      word_count: number;
      message: string;
    }>('/knowledge/upload', {
      method: 'POST',
      body: formData,
    }),
  addKnowledgeWebSource: (data: { url: string; title?: string; category?: string }) =>
    fetcher<CompanyAsset>('/knowledge/web-source', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteKnowledgeAsset: (assetId: string) =>
    fetcher<{ success: boolean; message: string }>(`/knowledge/assets/${assetId}`, {
      method: 'DELETE',
    }),
  addKnowledgeAsset: (data: { category: string; title: string; description?: string; tags?: string[]; metadata_json?: any }) =>
    fetcher<CompanyAsset>('/knowledge/assets', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Knowledge & Document Downloads / Previews
  getKnowledgeAssetBlobUrl: async (assetId: string, inline: boolean = false) => {
    return fetchAuthenticatedBlobUrl(`${API_BASE_URL}/knowledge/assets/${assetId}/download?inline=${inline}`);
  },

  getWordTemplateBlobUrl: async () => {
    return fetchAuthenticatedBlobUrl(`${API_BASE_URL}/knowledge/template/word/download`);
  },

  // Admin Tenant Document Management
  getAdminTenantDocuments: (tenantId: string) =>
    fetcher<Array<{
      id: string;
      file_name: string;
      title: string;
      category: string;
      file_path: string;
      file_type: string;
      file_size: number;
      status: string;
      source: string;
      created_at?: string;
      can_download: boolean;
    }>>(`/admin/tenants/${tenantId}/documents`),

  getAdminTenantDocumentBlobUrl: async (tenantId: string, docId: string, inline: boolean = false) => {
    return fetchAuthenticatedBlobUrl(`${API_BASE_URL}/admin/tenants/${tenantId}/documents/${docId}/download?inline=${inline}`);
  },


  // Project Q&A Assistant with configurable source mode ('corpus' | 'corpus_web' | 'web')
  askProject: (projectId: string, question: string, sourceMode: 'corpus' | 'corpus_web' | 'web' = 'corpus') =>
    fetcher<{
      question: string;
      source_mode: 'corpus' | 'corpus_web' | 'web';
      answer_markdown: string;
      sources: Array<{
        type: string;
        title?: string;
        page?: number;
        url?: string;
        citation: string;
        snippet: string;
      }>;
      total_sources_found: number;
      is_degraded?: boolean;
      degraded_reason?: string;
      timestamp: string;
    }>(`/projects/${projectId}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question, source_mode: sourceMode }),
    }),

  // Company-wide Q&A Assistant ("Mon Entreprise") -- searches CompanyAsset knowledge +
  // optionally web search strictly restricted to configured Sites de Référence. Distinct
  // endpoint from askProject: never scoped to (or mixed in with) any single project's DCE.
  askCompany: (question: string, sourceMode: 'corpus' | 'corpus_web' | 'web' = 'corpus') =>
    fetcher<{
      question: string;
      source_mode: 'corpus' | 'corpus_web' | 'web';
      answer_markdown: string;
      sources: Array<{
        type: string;
        title?: string;
        category?: string;
        url?: string;
        citation: string;
        snippet: string;
      }>;
      total_sources_found: number;
      is_degraded?: boolean;
      degraded_reason?: string;
      timestamp: string;
    }>('/company/ask', {
      method: 'POST',
      body: JSON.stringify({ question, source_mode: sourceMode }),
    }),


  // Super-Admin Tenant Management & Model Settings
  getTenants: () => fetcher<Tenant[]>('/admin/tenants'),
  getTenantDetail: (tenantId: string) => fetcher<any>(`/admin/tenants/${tenantId}`),
  createTenant: (data: CreateTenantInput) =>
    fetcher<Tenant>('/admin/tenants', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateTenant: (tenantId: string, data: any) =>
    fetcher<any>(`/admin/tenants/${tenantId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteTenant: (tenantId: string) =>
    fetcher<{ success: boolean; message: string; certificate?: any }>(`/admin/tenants/${tenantId}`, {
      method: 'DELETE',
    }),
  // Whitelist reglementaire (sites officiels par pays) -- restreint strictement la recherche web
  // de l'IA pendant la generation de sections et le chat DCE. CRUD reserve au Super Admin.
  listCountrySourcesAdmin: (countryCode?: string) =>
    fetcher<Array<{
      id: string;
      country_code: string;
      portal_name: string;
      portal_url: string;
      portal_type: string;
      reference_law: string | null;
      status: string;
      last_checked_at: string | null;
      created_at: string | null;
    }>>(`/admin/country-sources${countryCode ? `?country_code=${countryCode}` : ''}`),
  createCountrySourceAdmin: (data: {
    country_code: string;
    portal_name: string;
    portal_url: string;
    portal_type: string;
    reference_law?: string;
    status?: string;
  }) =>
    fetcher<{ success: boolean; id: string }>('/admin/country-sources', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateCountrySourceAdmin: (sourceId: string, data: Partial<{
    country_code: string;
    portal_name: string;
    portal_url: string;
    portal_type: string;
    reference_law: string;
    status: string;
  }>) =>
    fetcher<{ success: boolean }>(`/admin/country-sources/${sourceId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteCountrySourceAdmin: (sourceId: string) =>
    fetcher<{ success: boolean; message: string }>(`/admin/country-sources/${sourceId}`, {
      method: 'DELETE',
    }),
  getPlatformLLMKeys: () => fetcher<PlatformLLMKeys>('/admin/llm-keys'),
  getLlmUsageSummary: () => fetcher<any>('/admin/llm-usage-summary'),
  getRevenueSummary: () => fetcher<any>('/admin/revenue-summary'),
  updatePlatformLLMKeys: (data: {
    anthropic_api_key?: string;
    openai_api_key?: string;
    mistral_api_key?: string;
    default_llm_tier?: string;
    default_fallback_tier?: string;
    custom_providers?: any[];
    model_tier_overrides?: Record<string, string>;
    web_search_providers?: Array<{
      id: string;
      name: string;
      type: string;
      enabled: boolean;
      priority: number;
      api_key?: string;
    }>;
  }) =>
    fetcher<any>('/admin/llm-keys', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  testLLMProvider: (data: {
    provider_id?: string;
    name?: string;
    litellm_id: string;
    api_key?: string;
    api_base?: string;
  }) =>
    fetcher<{
      success: boolean;
      status: 'success' | 'error';
      latency_ms: number;
      message?: string;
      error_message?: string;
      tested_at: string;
    }>('/admin/llm-keys/test-provider', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  // Test réel d'une clé de recherche web : exécute une vraie requête et renvoie le
  // nombre de résultats ou l'erreur du fournisseur (04/09).
  testSearchProvider: (data: { provider: string; provider_id?: string; api_key?: string }) =>
    fetcher<{
      success: boolean;
      provider: string;
      results_count?: number;
      latency_ms?: number;
      message?: string;
      error?: string;
    }>('/admin/llm-keys/test-search-provider', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // ── Plafonds de dépense IA (fournisseur / forfait / client) ──────────────
  getCostLimits: () => fetcher<CostLimitsOverview>('/admin/cost-limits'),
  updateCostLimitSettings: (data: {
    display_currency?: 'EUR' | 'USD';
    eur_usd_rate?: number;
    target_llm_share?: number;
    alert_threshold_pct?: number;
  }) =>
    fetcher<{ success: boolean; settings: CostLimitsOverview['settings'] }>('/admin/cost-limits/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  setProviderCostCap: (providerId: string, amount: number | null, currency: 'EUR' | 'USD') =>
    fetcher<{ success: boolean; cap_usd: number | null }>(`/admin/cost-limits/providers/${providerId}`, {
      method: 'PUT',
      body: JSON.stringify({ amount, currency }),
    }),
  setPlanCostCap: (planId: string, amount: number | null, currency: 'EUR' | 'USD') =>
    fetcher<{ success: boolean; cap_usd: number | null }>(`/admin/cost-limits/plans/${planId}`, {
      method: 'PUT',
      body: JSON.stringify({ amount, currency }),
    }),
  setTenantCostCap: (tenantId: string, amount: number | null, currency: 'EUR' | 'USD') =>
    fetcher<{ success: boolean; cap_usd: number | null }>(`/admin/cost-limits/tenants/${tenantId}`, {
      method: 'PUT',
      body: JSON.stringify({ amount, currency }),
    }),
  applyRecommendedPlanCaps: () =>
    fetcher<{ success: boolean; applied: { plan_id: string; cap_usd: number }[] }>(
      '/admin/cost-limits/plans/apply-recommended',
      { method: 'POST' },
    ),

  getLlmCatalog: () => fetcher<LlmCatalogResponse>('/admin/llm-catalog'),
  syncLlmCatalog: () =>
    fetcher<LlmCatalogSyncResult>('/admin/llm-catalog/sync', {
      method: 'POST',
    }),



  // RGPD Account Erasure
  requestAccountDeletion: () =>
    fetcher<{
      success: boolean;
      status: string;
      deletion_requested_at: string;
      scheduled_purge_at: string;
      message: string;
      legal_notice: string;
    }>('/auth/account/delete-request', {
      method: 'POST',
    }),
  cancelAccountDeletion: () =>
    fetcher<{
      success: boolean;
      status: string;
      message: string;
    }>('/auth/account/cancel-deletion', {
      method: 'POST',
    }),

  // Knowledge & Retention
  markKnowledgeAssetObsolete: (assetId: string) =>
    fetcher<{
      success: boolean;
      message: string;
      asset_id: string;
      status: string;
      obsolete_at: string;
    }>(`/knowledge/assets/${assetId}/obsolete`, {
      method: 'POST',
    }),

  // Assistant History Hard-Delete
  deleteAssistantMessage: (projectId: string, messageId: string) =>
    fetcher<{
      success: boolean;
      message: string;
      project_id: string;
      deleted_message_id: string;
    }>(`/projects/${projectId}/assistant/messages/${messageId}`, {
      method: 'DELETE',
    }),

  // Super Admin Tenant Purge & RGPD Certificate
  purgeTenantWithCertificate: (tenantId: string) =>
    fetcher<{
      success: boolean;
      message: string;
      certificate: {
        certificate_id: string;
        regulation: string;
        tenant_id: string;
        tenant_name: string;
        tenant_siret: string;
        tenant_slug: string;
        purged_by_admin: string;
        purged_at_utc: string;
        deleted_elements: Record<string, any>;
        legal_notice: string;
      };
    }>(`/admin/tenants/${tenantId}`, {
      method: 'DELETE',
    }),

  // Admin RAG & System Prompt & Model Routing
  getRagSupervision: () => fetcher<{
    embedding_model: string;
    dimensions: number;
    similarity_metric: string;
    total_dce_chunks: number;
    total_knowledge_chunks: number;
    index_type: string;
    embedding_mode?: 'real' | 'degraded_fallback';
    embedding_provider?: 'openai' | 'mistral' | null;
  }>('/admin/rag-supervision'),
  getTenantSystemPrompt: (tenantId: string) => fetcher<{ tenant_id: string; system_prompt: string }>(`/admin/system-prompt/${tenantId}`),
  updateTenantSystemPrompt: (tenantId: string, systemPrompt: string) =>
    fetcher<{ success: boolean; message: string }>('/admin/system-prompt', {
      method: 'POST',
      body: JSON.stringify({ tenant_id: tenantId, system_prompt: systemPrompt }),
    }),
  updateTenantModelRouting: (payload: { tenant_id: string; extraction_gonogo?: any; redaction_memoire?: any; analyse_prix?: any }) =>
    fetcher<{ success: boolean; message: string }>('/admin/model-routing', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // BT01 -- Chiffrage & Ajustement Inflation
  getPricingLines: (projectId: string) => fetcher<any[]>(`/projects/${projectId}/pricing-lines`),
  createPricingLine: (projectId: string, payload: { lot?: string; designation: string; unite: string; quantite: number; prix_unitaire_ht: number }) =>
    fetcher<any>(`/projects/${projectId}/pricing-lines`, { method: 'POST', body: JSON.stringify(payload) }),
  updatePricingLine: (lineId: string, payload: { lot?: string; designation: string; unite: string; quantite: number; prix_unitaire_ht: number }) =>
    fetcher<any>(`/pricing-lines/${lineId}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deletePricingLine: (lineId: string) => fetcher<any>(`/pricing-lines/${lineId}`, { method: 'DELETE' }),
  getPricingSummary: (projectId: string) => fetcher<any>(`/projects/${projectId}/pricing-summary`),
  analyzePricing: (projectId: string) => fetcher<any>(`/projects/${projectId}/pricing-analysis`, { method: 'POST' }),
  getEconomicSettings: () => fetcher<any>('/company/economic-settings'),
  updateEconomicSettings: (payload: { taux_inflation_pct?: number; marge_cible_pct?: number; risk_contingency_pct?: number; taux_horaires?: Record<string, number> }) =>
    fetcher<any>('/company/economic-settings', { method: 'PUT', body: JSON.stringify(payload) }),

  // Knowledge & Word Template
  uploadWordTemplate: (formData: FormData) =>
    fetcher<{ success: boolean; message: string; filename: string }>('/knowledge/template/word', {
      method: 'POST',
      body: formData,
    }),

  // Company Profile Auto-Bootstrap & Reference URLs
  triggerCompanyBootstrap: (payload: { company_name: string; siret?: string; reference_urls?: string[] }) =>
    fetcher<{ success: boolean; run_id: string; status: string; message: string }>('/company/bootstrap', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getCompanyBootstrapStatus: (runId: string) =>
    fetcher<{
      id: string;
      tenant_id: string;
      status: string;
      sources_found: Array<{ url: string; title: string; source_type: string; fetched_at: string }>;
      extracted_assets: Array<{
        id: string;
        category: string;
        title: string;
        description: string;
        s3_url?: string;
        source_type: string;
        validated_by_user: boolean;
        metadata_json: Record<string, any>;
      }>;
      error_message?: string;
    }>(`/company/bootstrap/${runId}`),
  validateCompanyAsset: (assetId: string, payload: { validated: boolean; title?: string; description?: string; category?: string }) =>
    fetcher<{ id: string; validated_by_user: boolean; title: string; description: string }>(`/company/assets/${assetId}/validate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getReferenceUrls: () =>
    fetcher<Array<{ id: string; url: string; label?: string; added_at: string; status: string; last_fetched_at?: string; last_fetch_error?: string | null }>>('/company/reference-urls'),
  addReferenceUrl: (payload: { url: string; label?: string }) =>
    fetcher<{ id: string; url: string; label?: string; status: string }>('/company/reference-urls', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  deleteReferenceUrl: (urlId: string) =>
    fetcher<{ success: boolean; message: string }>(`/company/reference-urls/${urlId}`, {
      method: 'DELETE',
    }),
  refreshReferenceUrl: (urlId: string) =>
    fetcher<{ success: boolean; message: string; title?: string; status?: string; error?: string | null }>(`/company/reference-urls/${urlId}/refresh`, {
      method: 'POST',
    }),

  // Infrastructure Cluster Health
  getClusterHealth: async () => {
    const rawApiUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
    const targetUrl = rawApiUrl.endsWith('/api') ? `${rawApiUrl}/health` : `${rawApiUrl}/api/health`;
    const res = await fetch(targetUrl);
    return await res.json();
  },

  // Team & Collaboration Management (Real Multi-Tenant RBAC)
  getTeamMembers: () => fetcher<TeamMember[]>('/team/members'),
  inviteTeamMember: (data: { email: string; role?: string }) =>
    fetcher<TeamInvitation>('/team/invitations', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteTeamMember: (userId: string) =>
    fetcher<{ status: string; message: string }>(`/team/members/${userId}`, {
      method: 'DELETE',
    }),
  updateTeamMemberRole: (userId: string, role: string) =>
    fetcher<TeamMember>(`/team/members/${userId}/role`, {
      method: 'PUT',
      body: JSON.stringify({ role }),
    }),
  getTeamInvitations: () => fetcher<TeamInvitation[]>('/team/invitations'),

  // Suggested / Deduced Starting Template from Tenant History
  getSuggestedTemplate: () => fetcher<SuggestedTemplate>('/knowledge/template/suggested'),

  // MEA Regional Dossiers Export (Saudi Arabia GTPL, Qatar Ashghal, UAE, Lebanon)
  exportMeaDossier: async (projectId: string, countryCode: string, language: 'en' | 'ar' | 'fr' = 'en') => {
    const { data: { session } } = await supabase.auth.getSession();
    const token = session?.access_token;
    const tenantId = (session?.user?.app_metadata as any)?.tenant_id;

    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    const queryUrl = `${API_BASE_URL}/dossiers/${projectId}/mea?country_code=${encodeURIComponent(countryCode)}&language=${encodeURIComponent(language)}`;
    const res = await fetch(queryUrl, { headers });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Erreur export MEA (${res.status}): ${errText}`);
    }

    const blob = await res.blob();
    const filenameHeader = res.headers.get('Content-Disposition');
    let filename = `Dossier_MEA_${countryCode}_${language}.docx`;
    if (filenameHeader && filenameHeader.includes('filename=')) {
      const match = filenameHeader.match(/filename="?([^";]+)"?/);
      if (match && match[1]) filename = match[1];
    }

    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(downloadUrl);

    return { success: true, filename };
  },
};








