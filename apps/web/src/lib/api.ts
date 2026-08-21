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
} from './types';



import { supabase } from './supabase/client';

const rawApiUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_BASE_URL = rawApiUrl.endsWith('/api') ? rawApiUrl : `${rawApiUrl}/api`;
const DEMO_TENANT_ID = '11111111-1111-1111-1111-111111111111';


async function fetcher<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  
  // Real Supabase Auth Token Injection
  try {
    const { data } = await supabase.auth.getSession();
    if (data?.session?.access_token) {
      headers.set('Authorization', `Bearer ${data.session.access_token}`);
      const tenantId = (data.session.user.app_metadata as any)?.tenant_id;
      if (tenantId) {
        headers.set('X-Tenant-ID', tenantId);
      } else {
        headers.set('X-Tenant-ID', DEMO_TENANT_ID);
      }
    } else {
      // Local dev token fallback to ensure local backend queries succeed
      const LOCAL_DEV_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMTExMTExMS1hYWFhLWFhYWEtYWFhYS1hYWFhYWFhYWFhYWEiLCJlbWFpbCI6ImRpcmVjdGV1ckBlaWZmYWJ0cC5mciIsImF1ZCI6ImF1dGhlbnRpY2F0ZWQiLCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFwcF9tZXRhZGF0YSI6eyJ0ZW5hbnRfaWQiOiIxMTExMTExMS0xMTExLTExMTEtMTExMS0xMTExMTExMTExMTEiLCJyb2xlIjoib3duZXIifSwidXNlcl9tZXRhZGF0YSI6eyJ0ZW5hbnRfaWQiOiIxMTExMTExMS0xMTExLTExMTEtMTExMS0xMTExMTExMTExMTEiLCJyb2xlIjoib3duZXIifX0.XM-XVexbsiIzyUqu25d8MlZvH0NCuaGhr8vM9H9EzTs';
      headers.set('Authorization', `Bearer ${LOCAL_DEV_TOKEN}`);
      headers.set('X-Tenant-ID', DEMO_TENANT_ID);
    }
  } catch {
    const LOCAL_DEV_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMTExMTExMS1hYWFhLWFhYWEtYWFhYS1hYWFhYWFhYWFhYWEiLCJlbWFpbCI6ImRpcmVjdGV1ckBlaWZmYWJ0cC5mciIsImF1ZCI6ImF1dGhlbnRpY2F0ZWQiLCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFwcF9tZXRhZGF0YSI6eyJ0ZW5hbnRfaWQiOiIxMTExMTExMS0xMTExLTExMTEtMTExMS0xMTExMTExMTExMTEiLCJyb2xlIjoib3duZXIifSwidXNlcl9tZXRhZGF0YSI6eyJ0ZW5hbnRfaWQiOiIxMTExMTExMS0xMTExLTExMTEtMTExMS0xMTExMTExMTExMTEiLCJyb2xlIjoib3duZXIifX0.XM-XVexbsiIzyUqu25d8MlZvH0NCuaGhr8vM9H9EzTs';
    headers.set('Authorization', `Bearer ${LOCAL_DEV_TOKEN}`);
    headers.set('X-Tenant-ID', DEMO_TENANT_ID);
  }



  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers,
    });
    if (!res.ok) {
      throw new Error(`API error ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    console.warn(`[API Client] Error on ${endpoint}:`, err);
    throw err;
  }
}


export const api = {
  // Auth & Password Reset



  getProfile: () => fetcher<UserProfile>('/auth/me'),
  getTenant: () => fetcher<Tenant>('/auth/tenant'),
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
  updateSection: (sectionId: string, contentHtml: string, status = 'edited', locked?: boolean) =>
    fetcher<GeneratedSection>(`/generate/section/${sectionId}`, {
      method: 'PUT',
      body: JSON.stringify({
        content_html: contentHtml,
        status,
        locked_for_export: locked,
      }),
    }),

  // Visuals (Gantt & Organigramme)
  generateGantt: (projectId: string, projectTitle: string, phases: any[]) =>
    fetcher<{ s3_key: string; url: string; total_weeks: number; completion_date: string }>('/visuals/gantt', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, project_title: projectTitle, phases }),
    }),
  generateOrganigramme: (projectId: string, title: string, nodes: any[]) =>
    fetcher<{ s3_key: string; url: string }>('/visuals/organigramme', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId, title, nodes }),
    }),

  // Export Word / PDF (unified helper used by export page)
  exportProject: (projectId: string, opts: { format: 'docx' | 'pdf'; include_visuals?: boolean; template?: string }) =>
    fetcher<{ docx_url?: string; pdf_url?: string; filename?: string; file_size_kb?: number; sections_count?: number }>('/export/compile', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        format: opts.format,
        include_gantt: opts.include_visuals ?? true,
        include_organigramme: opts.include_visuals ?? true,
        template: opts.template || 'standard_btp',
      }),
    }),

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
  addKnowledgeAsset: (data: { title: string; asset_type: string; description?: string; qualification_number?: string }) =>
    fetcher<CompanyAsset>('/knowledge/assets', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

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


  // Super-Admin Tenant Management
  getTenants: () => fetcher<Tenant[]>('/admin/tenants'),
  createTenant: (data: CreateTenantInput) =>
    fetcher<Tenant>('/admin/tenants', {
      method: 'POST',
      body: JSON.stringify(data),
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
};




