#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 7 — persistent "Consignes Stratégiques Générales" (Project.strategic_directives) as an
overriding-priority directive over the RAG for every AI generation, PLUS zero-click proactive
generation at project creation, PLUS zero-hallucination tag standardization to the literal
"Donnée non trouvée / Manquante", per the user's mega-spec sections 2 and 3:

  "Génération Proactive (Zero-Click) : Dès la création du dossier, l'IA pré-génère l'intégralité
  du contenu. L'éditeur ne doit jamais être vide lors de son ouverture."
  "Gestion de l'Information Manquante : ... Elle insère le tag visuel : 'Donnée non trouvée /
  Manquante'."
  "Directives Stratégiques Globales (System Prompt User) : À la création de l'AO, ajouter un
  champ de texte libre 'Consignes spécifiques générales' ... Ce champ agit comme une directive
  prioritaire qui surcharge les données du RAG."

Also fixes a real, independently-discovered pre-existing bug found while investigating this
batch: apps/web/.../wizard/page.tsx's handleGenerateMissingSections() used a stale/mismatched
set of 4 section keys ('comprehension_besoin', 'methodologie_travaux', ...) that do NOT match
the 9 real canonical section keys used by generate.py's SECTION_DEFINITIONS and by the actual
editor (apps/web/.../projects/[id]/editor/page.tsx's SECTION_KEYS) — meaning any project that
fell back to this client-side path got 4 garbage-keyed sections the editor could never display,
i.e. exactly the "éditeur vide" symptom the new spec calls out. Fixed defensively even though the
new server-side zero-click generation at creation time makes this fallback unreachable in the
normal flow.

Every block's expected occurrence count was verified live against the running files via grep
immediately before writing this script (protects against drift from the other AI's concurrent
edits, exactly like every prior batch this session). apply_patch aborts per-file with zero writes
on any mismatch — atomic per file, independent across files.
"""
import os
import sys


def apply_patch(path, replacements):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for item in replacements:
        if len(item) == 4:
            label, old, new, expected_count = item
        else:
            label, old, new = item
            expected_count = 1
        count = content.count(old)
        if count != expected_count:
            print(f"ABORT [{path}] block '{label}': found {count} occurrences (expected {expected_count}). No changes written.")
            return False
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: {path} patched ({len(replacements)} block(s)).")
    return True


if len(sys.argv) != 2:
    print("Usage: patch_batch7_strategic_directives.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
ENTITIES_PY = f"{REPO_ROOT}/apps/api/app/models/entities.py"
SCHEMAS_PY = f"{REPO_ROOT}/apps/api/app/models/schemas.py"
PROJECTS_PY = f"{REPO_ROOT}/apps/api/app/api/projects.py"
GENERATE_PY = f"{REPO_ROOT}/apps/api/app/api/generate.py"
TASKS_PY = f"{REPO_ROOT}/apps/api/app/workers/tasks.py"
LLM_GENERATOR_PY = f"{REPO_ROOT}/apps/api/app/services/llm_generator.py"
TYPES_TS = f"{REPO_ROOT}/apps/web/src/lib/types.ts"
I18N_TSX = f"{REPO_ROOT}/apps/web/src/components/i18n-provider.tsx"
WIZARD_TSX = f"{REPO_ROOT}/apps/web/src/app/dashboard/wizard/page.tsx"

results = []

# ─────────────────────────────────────────────────────────────────────────
# 1. entities.py — persistent column
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(ENTITIES_PY, [
    (
        "Project.strategic_directives column",
        '    scoring_notes = Column(JSONB, default=lambda: {"technical_weight": 60, "price_weight": 40})\n    metadata_json = Column(JSONB, default=dict)',
        '    scoring_notes = Column(JSONB, default=lambda: {"technical_weight": 60, "price_weight": 40})\n    strategic_directives = Column(Text, nullable=True)\n    metadata_json = Column(JSONB, default=dict)',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 2. schemas.py — ProjectCreate / ProjectUpdate / ProjectOut
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(SCHEMAS_PY, [
    (
        "ProjectCreate.strategic_directives",
        '''class ProjectCreate(BaseModel):
    title: str = Field(..., example="Construction du Groupe Scolaire & Gymnase HQE")
    reference_code: str = Field(..., example="AO-2026-MGP-089")
    client_name: str = Field(..., example="Métropole du Grand Paris")
    location: Optional[str] = Field(default="Saint-Denis (93)", example="Saint-Denis (93)")
    lot_number: Optional[str] = Field(default="Lot 01 - Gros Œuvre", example="Lot 01 - Gros Œuvre")
    budget_estimate: Optional[float] = Field(default=3500000.0, example=3500000.0)
    submission_deadline: Optional[datetime] = None
    scoring_notes: Dict[str, Any] = Field(
        default_factory=lambda: {"technical_weight": 60, "price_weight": 40}
    )''',
        '''class ProjectCreate(BaseModel):
    title: str = Field(..., example="Construction du Groupe Scolaire & Gymnase HQE")
    reference_code: str = Field(..., example="AO-2026-MGP-089")
    client_name: str = Field(..., example="Métropole du Grand Paris")
    location: Optional[str] = Field(default="Saint-Denis (93)", example="Saint-Denis (93)")
    lot_number: Optional[str] = Field(default="Lot 01 - Gros Œuvre", example="Lot 01 - Gros Œuvre")
    budget_estimate: Optional[float] = Field(default=3500000.0, example=3500000.0)
    submission_deadline: Optional[datetime] = None
    scoring_notes: Dict[str, Any] = Field(
        default_factory=lambda: {"technical_weight": 60, "price_weight": 40}
    )
    strategic_directives: Optional[str] = None''',
    ),
    (
        "ProjectUpdate.strategic_directives",
        '''class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    reference_code: Optional[str] = None
    client_name: Optional[str] = None
    location: Optional[str] = None
    lot_number: Optional[str] = None
    status: Optional[str] = None
    budget_estimate: Optional[float] = None
    submission_deadline: Optional[datetime] = None
    scoring_notes: Optional[Dict[str, Any]] = None''',
        '''class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    reference_code: Optional[str] = None
    client_name: Optional[str] = None
    location: Optional[str] = None
    lot_number: Optional[str] = None
    status: Optional[str] = None
    budget_estimate: Optional[float] = None
    submission_deadline: Optional[datetime] = None
    scoring_notes: Optional[Dict[str, Any]] = None
    strategic_directives: Optional[str] = None''',
    ),
    (
        "ProjectOut.strategic_directives",
        '''    submission_deadline: Optional[datetime]
    scoring_notes: Dict[str, Any]
    outcome_status: str = "pending"''',
        '''    submission_deadline: Optional[datetime]
    scoring_notes: Dict[str, Any]
    strategic_directives: Optional[str] = None
    outcome_status: str = "pending"''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 3. projects.py — imports, create_project (field + zero-click generation), update_project (field)
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(PROJECTS_PY, [
    (
        "import GeneratedSection",
        "from app.models.entities import CompanyAsset, CountryOfficialSource, DCEEmbedding, Project, ProjectGoNoGoAnalysis, Tenant, TenantLearning",
        "from app.models.entities import CompanyAsset, CountryOfficialSource, DCEEmbedding, GeneratedSection, Project, ProjectGoNoGoAnalysis, Tenant, TenantLearning",
    ),
    (
        "import billing_service",
        "from app.services.go_no_go_service import go_no_go_service\nfrom app.services.learning_service import learning_service",
        "from app.services.billing_service import billing_service\nfrom app.services.go_no_go_service import go_no_go_service\nfrom app.services.learning_service import learning_service",
    ),
    (
        "create_project: Project() constructor gains strategic_directives",
        '''        budget_estimate=payload.budget_estimate,
        submission_deadline=payload.submission_deadline,
        scoring_notes=payload.scoring_notes,
        created_at=now,
        updated_at=now,
    )''',
        '''        budget_estimate=payload.budget_estimate,
        submission_deadline=payload.submission_deadline,
        scoring_notes=payload.scoring_notes,
        strategic_directives=payload.strategic_directives,
        created_at=now,
        updated_at=now,
    )''',
    ),
    (
        "create_project: zero-click proactive generation block",
        '''    gng_out = GoNoGoSummaryOut(
        id=str(analysis.id),
        recommendation=analysis.recommendation,
        score=float(analysis.score),
        summary=analysis.summary,
        mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
        blocking_issues=analysis.blocking_issues or [],
    ) if analysis else None

    return ProjectOut(
        id=str(new_project.id),''',
        '''    gng_out = GoNoGoSummaryOut(
        id=str(analysis.id),
        recommendation=analysis.recommendation,
        score=float(analysis.score),
        summary=analysis.summary,
        mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
        blocking_issues=analysis.blocking_issues or [],
    ) if analysis else None

    # Génération Proactive (Zero-Click) : pré-génère immédiatement l'intégralité des sections
    # standard du mémoire technique, afin que l'éditeur ne soit jamais vide à l'ouverture.
    try:
        await billing_service.check_and_enforce_quota(current_user.tenant_id, action="dossier_auto_generation", db=db)
        from app.api.generate import SECTION_DEFINITIONS
        from app.workers.tasks import generate_section_task
        proactive_now = datetime.utcnow()
        for proactive_key, proactive_meta in SECTION_DEFINITIONS.items():
            if proactive_key == "qse_environnement":
                continue  # alias rétro-compatible de rse_environnement, ne pas générer en double
            db.add(GeneratedSection(
                id=uuid.uuid4(),
                tenant_id=t_uuid,
                project_id=new_project.id,
                section_key=proactive_key,
                title=proactive_meta["title"],
                order_index=proactive_meta["order"],
                content_html="<p>Génération en cours d'exécution par le worker d'IA en tâche de fond...</p>",
                content_json={},
                visual_placeholders=[],
                compliance_score=0.0,
                compliance_notes="Génération proactive automatique à la création du dossier (Celery worker)",
                status="processing",
                locked_for_export=False,
                updated_at=proactive_now,
            ))
        await db.flush()
        for proactive_key in SECTION_DEFINITIONS.keys():
            if proactive_key == "qse_environnement":
                continue
            generate_section_task.delay(
                tenant_id=current_user.tenant_id,
                project_id=str(new_project.id),
                section_key=proactive_key,
                custom_instructions=None,
            )
    except HTTPException as e:
        logger.warning(f"Génération proactive ignorée à la création (quota/abonnement) : {e.detail}")
    except Exception as e:
        logger.warning(f"Notice génération proactive à la création du dossier : {e}")

    return ProjectOut(
        id=str(new_project.id),''',
    ),
    (
        "create_project: ProjectOut return gains strategic_directives",
        '''        scoring_notes=new_project.scoring_notes or {"technical_weight": 60, "price_weight": 40},
        outcome_status=new_project.outcome_status or "pending",''',
        '''        scoring_notes=new_project.scoring_notes or {"technical_weight": 60, "price_weight": 40},
        strategic_directives=new_project.strategic_directives,
        outcome_status=new_project.outcome_status or "pending",''',
    ),
    (
        "get_project/update_project/record_project_outcome: ProjectOut return gains strategic_directives (3 identical occurrences, verified live)",
        '''        scoring_notes=project.scoring_notes or {"technical_weight": 60, "price_weight": 40},
        outcome_status=project.outcome_status or "pending",''',
        '''        scoring_notes=project.scoring_notes or {"technical_weight": 60, "price_weight": 40},
        strategic_directives=project.strategic_directives,
        outcome_status=project.outcome_status or "pending",''',
        3,
    ),
    (
        "list_projects (loop var p): ProjectOut return gains strategic_directives",
        '''                scoring_notes=p.scoring_notes or {"technical_weight": 60, "price_weight": 40},
                outcome_status=p.outcome_status or "pending",''',
        '''                scoring_notes=p.scoring_notes or {"technical_weight": 60, "price_weight": 40},
                strategic_directives=p.strategic_directives,
                outcome_status=p.outcome_status or "pending",''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 4. tasks.py — merge project.strategic_directives into custom_instructions (single source of
#    truth inside the Celery task itself, so it applies regardless of caller)
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(TASKS_PY, [
    (
        "generate_section_task: merge strategic_directives as priority override",
        '''            proj_stmt = select(Project).where(Project.id == proj_uuid, Project.tenant_id == tenant_uuid)
            proj_res = await db.execute(proj_stmt)
            project = proj_res.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {project_id} not found for tenant {tenant_id}")

            # 3. Fetch section or create new''',
        '''            proj_stmt = select(Project).where(Project.id == proj_uuid, Project.tenant_id == tenant_uuid)
            proj_res = await db.execute(proj_stmt)
            project = proj_res.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {project_id} not found for tenant {tenant_id}")

            # Directive Stratégique Générale (définie à la création du dossier) : surcharge
            # prioritaire sur le RAG et sur toute autre source pour CHAQUE génération IA.
            if getattr(project, "strategic_directives", None):
                _priority_directive = (
                    "[DIRECTIVE STRATÉGIQUE PRIORITAIRE — DÉFINIE PAR L'ENTREPRISE, PRÉVAUT SUR LE RAG "
                    f"ET TOUTE AUTRE SOURCE] {project.strategic_directives}"
                )
                custom_instructions = (
                    f"{_priority_directive}\\n\\n{custom_instructions}" if custom_instructions else _priority_directive
                )

            # 3. Fetch section or create new''',
        1,
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 5. llm_generator.py — zero-hallucination tag standardization + priority-override prompt framing
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(LLM_GENERATOR_PY, [
    (
        "anti-hallucination instruction to the LLM itself (rule 4)",
        "   - Insère immédiatement un marqueur explicite sous la forme : [Information requise de l'entreprise : Préciser le choix technique ou la référence manquante].",
        "   - Insère immédiatement un marqueur explicite sous la forme : [Donnée non trouvée / Manquante : Préciser le choix technique ou la référence manquante].",
    ),
    (
        "missing_data_alert primary code-level fallback text",
        '''            missing_data_alert = "<p style='color: #b91c1c; background: #fef2f2; padding: 8px; border-left: 4px solid #ef4444;'><strong>[Information requise de l'entreprise :</strong> Les données relatives à cette exigence spécifique ne figurent ni dans le DCE ni dans les sources web. Préciser le choix technique requis.]</p>"''',
        '''            missing_data_alert = "<p style='color: #b91c1c; background: #fef2f2; padding: 8px; border-left: 4px solid #ef4444;'><strong>[Donnée non trouvée / Manquante :</strong> Les données relatives à cette exigence spécifique ne figurent ni dans le corpus client (RAG) ni dans les sources web officielles autorisées. Préciser le choix ou l'information requise.]</p>"''',
    ),
    (
        "missing_data_alert secondary-engine fallback text",
        '''{missing_data_alert or "<p style='color: #b91c1c; background: #fef2f2; padding: 8px; border-left: 4px solid #ef4444;'><strong>[A compléter :</strong> le moteur de génération de secours ne dispose pas encore d'un gabarit dédié pour cette section précise — merci de relire et compléter ce contenu manuellement, ou de relancer la génération (un nouvel essai peut aboutir sur un appel IA réel).]</p>"}''',
        '''{missing_data_alert or "<p style='color: #b91c1c; background: #fef2f2; padding: 8px; border-left: 4px solid #ef4444;'><strong>[Donnée non trouvée / Manquante :</strong> le moteur de génération de secours ne dispose pas encore d'un gabarit dédié pour cette section précise — merci de relire et compléter ce contenu manuellement, ou de relancer la génération (un nouvel essai peut aboutir sur un appel IA réel).]</p>"}''',
    ),
    (
        "section 8 prompt header — explicit overriding-priority framing",
        '''8. CONSIGNES PARTICULIÈRES :
{custom_instructions or "Aucune instruction supplémentaire."}''',
        '''8. CONSIGNES PARTICULIÈRES (PRIORITAIRES — SURCHARGENT LES SECTIONS 1 À 7 CI-DESSUS EN CAS DE CONFLIT) :
{custom_instructions or "Aucune instruction supplémentaire."}''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 6. generate.py — prefill_draft insufficient-data HTML block wording
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(GENERATE_PY, [
    (
        "prefill_draft insufficient-data tag standardization",
        '''            saved_sec.content_html = (
                f"<div class='p-4 bg-amber-50 border-l-4 border-amber-500 text-amber-900 rounded my-2'>"
                f"<strong>Information requise :</strong> Il manque des informations sur <em>{missing_label}</em> "
                f"pour compléter cette section à partir de votre profil d'entreprise."
                f"</div>"
            )''',
        '''            saved_sec.content_html = (
                f"<div class='p-4 bg-amber-50 border-l-4 border-amber-500 text-amber-900 rounded my-2'>"
                f"<strong>[Donnée non trouvée / Manquante :</strong> Il manque des informations sur <em>{missing_label}</em> "
                f"pour compléter cette section à partir de votre profil d'entreprise.]"
                f"</div>"
            )''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 7. types.ts — Project.strategic_directives
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(TYPES_TS, [
    (
        "Project.strategic_directives field",
        '''  scoring_notes?: {
    technical_weight: number;
    price_weight: number;
  };
  go_no_go?: GoNoGoAnalysis | null;''',
        '''  scoring_notes?: {
    technical_weight: number;
    price_weight: number;
  };
  strategic_directives?: string;
  go_no_go?: GoNoGoAnalysis | null;''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 8. i18n-provider.tsx — 3 new wizard.* translation keys (fr/en/ar)
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(I18N_TSX, [
    (
        "wizard.label/placeholder/help_strategic_directives translation keys",
        '''  'wizard.optional_title': { fr: 'Titre indicatif du dossier (optionnel si détecté depuis les fichiers)', en: 'Proposal title (optional if auto-detected from files)', ar: 'عنوان الملف (اختياري في حال تم استخراجه من المستندات)' },''',
        '''  'wizard.optional_title': { fr: 'Titre indicatif du dossier (optionnel si détecté depuis les fichiers)', en: 'Proposal title (optional if auto-detected from files)', ar: 'عنوان الملف (اختياري في حال تم استخراجه من المستندات)' },
  'wizard.label_strategic_directives': { fr: 'Consignes Stratégiques Générales (prioritaires sur l\\'IA)', en: 'General Strategic Directives (overrides AI defaults)', ar: 'التوجيهات الاستراتيجية العامة (لها الأولوية على الذكاء الاصطناعي)' },
  'wizard.placeholder_strategic_directives': { fr: 'Ex : Marge de 15 %, refus du sous-traitant X, toujours mentionner la certification ISO 9001...', en: 'E.g.: 15% margin, exclude subcontractor X, always mention ISO 9001 certification...', ar: 'مثال: هامش ربح 15%، رفض المقاول من الباطن X، اذكر دائمًا شهادة ISO 9001...' },
  'wizard.help_strategic_directives': { fr: 'Ces consignes s\\'appliquent en priorité sur l\\'historique de vos anciens dossiers pour chaque génération IA de ce dossier.', en: 'These directives take priority over your historical proposal data for every AI generation in this file.', ar: 'تُطبَّق هذه التوجيهات كأولوية على بيانات ملفاتكم السابقة في كل عملية توليد بالذكاء الاصطناعي لهذا الملف.' },''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 9. wizard/page.tsx — state, JSX field (Step 1), wire into create/update calls, load effect,
#    and fix the stale/mismatched standardKeys bug in handleGenerateMissingSections
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(WIZARD_TSX, [
    (
        "add strategicDirectives state",
        "  const [estimatedBudget, setEstimatedBudget] = useState('');",
        "  const [estimatedBudget, setEstimatedBudget] = useState('');\n  const [strategicDirectives, setStrategicDirectives] = useState('');",
    ),
    (
        "load strategic_directives on existing project load",
        '''        setReferenceCode(p.reference_code || '');
        setLocation(p.location || '');''',
        '''        setReferenceCode(p.reference_code || '');
        setLocation(p.location || '');
        setStrategicDirectives(p.strategic_directives || '');''',
    ),
    (
        "wire strategic_directives into createProject call",
        '''        created = await api.createProject({
          title: title || files[0]?.name.replace(/\\.[^/.]+$/, '') || "Nouvel Appel d'Offres",
          client_name: clientName || "Acheteur Public Détecté",
          reference_code: referenceCode || `AO-${new Date().getFullYear()}-${Math.floor(Math.random() * 1000)}`,
          status: 'in_progress',
        });''',
        '''        created = await api.createProject({
          title: title || files[0]?.name.replace(/\\.[^/.]+$/, '') || "Nouvel Appel d'Offres",
          client_name: clientName || "Acheteur Public Détecté",
          reference_code: referenceCode || `AO-${new Date().getFullYear()}-${Math.floor(Math.random() * 1000)}`,
          status: 'in_progress',
          strategic_directives: strategicDirectives || undefined,
        });''',
    ),
    (
        "wire strategic_directives into updateProject call (Step 2)",
        '''        submission_deadline: submissionDeadline ? new Date(submissionDeadline).toISOString() : undefined,
      });
      setProject(updated);''',
        '''        submission_deadline: submissionDeadline ? new Date(submissionDeadline).toISOString() : undefined,
        strategic_directives: strategicDirectives || undefined,
      });
      setProject(updated);''',
    ),
    (
        "add Consignes Stratégiques Générales textarea to Step 1 form",
        '''            {/* Optional Manual Title */}
            <div className="pt-2 border-t border-slate-200 dark:border-[#1E2638]">
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                {t('wizard.optional_title')}
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t('wizard.title_placeholder')}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
              />
            </div>

            {uploadError && (''',
        '''            {/* Optional Manual Title */}
            <div className="pt-2 border-t border-slate-200 dark:border-[#1E2638]">
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                {t('wizard.optional_title')}
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t('wizard.title_placeholder')}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
              />
            </div>

            {/* Consignes Stratégiques Générales — directive prioritaire sur le RAG pour toute génération IA de ce dossier */}
            <div className="pt-2 border-t border-slate-200 dark:border-[#1E2638]">
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                {t('wizard.label_strategic_directives')}
              </label>
              <textarea
                value={strategicDirectives}
                onChange={(e) => setStrategicDirectives(e.target.value)}
                placeholder={t('wizard.placeholder_strategic_directives')}
                rows={3}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
              />
              <p className="text-[10px] text-slate-500 dark:text-slate-500 mt-1">
                {t('wizard.help_strategic_directives')}
              </p>
            </div>

            {uploadError && (''',
    ),
    (
        "fix stale/mismatched standardKeys in handleGenerateMissingSections",
        '''      const standardKeys = [
        'comprehension_besoin',
        'methodologie_travaux',
        'moyens_humains_materiels',
        'securite_qse_environnement',
      ];''',
        '''      const standardKeys = [
        'presentation_entreprise',
        'references_similaires',
        'moyens_humains',
        'moyens_materiels',
        'methodologie_phasage',
        'qualite_controle',
        'securite_ppsps',
        'rse_environnement',
        'sous_traitance',
      ];''',
    ),
]))

if not all(results):
    print("\nFAILED — see ABORT lines above. Each file's patch is atomic (all-or-nothing per file).")
    sys.exit(1)

print("\nALL BATCH-7 STRATEGIC-DIRECTIVES + ZERO-CLICK + MISSING-DATA-TAG PATCHES APPLIED SUCCESSFULLY.")
