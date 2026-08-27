#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 5 — two concrete, scoped .docx export-fidelity fixes from the known backlog
(claude/etat-technique-btpao.md, "Constat 23/08 — Fidelite du .docx exporte"), both fixable
and verifiable WITHOUT a real uploaded client template (export_templates has 0 rows for this
tenant -- true "reproduce diagrams found in an uploaded client template" fidelity work is
blocked on the user actually uploading one; these two are not):

1. Cover page hardcoded the literal text "BTP CONSTRUCTION FRANCE" instead of the tenant's own
   name -- every exported memoire technique, for every tenant, carried a fake competitor-sounding
   company name on its own cover page regardless of branding_config. Fixed by fetching the
   Tenant row at both call sites (apps/api/app/api/export.py's synchronous /export/compile
   endpoint, and apps/api/app/workers/tasks.py's async Celery export task) and threading a real
   `company_name` (branding_config.company_name -> tenant.name -> a neutral generic fallback,
   NEVER a fake hardcoded company name) through project_data, matching the existing pattern
   already used for every other project_dict field.

2. Gantt/organigramme generation failures were silently swallowed (try/except with only a
   server-side print()) -- the section would simply render with NO figure and no explanation,
   so a user could not tell "no figure was needed" from "figure generation failed" when
   inspecting their exported .docx. Fixed by capturing a user-facing message on failure and
   rendering a clearly-flagged red italic placeholder paragraph in the section instead of
   silence, while leaving the non-blocking behavior (export still succeeds) unchanged.

Exact-match-count-of-1 verified live against the running files immediately before writing this
script (protects against drift from the other AI's concurrent edits). Aborts per-file with zero
writes on any mismatch.
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
    print("Usage: patch_batch5_exporter_fidelity.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
EXPORTER_PY = f"{REPO_ROOT}/apps/api/app/services/exporter_service.py"
EXPORT_API_PY = f"{REPO_ROOT}/apps/api/app/api/export.py"
TASKS_PY = f"{REPO_ROOT}/apps/api/app/workers/tasks.py"

results = []

# ─────────────────────────────────────────────────────────────────────────
# 1. exporter_service.py — real company_name on cover page + non-silent visual failures
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(EXPORTER_PY, [
    (
        "cover page: real company_name instead of hardcoded fake name",
        'p_header = doc.add_paragraph()\n        r_logo = p_header.add_run("BTP CONSTRUCTION FRANCE\\n")',
        'p_header = doc.add_paragraph()\n        r_logo = p_header.add_run(f"{project_data.get(\'company_name\') or \'Votre Entreprise\'}\\n")',
    ),
    (
        "init gantt_error/organigramme_error alongside paths",
        '''        gantt_path = None
        organigramme_path = None

        if include_visuals:''',
        '''        gantt_path = None
        organigramme_path = None
        gantt_error = None
        organigramme_error = None

        if include_visuals:''',
    ),
    (
        "capture gantt_error on failure",
        '''            except Exception as e:
                print(f"[ExporterService] Gantt generation error: {e}")

            try:''',
        '''            except Exception as e:
                print(f"[ExporterService] Gantt generation error: {e}")
                gantt_error = "Le planning previsionnel (Gantt) n'a pas pu etre genere automatiquement pour cet export."

            try:''',
    ),
    (
        "capture organigramme_error on failure",
        '''            except Exception as e:
                print(f"[ExporterService] Organigramme generation error: {e}")

        # 5. Render Each Section Body''',
        '''            except Exception as e:
                print(f"[ExporterService] Organigramme generation error: {e}")
                organigramme_error = "L'organigramme d'encadrement n'a pas pu etre genere automatiquement pour cet export."

        # 5. Render Each Section Body''',
    ),
    (
        "render a visible placeholder instead of silently omitting a failed figure",
        '''            if sec_key == "moyens_humains" and organigramme_path and os.path.exists(organigramme_path):
                doc.add_paragraph("\\nFigure 1 : Organigramme d'Encadrement Chantier").runs[0].italic = True
                doc.add_picture(organigramme_path, width=Inches(6.5))
                doc.add_paragraph("\\n")

            elif (sec_key == "methodologie_phasage" or sec_key == "planning_gantt") and gantt_path and os.path.exists(gantt_path):
                doc.add_paragraph("\\nFigure 2 : Planning Prévisionnel de Phasage (Gantt)").runs[0].italic = True
                doc.add_picture(gantt_path, width=Inches(6.5))
                doc.add_paragraph("\\n")''',
        '''            if sec_key == "moyens_humains":
                if organigramme_path and os.path.exists(organigramme_path):
                    doc.add_paragraph("\\nFigure 1 : Organigramme d'Encadrement Chantier").runs[0].italic = True
                    doc.add_picture(organigramme_path, width=Inches(6.5))
                    doc.add_paragraph("\\n")
                elif organigramme_error:
                    warn_p = doc.add_paragraph()
                    warn_run = warn_p.add_run(f"[Figure non disponible : {organigramme_error}]")
                    warn_run.italic = True
                    warn_run.font.color.rgb = RGBColor(185, 28, 28)

            elif sec_key == "methodologie_phasage" or sec_key == "planning_gantt":
                if gantt_path and os.path.exists(gantt_path):
                    doc.add_paragraph("\\nFigure 2 : Planning Prévisionnel de Phasage (Gantt)").runs[0].italic = True
                    doc.add_picture(gantt_path, width=Inches(6.5))
                    doc.add_paragraph("\\n")
                elif gantt_error:
                    warn_p = doc.add_paragraph()
                    warn_run = warn_p.add_run(f"[Figure non disponible : {gantt_error}]")
                    warn_run.italic = True
                    warn_run.font.color.rgb = RGBColor(185, 28, 28)''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 2. export.py — fetch Tenant, resolve real company_name, thread into project_dict
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(EXPORT_API_PY, [
    (
        "import Tenant model",
        "from app.models.entities import ExportJob, ExportTemplate, GeneratedSection, Project, ProjectDecision",
        "from app.models.entities import ExportJob, ExportTemplate, GeneratedSection, Project, ProjectDecision, Tenant",
    ),
    (
        "fetch tenant + resolve company_name, add to project_dict",
        '''    template_bytes = None
    if template and template.s3_docx_key:
        try:
            template_bytes = storage_service.download_file(current_user.tenant_id, template.s3_docx_key)
        except Exception:
            template_bytes = None

    project_dict = {
        "id": str(project.id),
        "title": project.title,
        "reference_code": project.reference_code,
        "client_name": project.client_name,
        "location": project.location,
        "lot_number": project.lot_number,
        "budget_estimate": float(project.budget_estimate) if project.budget_estimate is not None else 0.0,
    }''',
        '''    template_bytes = None
    if template and template.s3_docx_key:
        try:
            template_bytes = storage_service.download_file(current_user.tenant_id, template.s3_docx_key)
        except Exception:
            template_bytes = None

    tenant_res = await db.execute(select(Tenant).where(Tenant.id == t_uuid))
    tenant_row = tenant_res.scalar_one_or_none()
    company_name = None
    if tenant_row:
        branding = tenant_row.branding_config or {}
        company_name = branding.get("company_name") or tenant_row.name
    company_name = company_name or "Votre Entreprise"

    project_dict = {
        "id": str(project.id),
        "title": project.title,
        "reference_code": project.reference_code,
        "client_name": project.client_name,
        "location": project.location,
        "lot_number": project.lot_number,
        "budget_estimate": float(project.budget_estimate) if project.budget_estimate is not None else 0.0,
        "company_name": company_name,
    }''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 3. tasks.py — same fix for the async Celery export path (Tenant already imported)
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(TASKS_PY, [
    (
        "fetch tenant + resolve company_name, add to project_dict",
        '''                template_bytes = None
                if template and template.s3_docx_key:
                    try:
                        template_bytes = storage_service.download_file(tenant_id, template.s3_docx_key)
                    except Exception:
                        template_bytes = None

                # 4. Build Word document
                project_dict = {
                    "id": str(project.id),
                    "title": project.title,
                    "reference_code": project.reference_code,
                    "client_name": project.client_name,
                    "location": project.location,
                }''',
        '''                template_bytes = None
                if template and template.s3_docx_key:
                    try:
                        template_bytes = storage_service.download_file(tenant_id, template.s3_docx_key)
                    except Exception:
                        template_bytes = None

                tenant_res = await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))
                tenant_row = tenant_res.scalar_one_or_none()
                company_name = None
                if tenant_row:
                    branding = tenant_row.branding_config or {}
                    company_name = branding.get("company_name") or tenant_row.name
                company_name = company_name or "Votre Entreprise"

                # 4. Build Word document
                project_dict = {
                    "id": str(project.id),
                    "title": project.title,
                    "reference_code": project.reference_code,
                    "client_name": project.client_name,
                    "location": project.location,
                    "company_name": company_name,
                }''',
    ),
]))

if not all(results):
    print("\nFAILED — see ABORT lines above. Each file's patch is atomic (all-or-nothing per file).")
    sys.exit(1)

print("\nALL BATCH-5 EXPORTER FIDELITY PATCHES APPLIED SUCCESSFULLY.")
