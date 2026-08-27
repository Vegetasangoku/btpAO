#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Follow-up to patch_batch2_visuals_and_status.py: that script's refactor-into-shared-helper
edit for api.ts aborted safely (0 writes) because its old_string didn't match a line with
trailing whitespace inside fetcher() (confirmed via `cat -A`: the blank line right after
`const headers = new Headers(...)` is actually "  " + newline, not empty). gantt-preview.tsx,
organigramme-preview.tsx and editor/page.tsx already applied successfully and are untouched
by this script.

Rather than re-risk another whitespace mismatch reconstructing that exact blank line,
this is a pure INSERTION anchored on a clean, already-verified region (`cat -A`-checked):
the end of fetcher() / start of `export const api = {`. It adds a small, self-contained
fetchAuthenticatedBlobUrl() with its own copy of the auth-header logic (deliberately not
sharing code with fetcher(), to avoid touching fetcher's body at all) so gantt-preview.tsx /
organigramme-preview.tsx (already patched) can load protected images via a fetch + blob: URL
instead of a bare <img src> (which 401s against get_current_tenant_user).
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
    print("Usage: patch_api_ts_blob_helper.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
API_TS = f"{REPO_ROOT}/apps/web/src/lib/api.ts"

OLD = '''}


export const api = {'''

NEW = '''}

// Charge une ressource protégée (ex. /api/visuals/file/...) via un fetch authentifié et
// retourne une blob: URL locale. Nécessaire pour tout <img src> pointant vers une route
// gardée par get_current_tenant_user : une balise <img> ne peut pas transporter d'en-tête
// Authorization, donc un accès direct y échoue systématiquement en 401 (image "cassée"
// silencieuse) même quand la génération a réellement réussi côté serveur. Copie volontairement
// la même logique d'auth que fetcher() ci-dessus plutôt que de la partager, pour ne pas avoir
// à toucher au corps de fetcher().
export async function fetchAuthenticatedBlobUrl(absoluteUrl: string): Promise<string> {
  const headers = new Headers();
  try {
    const { data } = await supabase.auth.getSession();
    if (data?.session?.access_token) {
      headers.set('Authorization', `Bearer ${data.session.access_token}`);
      const tenantId = (data.session.user.app_metadata as any)?.tenant_id || (data.session.user.user_metadata as any)?.tenant_id;
      headers.set('X-Tenant-ID', tenantId || '93365082-4489-4f0a-9e4b-9dbb219553aa');
    } else if (typeof document !== 'undefined' && process.env.NODE_ENV !== 'production') {
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
    // Requête envoyée sans en-tête Authorization : le backend renverra 401 et l'appelant
    // affichera son état "non authentifié / non généré" au lieu d'une image cassée muette.
  }
  const res = await fetch(absoluteUrl, { headers });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}


export const api = {'''

ok = apply_patch(API_TS, [("insert fetchAuthenticatedBlobUrl (self-contained)", OLD, NEW)])

if not ok:
    print("\\nFAILED — see ABORT line above.")
    sys.exit(1)

print("\\nOK — api.ts patched.")
