#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 2 — fixes for issues confirmed by live investigation (browser + DB + code):

ROOT CAUSES CONFIRMED THIS SESSION (not theorized — verified):
1. generated_sections for the demo project are ALL stuck at status="processing",
   compliance_score=0.0, content_html=<the backend's own INSERT-time placeholder string>,
   all created within the same second. /health shows Postgres OK and the Celery BROKER
   (Redis) reachable -- but nothing has EVER progressed past insert. Root cause: there is
   no "dev:worker" npm script anywhere and the Celery worker requires a separate manual
   `celery -A app.core.celery_app worker` process (per README's "sans Docker" section) that
   is almost certainly simply not running. This script does NOT (and cannot) start that
   worker -- only the user can, on their real machine. What IS fixed here is the frontend's
   dishonest handling of that state:
     a) `hasContent = Boolean(sec?.content_html)` treated the placeholder string itself as
        "real content" -> false green checkmark the instant a row is inserted, before any
        real generation happened.
     b) `compliance_score: activeSection?.compliance_score || 85` -- `0 || 85` evaluates to
        85 in JS because 0 is falsy. The REAL score (0.0, correctly shown as "0%" in the
        sidebar via `sec?.compliance_score` with no `||`) was masked by a fake "85%" in the
        bottom badge, which is exactly the "pourquoi 85% alors que tout est vide" the user
        flagged as nonsensical.
     c) Polling timeout (20 attempts / ~80s) silently cleared `generating` with ZERO visible
        signal of failure -- leaving a permanently ambiguous "looks maybe done, isn't" state.
   Fix: real completion is now `status in (generated, edited, validated, restored)` AND
   non-empty content -- never just "content_html is non-empty". Score falls back to 0 (not a
   fake 85) only via `??`, never masking a real 0. A new `failedKeys` state makes timeouts
   and backend "failed" statuses explicit everywhere the section appears (sidebar icon +
   sidebar subtitle + main body message + bottom badge), instead of silence.

2. GanttPreview / OrganigrammePreview render `<img src="{apiBase}/api/visuals/file/...">`
   directly. That endpoint is guarded by `Depends(get_current_tenant_user)` (Bearer JWT
   required) -- a plain <img> tag cannot attach an Authorization header, so the request
   401s and the browser shows a broken-image icon. This is a totally separate bug from any
   auth problem in the current test tab: it would 401 even for a fully logged-in real user,
   which matches the user's screenshot showing a successful "Planning synchronisé : 24
   semaines" banner (the *authenticated* regenerate POST worked) sitting right above a
   still-broken image (the *unauthenticated* GET for the <img> failed).
   Fix: both components now fetch the image via an authenticated request (reusing the
   exact same auth-header logic api.ts already uses for every other call, factored out into
   `applyAuthHeaders`) and render it from a blob: object URL. They also now distinguish and
   clearly label three states instead of one silent broken icon: not generated yet (404),
   real error (network/auth), and loading.

