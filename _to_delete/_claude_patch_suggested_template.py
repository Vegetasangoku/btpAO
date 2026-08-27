#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fixes GET /api/knowledge/template/suggested (get_suggested_template) step 3:
it filtered CompanyAsset.category on values ("memoire_technique",
"reference_chantier", "dossier_reference") that do NOT match any category
value the app actually writes to that column:
  - Manual upload form (company/page.tsx dropdown): fiche_technique,
    memoire_reference, certification, qse_securite, moyens_materiels
  - AI company-bootstrap service (company_bootstrap_service.py prompt):
    presentation_generale, certificat_qualibat, materiel_engins,
    cv_encadrement, demarche_rse, reference_chantier
As coded, step 3 could never match a single real row, so the "suggest a
template from your document history" feature silently always fell through
to "no template found" for every tenant. This widens the filter to the
real union of both vocabularies actually used in this codebase.
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
    print("Usage: patch_suggested_template.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
KNOWLEDGE_PY = f"{REPO_ROOT}/apps/api/app/api/knowledge.py"

replacements = [
    (
        "suggested-template-category-fix",
        '''            CompanyAsset.category.in_(["memoire_technique", "reference_chantier", "dossier_reference"]),''',
        '''            CompanyAsset.category.in_([
                # Real categories from the manual upload form (company/page.tsx)
                "fiche_technique", "memoire_reference", "certification",
                "qse_securite", "moyens_materiels",
                # Real categories from the AI company-bootstrap service
                "presentation_generale", "certificat_qualibat", "materiel_engins",
                "cv_encadrement", "demarche_rse", "reference_chantier",
            ]),''',
    ),
]

apply_patch(KNOWLEDGE_PY, replacements)
print("ALL PATCHES APPLIED SUCCESSFULLY.")
