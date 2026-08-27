#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-shot patch script applied by Claude to fix two things reported live by the user:
1. No duplicate-content detection on knowledge asset upload (a double drag-and-drop
   silently created two identical company_assets rows).
2. The frontend API client swallowed FastAPI's HTTPException `detail` message,
   so even a well-written backend error would have shown up as a cryptic
   "API error 409: Conflict" instead of the real French message.
Each replacement is verified to match EXACTLY ONCE before being applied; the script
aborts without writing anything if any expected block is not found, so it can never
silently corrupt the file.
"""
import sys

def apply_patch(path, replacements):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for label, old, new in replacements:
        count = content.count(old)
        if count != 1:
            print(f"ABORT [{path}] block '{label}': found {count} occurrences (expected 1). No changes written.")
            sys.exit(1)
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: {path} patched ({len(replacements)} block(s)).")


if len(sys.argv) != 2:
    print("Usage: patch_knowledge_upload.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
KNOWLEDGE_PY = f"{REPO_ROOT}/apps/api/app/api/knowledge.py"
API_TS = f"{REPO_ROOT}/apps/web/src/lib/api.ts"
PAGE_TSX = f"{REPO_ROOT}/apps/web/src/app/dashboard/company/page.tsx"

knowledge_replacements = [
    (
        "imports",
        "import io\nimport logging\nimport re\nimport uuid\nfrom datetime import datetime, timezone",
        "import hashlib\nimport io\nimport logging\nimport re\nimport uuid\nfrom datetime import datetime, timezone",
    ),
    (
        "dedup-check",
        '''    # 1. Check & Enforce Quota
    await billing_service.check_and_enforce_knowledge_quota(t_uuid, db=db)

    # 2. Read bytes and enforce 50 MB limit
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size > MAX_FILE_SIZE_BYTES:
        size_mb = round(file_size / (1024 * 1024), 2)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Le fichier dépasse la taille maximale autorisée de 50 Mo (taille reçue : {size_mb} Mo).",
        )

    filename_lower = file.filename.lower()''',
        '''    # 1. Check & Enforce Quota
    await billing_service.check_and_enforce_knowledge_quota(t_uuid, db=db)

    # 2. Read bytes and enforce 50 MB limit
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size > MAX_FILE_SIZE_BYTES:
        size_mb = round(file_size / (1024 * 1024), 2)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Le fichier dépasse la taille maximale autorisée de 50 Mo (taille reçue : {size_mb} Mo).",
        )

    # 2bis. Reject exact duplicate content already indexed for this tenant
    # (prevents accidental double-upload, e.g. a double drag-and-drop or double click)
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    dedup_stmt = select(CompanyAsset).where(
        CompanyAsset.tenant_id == t_uuid,
        CompanyAsset.status != "obsolete",
        CompanyAsset.metadata_json["file_hash"].astext == file_hash,
    )
    dedup_result = await db.execute(dedup_stmt)
    existing_duplicate = dedup_result.scalar_one_or_none()
    if existing_duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ce fichier est identique à un document déjà indexé : « {existing_duplicate.title} ». Supprimez-le d'abord si vous voulez le remplacer.",
        )

    filename_lower = file.filename.lower()''',
    ),
    (
        "metadata-file-hash",
        '''    metadata = {
        "source_type": "file",
        "file_name": file.filename,
        "file_size": file_size,
        "content_type": content_type,
        "status": status_state,
        "error_message": error_msg,
        "word_count": word_count,
        "s3_key": s3_key,
        "tags": [inferred_category],
        "indexed_at": now.isoformat(),
    }''',
        '''    metadata = {
        "source_type": "file",
        "file_name": file.filename,
        "file_size": file_size,
        "file_hash": file_hash,
        "content_type": content_type,
        "status": status_state,
        "error_message": error_msg,
        "word_count": word_count,
        "s3_key": s3_key,
        "tags": [inferred_category],
        "indexed_at": now.isoformat(),
    }''',
    ),
]

api_ts_replacements = [
    (
        "fetcher-error-detail",
        '''    const res = await fetch(url, {
      ...options,
      headers,
    });
    if (!res.ok) {
      throw new Error(`API error ${res.status}: ${res.statusText}`);
    }
    return await res.json();''',
        '''    const res = await fetch(url, {
      ...options,
      headers,
    });
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
      throw new Error(detail);
    }
    return await res.json();''',
    ),
]

page_tsx_replacements = [
    (
        "selected-file-confirmation",
        '''              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">{t('company.label_file')}</label>
                <input
                  type="file"
                  required
                  accept=".pdf,.docx,.doc"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full text-[11px] text-slate-500 file:mr-2 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-amber-600 file:text-white file:text-xs file:font-semibold"
                />
              </div>''',
        '''              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">{t('company.label_file')}</label>
                <input
                  type="file"
                  required
                  accept=".pdf,.docx,.doc"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full text-[11px] text-slate-500 file:mr-2 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-amber-600 file:text-white file:text-xs file:font-semibold"
                />
                {uploadFile && (
                  <p className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold truncate">
                    ✓ {uploadFile.name} sélectionné
                  </p>
                )}
              </div>''',
    ),
]

apply_patch(KNOWLEDGE_PY, knowledge_replacements)
apply_patch(API_TS, api_ts_replacements)
apply_patch(PAGE_TSX, page_tsx_replacements)
print("ALL PATCHES APPLIED SUCCESSFULLY.")