Exact-match-count-of-1 verified before writing; aborts per-file with zero writes on mismatch.
"""
import sys

def apply_patch(path, replacements):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for label, old, new in replacements:
        count = content.count(old)
        if count != 1:
            print(f"ABORT [{path}] block '{label}': found {count} occurrences (expected 1). No changes written.")
            return False
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: {path} patched ({len(replacements)} block(s)).")
    return True


if len(sys.argv) != 2:
    print("Usage: patch_batch2_visuals_and_status.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
API_TS = f"{REPO_ROOT}/apps/web/src/lib/api.ts"
EDITOR_TSX = f"{REPO_ROOT}/apps/web/src/app/projects/[id]/editor/page.tsx"
GANTT_TSX = f"{REPO_ROOT}/apps/web/src/components/visuals/gantt-preview.tsx"
ORGANI_TSX = f"{REPO_ROOT}/apps/web/src/components/visuals/organigramme-preview.tsx"

# ─────────────────────────────────────────────────────────────────────────
# 1. api.ts — factor auth-header logic into applyAuthHeaders(), reuse it from
#    fetcher() AND from a new fetchAuthenticatedBlobUrl() export.
# ─────────────────────────────────────────────────────────────────────────
ok1 = apply_patch(API_TS, [
    (
        "extract applyAuthHeaders + call it from fetcher",
        '''async function fetcher<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});

  // Real Supabase Auth Token Injection
  try {
    const { data } = await supabase.auth.getSession();
    if (data?.session?.access_token) {
      headers.set('Authorization', `Bearer ${data.session.access_token}`);
      const tenantId = (data.session.user.app_metadata as any)?.tenant_id || (data.session.user.user_metadata as any)?.tenant_id;
      if (tenantId) {
        headers.set('X-Tenant-ID', tenantId);
      } else {
        headers.set('X-Tenant-ID', '93365082-4489-4f0a-9e4b-9dbb219553aa');
      }
    } else if (typeof document !== 'undefined' && process.env.NODE_ENV !== 'production') {
      // E2E test runner sets this cookie deliberately before running tests (non-production only).
      // No hardcoded-secret fallback here: an unauthenticated request must simply stay unauthenticated.
      const match = document.cookie.match(/btp_e2e_secret=([^;]+)/);
      const e2eSecret = match ? match[1] : undefined;
      if (e2eSecret) {
        headers.set('x-e2e-secret', e2eSecret);
        headers.set('X-Tenant-ID', '93365082-4489-4f0a-9e4b-9dbb219553aa');
      }
    }

    if (!headers.has('Authorization') && typeof window !== 'undefined') {
      const stored = localStorage.getItem('btp_auth_token') || localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      if (stored) {
        headers.set('Authorization', `Bearer ${stored}`);
        headers.set('X-Tenant-ID', '93365082-4489-4f0a-9e4b-9dbb219553aa');
      }
    }
  } catch (error) {
    // Ignore error for unauthenticated requests or allow backend to respond
  }''',
        '''// Injection des en-têtes d'authentification (session Supabase réelle, secret E2E de test
// non-production, ou fallback localStorage/sessionStorage). Factorisé hors de fetcher() pour
// être réutilisé par fetchAuthenticatedBlobUrl() (images protégées type <img>, qui ne peuvent
// pas transporter d'en-tête Authorization nativement -- voir plus bas).
async function applyAuthHeaders(headers: Headers): Promise<void> {
  try {
    const { data } = await supabase.auth.getSession();
    if (data?.session?.access_token) {
      headers.set('Authorization', `Bearer ${data.session.access_token}`);
      const tenantId = (data.session.user.app_metadata as any)?.tenant_id || (data.session.user.user_metadata as any)?.tenant_id;
      if (tenantId) {
        headers.set('X-Tenant-ID', tenantId);
      } else {
        headers.set('X-Tenant-ID', '93365082-4489-4f0a-9e4b-9dbb219553aa');
      }
    } else if (typeof document !== 'undefined' && process.env.NODE_ENV !== 'production') {
      // E2E test runner sets this cookie deliberately before running tests (non-production only).
      // No hardcoded-secret fallback here: an unauthenticated request must simply stay unauthenticated.
      const match = document.cookie.match(/btp_e2e_secret=([^;]+)/);
      const e2eSecret = match ? match[1] : undefined;
      if (e2eSecret) {
        headers.set('x-e2e-secret', e2eSecret);
        headers.set('X-Tenant-ID', '93365082-4489-4f0a-9e4b-9dbb219553aa');
      }
    }

    if (!headers.has('Authorization') && typeof window !== 'undefined') {
      const stored = localStorage.getItem('btp_auth_token') || localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      if (stored) {
        headers.set('Authorization', `Bearer ${stored}`);
        headers.set('X-Tenant-ID', '93365082-4489-4f0a-9e4b-9dbb219553aa');
      }
    }
  } catch (error) {
    // Ignore error for unauthenticated requests or allow backend to respond
  }
}

async function fetcher<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  await applyAuthHeaders(headers);''',
    ),
    (
        "insert fetchAuthenticatedBlobUrl export after fetcher()",
        '''    return await res.json();
  } catch (err) {
    console.warn(`[API Client] Error on ${endpoint}:`, err);
    throw err;
  }
}


export const api = {''',
        '''    return await res.json();
  } catch (err) {
    console.warn(`[API Client] Error on ${endpoint}:`, err);
    throw err;
  }
}

// Charge une ressource protégée (ex. /api/visuals/file/...) via un fetch authentifié et
// retourne une blob: URL locale. Nécessaire pour tout <img src> pointant vers une route
// gardée par get_current_tenant_user : une balise <img> ne peut pas transporter d'en-tête
// Authorization, donc un accès direct y échoue systématiquement en 401 (image "cassée"
// silencieuse) même quand la génération a réellement réussi côté serveur.
export async function fetchAuthenticatedBlobUrl(absoluteUrl: string): Promise<string> {
  const headers = new Headers();
  await applyAuthHeaders(headers);
  const res = await fetch(absoluteUrl, { headers });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}


export const api = {''',
    ),
])

# ─────────────────────────────────────────────────────────────────────────
# 2. gantt-preview.tsx — full rewrite: authenticated blob-URL loading +
#    explicit loading/missing/error states instead of a silent broken <img>.
# ─────────────────────────────────────────────────────────────────────────
GANTT_OLD = '''\'use client\';

import React, { useState } from \'react\';
import { BarChart3, RefreshCw, Download, Calendar, CheckCircle2 } from \'lucide-react\';
import { api } from \'@/lib/api\';

interface GanttPreviewProps {
  projectId: string;
  projectTitle?: string;
  initialImageUrl?: string;
}

export function GanttPreview({ projectId, projectTitle = \'Projet BTP\', initialImageUrl }: GanttPreviewProps) {
  const apiBase = (process.env.NEXT_PUBLIC_API_URL || \'\').replace(/\\/$/, \'\');
  const [imageUrl, setImageUrl] = useState<string>(
    initialImageUrl || `${apiBase}/api/visuals/file/tenants/11111111-1111-1111-1111-111111111111/visuals/${projectId}/gantt_planning.png`
  );
  const [isGenerating, setIsGenerating] = useState(false);
  const [lastGenerated, setLastGenerated] = useState<string | null>(null);

  const handleRegenerate = async () => {
    setIsGenerating(true);
    try {
      const res = await api.generateGantt(projectId, projectTitle, []);
      // Add timestamp to bypass browser cache
      setImageUrl(`${apiBase}/api/visuals/file/${res.s3_key}?t=${Date.now()}`);
      setLastGenerated(`${res.total_weeks} semaines (Livraison le ${res.completion_date})`);
    } catch (err) {
      console.error(\'Failed to generate gantt\', err);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-sky-400" />
            Planning Prévisionnel de Phasage (Gantt BTP)
          </h3>
          <p className="text-xs text-slate-400">
            Généré automatiquement par Python Matplotlib avec chemin critique, jalons et marge intempéries.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRegenerate}
            disabled={isGenerating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-glow disabled:opacity-50 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isGenerating ? \'animate-spin\' : \'\'}`} />
            <span>{isGenerating ? \'Calcul du Gantt...\' : \'Régénérer Gantt HD\'}</span>
          </button>
        </div>
      </div>

      {lastGenerated && (
        <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          Planning synchronisé : {lastGenerated}
        </div>
      )}

      {/* Image Preview Container */}
      <div className="relative rounded-xl border border-slate-800 overflow-hidden bg-slate-950 flex items-center justify-center p-2 min-h-[340px]">
        <img
          src={imageUrl}
          alt="Planning Gantt BTP"
          className="w-full h-auto rounded-lg shadow-md object-contain max-h-[500px]"
          onError={(e) => {
            // Trigger generation if not present
            handleRegenerate();
          }}
        />
      </div>

      <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-900">
        <span>Format : PNG Haute Définition (300 DPI) • Intégration directe dans le document Word .docx</span>
        <span className="text-sky-400 font-medium">Inclus dans la section 3 (Méthodologie & Phasage)</span>
      </div>
    </div>
  );
}'''

GANTT_NEW = '''\'use client\';

import React, { useEffect, useRef, useState } from \'react\';
import { BarChart3, RefreshCw, Calendar, CheckCircle2, AlertTriangle } from \'lucide-react\';
import { api, fetchAuthenticatedBlobUrl } from \'@/lib/api\';

interface GanttPreviewProps {
  projectId: string;
  projectTitle?: string;
  initialImageUrl?: string;
}

export function GanttPreview({ projectId, projectTitle = \'Projet BTP\', initialImageUrl }: GanttPreviewProps) {
  const apiBase = (process.env.NEXT_PUBLIC_API_URL || \'\').replace(/\\/$/, \'\');
  const [rawPath, setRawPath] = useState<string>(
    initialImageUrl || `${apiBase}/api/visuals/file/tenants/11111111-1111-1111-1111-111111111111/visuals/${projectId}/gantt_planning.png`
  );
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<\'loading\' | \'ready\' | \'missing\' | \'error\'>(\'loading\');
  const [isGenerating, setIsGenerating] = useState(false);
  const [lastGenerated, setLastGenerated] = useState<string | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  async function loadImage(path: string) {
    setLoadState(\'loading\');
    try {
      const url = await fetchAuthenticatedBlobUrl(path);
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = url;
      setBlobUrl(url);
      setLoadState(\'ready\');
    } catch (err: any) {
      if (String(err?.message || \'\').includes(\'404\')) {
        setLoadState(\'missing\');
      } else {
        console.error(\'Failed to load gantt image\', err);
        setLoadState(\'error\');
      }
    }
  }

  useEffect(() => {
    loadImage(rawPath);
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawPath]);

  const handleRegenerate = async () => {
    setIsGenerating(true);
    try {
      const res = await api.generateGantt(projectId, projectTitle, []);
      setLastGenerated(`${res.total_weeks} semaines (Livraison le ${res.completion_date})`);
      // Cache-bust via un nouveau chemin s3_key + timestamp, puis recharge en tant qu\'image
      // authentifiée (plus jamais un <img src> direct vers une route protégée).
      setRawPath(`${apiBase}/api/visuals/file/${res.s3_key}?t=${Date.now()}`);
    } catch (err) {
      console.error(\'Failed to generate gantt\', err);
      setLoadState(\'error\');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-sky-400" />
            Planning Prévisionnel de Phasage (Gantt BTP)
          </h3>
          <p className="text-xs text-slate-400">
            Généré automatiquement par Python Matplotlib avec chemin critique, jalons et marge intempéries.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRegenerate}
            disabled={isGenerating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-glow disabled:opacity-50 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isGenerating ? \'animate-spin\' : \'\'}`} />
            <span>{isGenerating ? \'Calcul du Gantt...\' : \'Régénérer Gantt HD\'}</span>
          </button>
        </div>
      </div>

      {lastGenerated && (
        <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          Planning synchronisé : {lastGenerated}
        </div>
      )}

      {/* Image Preview Container */}
      <div className="relative rounded-xl border border-slate-800 overflow-hidden bg-slate-950 flex items-center justify-center p-2 min-h-[340px]">
        {loadState === \'ready\' && blobUrl ? (
          <img
            src={blobUrl}
            alt="Planning Gantt BTP"
            className="w-full h-auto rounded-lg shadow-md object-contain max-h-[500px]"
          />
        ) : loadState === \'loading\' || isGenerating ? (
          <div className="flex flex-col items-center gap-2 text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin" />
            Chargement du planning...
          </div>
        ) : loadState === \'missing\' ? (
          <div className="flex flex-col items-center gap-2 text-slate-500 text-xs text-center px-6">
            <Calendar className="w-8 h-8 text-slate-600" />
            Aucun planning généré pour ce projet pour l\'instant.
            <span>Cliquez sur « Régénérer Gantt HD » pour le créer à partir des données du chantier.</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-rose-400 text-xs text-center px-6">
            <AlertTriangle className="w-8 h-8" />
            Impossible de charger le planning (session expirée ou service indisponible).
            <span>Réessayez « Régénérer Gantt HD », ou reconnectez-vous si le problème persiste.</span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-900">
        <span>Format : PNG Haute Définition (300 DPI) • Intégration directe dans le document Word .docx</span>
        <span className="text-sky-400 font-medium">Inclus dans la section 3 (Méthodologie & Phasage)</span>
      </div>
    </div>
  );
}'''

ok2 = apply_patch(GANTT_TSX, [("full-file rewrite: authenticated blob loading", GANTT_OLD, GANTT_NEW)])

# ─────────────────────────────────────────────────────────────────────────
# 3. organigramme-preview.tsx — same treatment.
# ─────────────────────────────────────────────────────────────────────────
ORGANI_OLD = '''\'use client\';

import React, { useState } from \'react\';
import { Users, RefreshCw, CheckCircle2 } from \'lucide-react\';
import { api } from \'@/lib/api\';

interface OrganigrammePreviewProps {
  projectId: string;
  projectTitle?: string;
  initialImageUrl?: string;
}

export function OrganigrammePreview({ projectId, projectTitle = \'Projet BTP\', initialImageUrl }: OrganigrammePreviewProps) {
  const apiBase = (process.env.NEXT_PUBLIC_API_URL || \'\').replace(/\\/$/, \'\');
  const [imageUrl, setImageUrl] = useState<string>(
    initialImageUrl || `${apiBase}/api/visuals/file/tenants/11111111-1111-1111-1111-111111111111/visuals/${projectId}/organigramme_chantier.png`
  );
  const [isGenerating, setIsGenerating] = useState(false);

  const handleRegenerate = async () => {
    setIsGenerating(true);
    try {
      const res = await api.generateOrganigramme(projectId, projectTitle, []);
      setImageUrl(`${apiBase}/api/visuals/file/${res.s3_key}?t=${Date.now()}`);
    } catch (err) {
      console.error(\'Failed to generate organigramme\', err);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Users className="w-5 h-5 text-emerald-400" />
            Organigramme d\'Encadrement Chantier (BTP)
          </h3>
          <p className="text-xs text-slate-400">
            Hiérarchie opérationnelle, temps de présence effectif et qualifications des cadres (MOA, Conducteur, QSE).
          </p>
        </div>

        <button
          onClick={handleRegenerate}
          disabled={isGenerating}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-glow disabled:opacity-50 transition-all"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isGenerating ? \'animate-spin\' : \'\'}`} />
          <span>{isGenerating ? \'Mise à jour...\' : \'Régénérer Organigramme\'}</span>
        </button>
      </div>

      {/* Image Preview */}
      <div className="relative rounded-xl border border-slate-800 overflow-hidden bg-slate-950 flex items-center justify-center p-2 min-h-[320px]">
        <img
          src={imageUrl}
          alt="Organigramme BTP"
          className="w-full h-auto rounded-lg shadow-md object-contain max-h-[500px]"
          onError={() => {
            handleRegenerate();
          }}
        />
      </div>

      <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-900">
        <span>Généré depuis les données du formulaire conducteur de travaux</span>
        <span className="text-emerald-400 font-medium">Inclus dans la section 1 (Moyens Humains)</span>
      </div>
    </div>
  );
}'''

ORGANI_NEW = '''\'use client\';

import React, { useEffect, useRef, useState } from \'react\';
import { Users, RefreshCw, AlertTriangle } from \'lucide-react\';
import { api, fetchAuthenticatedBlobUrl } from \'@/lib/api\';

interface OrganigrammePreviewProps {
  projectId: string;
  projectTitle?: string;
  initialImageUrl?: string;
}

export function OrganigrammePreview({ projectId, projectTitle = \'Projet BTP\', initialImageUrl }: OrganigrammePreviewProps) {
  const apiBase = (process.env.NEXT_PUBLIC_API_URL || \'\').replace(/\\/$/, \'\');
  const [rawPath, setRawPath] = useState<string>(
    initialImageUrl || `${apiBase}/api/visuals/file/tenants/11111111-1111-1111-1111-111111111111/visuals/${projectId}/organigramme_chantier.png`
  );
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<\'loading\' | \'ready\' | \'missing\' | \'error\'>(\'loading\');
  const [isGenerating, setIsGenerating] = useState(false);
  const objectUrlRef = useRef<string | null>(null);

  async function loadImage(path: string) {
    setLoadState(\'loading\');
    try {
      const url = await fetchAuthenticatedBlobUrl(path);
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = url;
      setBlobUrl(url);
      setLoadState(\'ready\');
    } catch (err: any) {
      if (String(err?.message || \'\').includes(\'404\')) {
        setLoadState(\'missing\');
      } else {
        console.error(\'Failed to load organigramme image\', err);
        setLoadState(\'error\');
      }
    }
  }

  useEffect(() => {
    loadImage(rawPath);
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawPath]);

  const handleRegenerate = async () => {
    setIsGenerating(true);
    try {
      const res = await api.generateOrganigramme(projectId, projectTitle, []);
      setRawPath(`${apiBase}/api/visuals/file/${res.s3_key}?t=${Date.now()}`);
    } catch (err) {
      console.error(\'Failed to generate organigramme\', err);
      setLoadState(\'error\');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Users className="w-5 h-5 text-emerald-400" />
            Organigramme d\'Encadrement Chantier (BTP)
          </h3>
          <p className="text-xs text-slate-400">
            Hiérarchie opérationnelle, temps de présence effectif et qualifications des cadres (MOA, Conducteur, QSE).
          </p>
        </div>

        <button
          onClick={handleRegenerate}
          disabled={isGenerating}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-glow disabled:opacity-50 transition-all"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isGenerating ? \'animate-spin\' : \'\'}`} />
          <span>{isGenerating ? \'Mise à jour...\' : \'Régénérer Organigramme\'}</span>
        </button>
      </div>

      {/* Image Preview */}
      <div className="relative rounded-xl border border-slate-800 overflow-hidden bg-slate-950 flex items-center justify-center p-2 min-h-[320px]">
        {loadState === \'ready\' && blobUrl ? (
          <img
            src={blobUrl}
            alt="Organigramme BTP"
            className="w-full h-auto rounded-lg shadow-md object-contain max-h-[500px]"
          />
        ) : loadState === \'loading\' || isGenerating ? (
          <div className="flex flex-col items-center gap-2 text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin" />
            Chargement de l\'organigramme...
          </div>
        ) : loadState === \'missing\' ? (
          <div className="flex flex-col items-center gap-2 text-slate-500 text-xs text-center px-6">
            <Users className="w-8 h-8 text-slate-600" />
            Aucun organigramme généré pour ce projet pour l\'instant.
            <span>Cliquez sur « Régénérer Organigramme » pour le créer à partir des données du chantier.</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-rose-400 text-xs text-center px-6">
            <AlertTriangle className="w-8 h-8" />
            Impossible de charger l\'organigramme (session expirée ou service indisponible).
            <span>Réessayez « Régénérer Organigramme », ou reconnectez-vous si le problème persiste.</span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-900">
        <span>Généré depuis les données du formulaire conducteur de travaux</span>
        <span className="text-emerald-400 font-medium">Inclus dans la section 1 (Moyens Humains)</span>
      </div>
    </div>
  );
}'''

ok3 = apply_patch(ORGANI_TSX, [("full-file rewrite: authenticated blob loading", ORGANI_OLD, ORGANI_NEW)])

# ─────────────────────────────────────────────────────────────────────────
# 4. editor/page.tsx — honest completion/failure state (see module docstring).
# ─────────────────────────────────────────────────────────────────────────
ok4 = apply_patch(EDITOR_TSX, [
    (
        "add failedKeys state",
        '''  const [generating, setGenerating] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);''',
        '''  const [generating, setGenerating] = useState<Set<string>>(new Set());
  const [failedKeys, setFailedKeys] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);''',
    ),
    (
        "handleGenerate: clear/set failedKeys",
        '''  async function handleGenerate(sectionKey: string) {
    setGenerating((prev) => new Set(prev).add(sectionKey));
    try {
      const result = await api.generateSection(projectId, sectionKey);
      setSections((prev) => {
        const existing = prev.findIndex((s) => s.section_key === sectionKey);
        if (existing >= 0) {
          const updated = [...prev];
          updated[existing] = { ...updated[existing], ...result };
          return updated;
        }
        return [...prev, result];
      });
    } catch (err) {
      console.error('Generation error:', err);
      setGenerating((prev) => {
        const next = new Set(prev);
        next.delete(sectionKey);
        return next;
      });
    }
    // On ne retire PAS la clé de `generating` ici en cas de succès : la génération réelle
    // se termine en tâche de fond (Celery). Le polling ci-dessous détecte la fin
    // (status !== 'processing') et nettoie `generating` à ce moment-là.
  }''',
        '''  async function handleGenerate(sectionKey: string) {
    setGenerating((prev) => new Set(prev).add(sectionKey));
    setFailedKeys((prev) => {
      if (!prev.has(sectionKey)) return prev;
      const next = new Set(prev);
      next.delete(sectionKey);
      return next;
    });
    try {
      const result = await api.generateSection(projectId, sectionKey);
      setSections((prev) => {
        const existing = prev.findIndex((s) => s.section_key === sectionKey);
        if (existing >= 0) {
          const updated = [...prev];
          updated[existing] = { ...updated[existing], ...result };
          return updated;
        }
        return [...prev, result];
      });
    } catch (err) {
      console.error('Generation error:', err);
      setGenerating((prev) => {
        const next = new Set(prev);
        next.delete(sectionKey);
        return next;
      });
      setFailedKeys((prev) => new Set(prev).add(sectionKey));
    }
    // On ne retire PAS la clé de `generating` ici en cas de succès : la génération réelle
    // se termine en tâche de fond (Celery). Le polling ci-dessous détecte la fin
    // (status !== 'processing') et nettoie `generating` à ce moment-là -- ou signale un
    // échec explicite (statut 'failed' ou timeout) au lieu de laisser un état ambigu.
  }''',
    ),
    (
        "polling: surface failed status + timeout as visible failedKeys instead of silent clear",
        '''    pollTimer.current = setInterval(async () => {
      attempts += 1;
      try {
        const fresh = await api.getSections(projectId);
        setSections(fresh);
        setGenerating((prev) => {
          const next = new Set(prev);
          for (const key of Array.from(next)) {
            const sec = fresh.find((s) => s.section_key === key);
            if (sec && sec.status !== 'processing') {
              next.delete(key);
            }
          }
          return next;
        });
      } catch (e) {
        console.error('Polling error:', e);
      }
      if (attempts >= 20 && pollTimer.current) {
        // Sécurité : on arrête après ~80s pour ne pas boucler indéfiniment si un worker
        // reste bloqué. Un clic manuel sur "Générer avec l'IA" relance la génération.
        clearInterval(pollTimer.current);
        pollTimer.current = null;
        setGenerating(new Set());
      }
    }, 4000);''',
        '''    pollTimer.current = setInterval(async () => {
      attempts += 1;
      try {
        const fresh = await api.getSections(projectId);
        setSections(fresh);
        setGenerating((prev) => {
          const next = new Set(prev);
          for (const key of Array.from(next)) {
            const sec = fresh.find((s) => s.section_key === key);
            if (sec && sec.status !== 'processing') {
              next.delete(key);
              if (sec.status === 'failed') {
                setFailedKeys((f) => new Set(f).add(key));
              }
            }
          }
          return next;
        });
      } catch (e) {
        console.error('Polling error:', e);
      }
      if (attempts >= 20 && pollTimer.current) {
        // Sécurité : on arrête après ~80s pour ne pas boucler indéfiniment si le worker
        // Celery ne répond pas (ex. worker non démarré côté serveur). On ne masque plus
        // l'échec : toute clé encore en cours à ce stade est explicitement marquée en échec
        // (icône + message dédiés) au lieu de disparaître silencieusement.
        clearInterval(pollTimer.current);
        pollTimer.current = null;
        setGenerating((prev) => {
          if (prev.size > 0) {
            setFailedKeys((f) => {
              const next = new Set(f);
              prev.forEach((k) => next.add(k));
              return next;
            });
          }
          return new Set();
        });
      }
    }, 4000);''',
    ),
    (
        "sidebar: real completion check + failed icon/subtitle instead of placeholder-as-content",
        '''          const hasContent = Boolean(sec?.content_html) || meta.key === 'planning_gantt';
          const isKeyGenerating = generating.has(meta.key);
          const score = sec?.compliance_score;
          const isLocked = sec?.locked_for_export;

          return (
            <button
              key={meta.key}
              onClick={() => setActiveKey(meta.key)}
              className={`w-full text-left px-3 py-2.5 rounded-xl flex items-start gap-2.5 transition-all group ${
                isActive
                  ? 'bg-sky-600/20 border border-sky-500/40 text-sky-300'
                  : 'hover:bg-slate-800/60 text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="mt-0.5 shrink-0">
                {isKeyGenerating
                  ? <Loader2 className="w-3.5 h-3.5 text-sky-400 animate-spin" />
                  : isLocked
                    ? <Lock className="w-3.5 h-3.5 text-emerald-400" />
                    : hasContent
                      ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      : <div className="w-3.5 h-3.5 rounded-full border border-slate-600 border-dashed" />
                }
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-semibold leading-tight line-clamp-2">{meta.label}</p>
                {meta.key === 'planning_gantt' ? (
                  <p className="text-[10px] font-mono mt-0.5 text-sky-400">Studio Visuels</p>
                ) : score !== undefined && (
                  <p className={`text-[10px] font-mono mt-0.5 ${score >= 90 ? 'text-emerald-400' : score >= 70 ? 'text-amber-400' : 'text-rose-400'}`}>
                    Score RC : {score}%
                  </p>
                )}
              </div>''',
        '''          // "A du contenu" = un statut réellement terminé (généré / édité / validé / restauré),
          // PAS juste "content_html non-vide" -- le backend écrit un texte-placeholder
          // ("Génération en cours...") dès l'insertion en base, donc `Boolean(content_html)`
          // seul était vrai avant même que la génération réelle ait commencé (coche verte
          // trompeuse). Voir aussi le badge de score plus bas, même logique.
          const isDone = meta.key === 'planning_gantt'
            ? true
            : (sec?.status === 'generated' || sec?.status === 'edited' || sec?.status === 'validated' || sec?.status === 'restored') && Boolean(sec?.content_html);
          const hasFailed = failedKeys.has(meta.key) || sec?.status === 'failed';
          const isKeyGenerating = generating.has(meta.key);
          const score = sec?.compliance_score;
          const isLocked = sec?.locked_for_export;

          return (
            <button
              key={meta.key}
              onClick={() => setActiveKey(meta.key)}
              className={`w-full text-left px-3 py-2.5 rounded-xl flex items-start gap-2.5 transition-all group ${
                isActive
                  ? 'bg-sky-600/20 border border-sky-500/40 text-sky-300'
                  : 'hover:bg-slate-800/60 text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="mt-0.5 shrink-0">
                {isKeyGenerating
                  ? <Loader2 className="w-3.5 h-3.5 text-sky-400 animate-spin" />
                  : hasFailed
                    ? <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                    : isLocked
                      ? <Lock className="w-3.5 h-3.5 text-emerald-400" />
                      : isDone
                        ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        : <div className="w-3.5 h-3.5 rounded-full border border-slate-600 border-dashed" />
                }
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-semibold leading-tight line-clamp-2">{meta.label}</p>
                {meta.key === 'planning_gantt' ? (
                  <p className="text-[10px] font-mono mt-0.5 text-sky-400">Studio Visuels</p>
                ) : hasFailed ? (
                  <p className="text-[10px] font-mono mt-0.5 text-rose-400">Échec de génération</p>
                ) : isKeyGenerating ? (
                  <p className="text-[10px] font-mono mt-0.5 text-sky-400">Génération en cours…</p>
                ) : isDone && score !== undefined ? (
                  <p className={`text-[10px] font-mono mt-0.5 ${score >= 90 ? 'text-emerald-400' : score >= 70 ? 'text-amber-400' : 'text-rose-400'}`}>
                    Score RC : {score}%
                  </p>
                ) : (
                  <p className="text-[10px] font-mono mt-0.5 text-slate-600">Non générée</p>
                )}
              </div>''',
    ),
    (
        "fallbackSection: honest content_html/score/status instead of a fake 85 and raw placeholder text",
        '''  const fallbackSection: GeneratedSection = {
    id: `temp-${activeKey}`,
    tenant_id: '11111111-1111-1111-1111-111111111111',
    project_id: projectId,
    section_key: activeKey,
    title: activeMetaSection?.label || 'Section',
    order_index: SECTION_KEYS.findIndex((s) => s.key === activeKey),
    content_html:
      activeSection?.content_html ||
      (isActiveGenerating
        ? '<p>⏳ Génération automatique en cours à partir de votre base de connaissances (RAG)…</p>'
        : '<p>Cliquez sur "Générer avec l\\'IA" ou commencez à rédiger...</p>'),
    content_json: {},
    visual_placeholders: [],
    compliance_score: activeSection?.compliance_score || 85,
    status: activeSection?.status || 'generating',
    locked_for_export: activeSection?.locked_for_export || false,
    updated_at: new Date().toISOString(),
  };''',
        '''  const isActiveFailed = failedKeys.has(activeKey) || activeSection?.status === 'failed';
  const isActiveProcessing = activeSection?.status === 'processing';

  const fallbackSection: GeneratedSection = {
    id: `temp-${activeKey}`,
    tenant_id: '11111111-1111-1111-1111-111111111111',
    project_id: projectId,
    section_key: activeKey,
    title: activeMetaSection?.label || 'Section',
    order_index: SECTION_KEYS.findIndex((s) => s.key === activeKey),
    // Le statut 'processing' en base ne veut JAMAIS dire "contenu prêt" -- son content_html
    // n'est que le texte-placeholder écrit à l'insertion. On ne l'affiche donc plus jamais
    // tel quel : un message honnête et actionnable remplace systématiquement les états
    // échec / en cours / jamais lancée.
    content_html:
      isActiveFailed
        ? '<p style="color:#fca5a5">⚠️ La génération automatique de cette section n\\'a pas abouti (service de génération indisponible ou surchargé). Cliquez sur « Générer avec l\\'IA » pour réessayer, ou rédigez cette section manuellement.</p>'
        : (isActiveGenerating || isActiveProcessing)
          ? '<p>⏳ Génération automatique en cours à partir de votre base de connaissances (RAG)… Cela peut prendre jusqu\\'à une minute.</p>'
          : (activeSection?.content_html || '<p>Cliquez sur "Générer avec l\\'IA" ou commencez à rédiger...</p>'),
    content_json: {},
    visual_placeholders: [],
    // `?? 0` (jamais `|| 85`) : un score réel de 0 doit rester 0, pas être masqué par une
    // fausse valeur par défaut -- c'est exactement le bug "85% alors que tout est vide".
    compliance_score: activeSection?.compliance_score ?? 0,
    status: activeSection?.status || 'missing_data',
    locked_for_export: activeSection?.locked_for_export || false,
    updated_at: new Date().toISOString(),
  };''',
    ),
    (
        "compliance badge: gate on real completion, add explicit failed/processing/never-generated states",
        '''        {/* Compliance Badge */}
        {!isGanttSection && currentSection?.compliance_score !== undefined && (
          <div className={`p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 ${
            currentSection.compliance_score >= 90
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : currentSection.compliance_score >= 70
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
          }`}>
            {currentSection.compliance_score >= 90
              ? <CheckCircle2 className="w-4 h-4" />
              : <AlertTriangle className="w-4 h-4" />
            }
            Score de conformité RC : <span className="font-mono text-lg">{currentSection.compliance_score}%</span>
            {currentSection.compliance_score < 80 && ' — Des critères RC manquent dans cette section. Régénérez ou complétez manuellement.'}
          </div>
        )}''',
        '''        {/* Compliance Badge -- un état explicite par situation réelle, jamais un score
            inventé ni un silence pendant qu'une génération est bloquée. */}
        {!isGanttSection && (
          isActiveFailed ? (
            <div className="p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 bg-rose-500/10 border-rose-500/30 text-rose-300">
              <AlertTriangle className="w-4 h-4" />
              Échec de la génération automatique — aucun score de conformité disponible. Réessayez ou rédigez manuellement.
            </div>
          ) : (isActiveGenerating || isActiveProcessing) ? (
            <div className="p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 bg-sky-500/10 border-sky-500/30 text-sky-300">
              <Loader2 className="w-4 h-4 animate-spin" />
              Génération en cours — le score de conformité RC sera calculé à la fin.
            </div>
          ) : (currentSection?.status === 'generated' || currentSection?.status === 'edited' || currentSection?.status === 'validated' || currentSection?.status === 'restored') ? (
            <div className={`p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 ${
              (currentSection.compliance_score ?? 0) >= 90
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : (currentSection.compliance_score ?? 0) >= 70
                  ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
            }`}>
              {(currentSection.compliance_score ?? 0) >= 90
                ? <CheckCircle2 className="w-4 h-4" />
                : <AlertTriangle className="w-4 h-4" />
              }
              Score de conformité RC : <span className="font-mono text-lg">{currentSection.compliance_score ?? 0}%</span>
              {(currentSection.compliance_score ?? 0) < 80 && ' — Des critères RC manquent dans cette section. Régénérez ou complétez manuellement.'}
            </div>
          ) : (
            <div className="p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 bg-slate-800/60 border-slate-700 text-slate-400">
              Section non encore générée — aucun score de conformité pour l'instant.
            </div>
          )
        )}''',
    ),
])

if not (ok1 and ok2 and ok3 and ok4):
    print("\\nFAILED — see ABORT lines above. Nothing partially applied (per-file atomic).")
    sys.exit(1)

print("\\nALL BATCH-2 PATCHES APPLIED SUCCESSFULLY.")
