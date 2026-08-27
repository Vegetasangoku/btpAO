#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-shot patch: wrap the Celery dispatch in POST /api/export/compile in a
try/except so that:
1. A broker/dispatch failure is recorded on the ExportJob row itself
   (status='failed', error_message=<real exception>) instead of leaving the
   job silently stuck in 'processing' forever with no user-visible trace.
2. The client gets a clean, honest French 503 message instead of an
   unhandled crash (which was surfacing in the browser as "Failed to fetch").
This also lets us read the real underlying exception straight out of
Postgres (export_jobs.error_message) without needing terminal/log access.
Exact-match-count-of-1 verified before writing; aborts with zero writes
if the expected block isn't found exactly once.
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
    print("Usage: patch_export_503.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
EXPORT_PY = f"{REPO_ROOT}/apps/api/app/api/export.py"

export_replacements = [
    (
        "celery-dispatch-try-except",
        '''    # 6. Dispatch asynchronous compilation task to Celery workers
    from app.workers.tasks import build_export_doc_task
    build_export_doc_task.delay(
        tenant_id=current_user.tenant_id,
        project_id=str(p_uuid),
        export_job_id=str(job_id),
        doc_format=payload.format,
        include_visuals=payload.include_gantt or payload.include_organigramme,
    )

    return ExportJobOut(''',
        '''    # 6. Dispatch asynchronous compilation task to Celery workers
    try:
        from app.workers.tasks import build_export_doc_task
        build_export_doc_task.delay(
            tenant_id=current_user.tenant_id,
            project_id=str(p_uuid),
            export_job_id=str(job_id),
            doc_format=payload.format,
            include_visuals=payload.include_gantt or payload.include_organigramme,
        )
    except Exception as e:
        new_job.status = "failed"
        new_job.error_message = f"Échec du lancement de la tâche de génération : {e.__class__.__name__}: {e}"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de génération de documents est temporairement indisponible. Veuillez réessayer dans quelques instants ; si le problème persiste, contactez le support.",
        )

    return ExportJobOut(''',
    ),
]

apply_patch(EXPORT_PY, export_replacements)
print("ALL PATCHES APPLIED SUCCESSFULLY.")
