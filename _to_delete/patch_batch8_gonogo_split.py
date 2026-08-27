#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 8 — splits the blended Go/No-Go score into two explicit, honest metrics per the user's spec
section 5 ("MODALE ÉVALUATION STRATÉGIQUE IA (DASHBOARD)"):

  1. Taux de Complétion (%) : Indique purement l'avancement du remplissage du dossier (données
     trouvées vs requises). Always computable, always shown — a pure fact, not a judgment call.
  2. Score Stratégique (Go / No-Go) : Évalue la pertinence de l'AO pour l'entreprise. "Si aucune
     donnée historique n'est disponible pour calculer ce score, masquer le composant (ne pas
     afficher de score arbitraire)."

Root cause confirmed by reading go_no_go_service.py in full: `score` starts at a hardcoded
baseline of 70.0 and every one of the 4 evaluation factors either adjusts it or leaves it
untouched when data is "missing_data" (explicitly neutral, by design, per the file's own
docstring). For a brand-new project with literally zero DCE criteria, zero company assets, zero
deadline and zero win/loss history, ALL FOUR factors hit their neutral branch, score stays at
the raw 70.0 baseline, blocking_issues is empty, and the service returns recommendation="GO" at
70% — a completely arbitrary, non-evidence-based "GO" that is exactly the bug the new spec calls
out. Fixed by tracking how many factors had real (non-"missing_data") signal and exposing
`has_sufficient_data` (True as soon as >=1 factor has real signal) so the frontend can hide the
strategic score specifically in the fully-arbitrary case, while the new `completion_rate` (based
on how many of the 9 canonical GeneratedSection keys have real generated content) is independent
of this and always shown.

Also implements "Bouton d'Enrichissement : Pour chaque critère manquant, ajouter une action 'Je
confirme être conforme' permettant d'ajouter l'information au corpus instantanément." Investigated
apps/api/app/api/knowledge.py and found `POST /knowledge/assets` (schemas.CompanyAssetCreate)
already exists, is quota-checked, generates an embedding, and is already wired in api.ts as
`addKnowledgeAsset(...)` — so this needs ZERO new backend endpoint: the button calls the existing
addKnowledgeAsset(...) to add the confirmed qualification to the corpus, then calls the existing
runGoNoGo(...) to re-evaluate for real (not fake it client-side), refreshing the modal in place.

Every block's expected occurrence count was verified live against the running files via a Python
content.count() check immediately before writing this script (protects against drift from the
other AI's concurrent edits, exactly like every prior batch this session). apply_patch aborts
per-file with zero writes on any mismatch — atomic per file, independent across files.
"""
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
    print("Usage: patch_batch8_gonogo_split.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
GO_NO_GO_SERVICE_PY = f"{REPO_ROOT}/apps/api/app/services/go_no_go_service.py"
ENTITIES_PY = f"{REPO_ROOT}/apps/api/app/models/entities.py"
SCHEMAS_PY = f"{REPO_ROOT}/apps/api/app/models/schemas.py"
PROJECTS_PY = f"{REPO_ROOT}/apps/api/app/api/projects.py"
DCE_PY = f"{REPO_ROOT}/apps/api/app/api/dce.py"
TYPES_TS = f"{REPO_ROOT}/apps/web/src/lib/types.ts"
DASHBOARD_PROJECTS_TSX = f"{REPO_ROOT}/apps/web/src/app/dashboard/projects/page.tsx"
DASHBOARD_TSX = f"{REPO_ROOT}/apps/web/src/app/dashboard/page.tsx"
PROJECT_DETAIL_TSX = f"{REPO_ROOT}/apps/web/src/app/projects/[id]/page.tsx"

results = []

# ─────────────────────────────────────────────────────────────────────────
# 1. go_no_go_service.py — completion_rate + has_sufficient_data computation & persistence
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(GO_NO_GO_SERVICE_PY, [
    (
        "import GeneratedSection",
        "from app.models.entities import CompanyAsset, DCECriterionEntity, Project, ProjectGoNoGoAnalysis, User",
        "from app.models.entities import CompanyAsset, DCECriterionEntity, GeneratedSection, Project, ProjectGoNoGoAnalysis, User",
    ),
    (
        "add REQUIRED_SECTION_KEYS / COMPLETED_SECTION_STATUSES module constants",
        "class GoNoGoService:",
        '''# Clés canoniques des 9 sections texte du mémoire technique (alignées sur generate.py's
# SECTION_DEFINITIONS, alias "qse_environnement" exclu) — dupliquées ici volontairement pour
# éviter un import services -> api (sens interdit dans l'architecture en couches du projet).
REQUIRED_SECTION_KEYS = [
    "presentation_entreprise",
    "references_similaires",
    "moyens_humains",
    "moyens_materiels",
    "methodologie_phasage",
    "qualite_controle",
    "securite_ppsps",
    "rse_environnement",
    "sous_traitance",
]
COMPLETED_SECTION_STATUSES = {"generated", "prefilled_draft", "restored"}


class GoNoGoService:''',
    ),
    (
        "fetch GeneratedSection rows + compute completion_rate (Taux de Complétion)",
        '''        hist_res = await db.execute(hist_stmt)
        hist_counts = dict(hist_res.all())

        factors: List[GoNoGoFactor] = []''',
        '''        hist_res = await db.execute(hist_stmt)
        hist_counts = dict(hist_res.all())

        # 6. Fetch Generated Sections to compute the Taux de Complétion (données trouvées vs
        # requises) — une métrique factuelle, indépendante du Score Stratégique ci-dessous.
        sec_stmt = select(GeneratedSection.section_key, GeneratedSection.status).where(
            GeneratedSection.project_id == project_id,
            GeneratedSection.tenant_id == tenant_id,
        )
        sec_res = await db.execute(sec_stmt)
        completed_keys = {
            key for key, sec_status in sec_res.all()
            if key in REQUIRED_SECTION_KEYS and sec_status in COMPLETED_SECTION_STATUSES
        }
        completion_rate = round((len(completed_keys) / len(REQUIRED_SECTION_KEYS)) * 100.0, 1)

        factors: List[GoNoGoFactor] = []''',
    ),
    (
        "compute has_sufficient_data before final recommendation",
        '''        # ---------------------------------------------------------------------
        # Final Recommendation & Score Boundaries
        # ---------------------------------------------------------------------
        final_score = max(0.0, min(100.0, round(score, 1)))''',
        '''        # ---------------------------------------------------------------------
        # Data Sufficiency Gate — évite un Score Stratégique arbitraire (ex : dossier vierge,
        # les 4 facteurs neutres "missing_data", score qui reste au baseline 70.0 sans aucun
        # signal réel). Le frontend masque le composant Score Stratégique quand ce flag est False,
        # tout en affichant toujours le Taux de Complétion (donnée factuelle, jamais arbitraire).
        # ---------------------------------------------------------------------
        real_data_factors = sum(1 for f in factors if f.status != "missing_data")
        has_sufficient_data = real_data_factors >= 1

        # ---------------------------------------------------------------------
        # Final Recommendation & Score Boundaries
        # ---------------------------------------------------------------------
        final_score = max(0.0, min(100.0, round(score, 1)))''',
    ),
    (
        "persist completion_rate + has_sufficient_data (new-record and update branches)",
        '''        if not analysis_record:
            analysis_record = ProjectGoNoGoAnalysis(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                project_id=project_id,
                recommendation=recommendation,
                score=final_score,
                summary=summary,
                factors=factors_json,
                mandatory_criteria_met=len(blocking_issues) == 0,
                blocking_issues=blocking_issues,
                evaluated_by=valid_user_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(analysis_record)
        else:
            analysis_record.recommendation = recommendation
            analysis_record.score = final_score
            analysis_record.summary = summary
            analysis_record.factors = factors_json
            analysis_record.mandatory_criteria_met = len(blocking_issues) == 0
            analysis_record.blocking_issues = blocking_issues
            if valid_user_id:
                analysis_record.evaluated_by = valid_user_id
            analysis_record.updated_at = datetime.now(timezone.utc)''',
        '''        if not analysis_record:
            analysis_record = ProjectGoNoGoAnalysis(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                project_id=project_id,
                recommendation=recommendation,
                score=final_score,
                summary=summary,
                factors=factors_json,
                mandatory_criteria_met=len(blocking_issues) == 0,
                blocking_issues=blocking_issues,
                completion_rate=completion_rate,
                has_sufficient_data=has_sufficient_data,
                evaluated_by=valid_user_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(analysis_record)
        else:
            analysis_record.recommendation = recommendation
            analysis_record.score = final_score
            analysis_record.summary = summary
            analysis_record.factors = factors_json
            analysis_record.mandatory_criteria_met = len(blocking_issues) == 0
            analysis_record.blocking_issues = blocking_issues
            analysis_record.completion_rate = completion_rate
            analysis_record.has_sufficient_data = has_sufficient_data
            if valid_user_id:
                analysis_record.evaluated_by = valid_user_id
            analysis_record.updated_at = datetime.now(timezone.utc)''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 2. entities.py — ProjectGoNoGoAnalysis persisted columns
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(ENTITIES_PY, [
    (
        "ProjectGoNoGoAnalysis.completion_rate + has_sufficient_data columns",
        '''    mandatory_criteria_met = Column(Boolean, default=True, nullable=False)
    blocking_issues = Column(JSONB, default=list, nullable=False)
    evaluated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)''',
        '''    mandatory_criteria_met = Column(Boolean, default=True, nullable=False)
    blocking_issues = Column(JSONB, default=list, nullable=False)
    completion_rate = Column(Numeric(5, 2), nullable=True)
    has_sufficient_data = Column(Boolean, default=True, nullable=False)
    evaluated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 3. schemas.py — GoNoGoSummaryOut + GoNoGoAnalysisOut gain the 2 new fields (identical
#    addition needed in both classes, verified live as the only 2 occurrences in the file)
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(SCHEMAS_PY, [
    (
        "GoNoGoSummaryOut + GoNoGoAnalysisOut: completion_rate / has_sufficient_data fields",
        '''    blocking_issues: List[str] = Field(default_factory=list)''',
        '''    blocking_issues: List[str] = Field(default_factory=list)
    completion_rate: Optional[float] = None
    has_sufficient_data: bool = True''',
        2,
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 4. projects.py — 4 GoNoGoSummaryOut(...) construction sites (2 distinct indentation
#    patterns verified live: 1 inside the list-loop at deeper indent, 3 at function-body indent)
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(PROJECTS_PY, [
    (
        "list-loop GoNoGoSummaryOut (deeper indent, 1 occurrence)",
        '''        gng_out = GoNoGoSummaryOut(
            id=str(analysis.id),
            recommendation=analysis.recommendation,
            score=float(analysis.score),
            summary=analysis.summary,
            mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
            blocking_issues=analysis.blocking_issues or [],
        ) if analysis else None''',
        '''        gng_out = GoNoGoSummaryOut(
            id=str(analysis.id),
            recommendation=analysis.recommendation,
            score=float(analysis.score),
            summary=analysis.summary,
            mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
            blocking_issues=analysis.blocking_issues or [],
            completion_rate=float(analysis.completion_rate) if analysis.completion_rate is not None else None,
            has_sufficient_data=bool(analysis.has_sufficient_data),
        ) if analysis else None''',
    ),
    (
        "create_project/update_project/record_project_outcome GoNoGoSummaryOut (3 occurrences, verified live)",
        '''        id=str(analysis.id),
        recommendation=analysis.recommendation,
        score=float(analysis.score),
        summary=analysis.summary,
        mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
        blocking_issues=analysis.blocking_issues or [],
    ) if analysis else None''',
        '''        id=str(analysis.id),
        recommendation=analysis.recommendation,
        score=float(analysis.score),
        summary=analysis.summary,
        mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
        blocking_issues=analysis.blocking_issues or [],
        completion_rate=float(analysis.completion_rate) if analysis.completion_rate is not None else None,
        has_sufficient_data=bool(analysis.has_sufficient_data),
    ) if analysis else None''',
        3,
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 5. dce.py — 2 GoNoGoAnalysisOut(...) construction sites (POST + GET /go-no-go/{project_id})
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(DCE_PY, [
    (
        "GoNoGoAnalysisOut: completion_rate / has_sufficient_data (2 occurrences, verified live)",
        '''        mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
        blocking_issues=analysis.blocking_issues or [],
        evaluated_by=str(analysis.evaluated_by) if analysis.evaluated_by else None,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )''',
        '''        mandatory_criteria_met=bool(analysis.mandatory_criteria_met),
        blocking_issues=analysis.blocking_issues or [],
        completion_rate=float(analysis.completion_rate) if analysis.completion_rate is not None else None,
        has_sufficient_data=bool(analysis.has_sufficient_data),
        evaluated_by=str(analysis.evaluated_by) if analysis.evaluated_by else None,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )''',
        2,
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 6. types.ts — GoNoGoAnalysis gains the 2 new fields
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(TYPES_TS, [
    (
        "GoNoGoAnalysis.completion_rate / has_sufficient_data",
        '''  mandatory_criteria_met: boolean;
  blocking_issues: string[];
  evaluated_by?: string;''',
        '''  mandatory_criteria_met: boolean;
  blocking_issues: string[];
  completion_rate?: number;
  has_sufficient_data?: boolean;
  evaluated_by?: string;''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 7. dashboard/projects/page.tsx — the "Évaluation Stratégique IA" modal: completion bar
#    (always shown), Score Banner hidden when has_sufficient_data===false, "Je confirme être
#    conforme" button per blocking issue (reuses existing addKnowledgeAsset + runGoNoGo, no new
#    backend endpoint needed), plus hasScore gains the sufficiency gate for the 2 compact badges
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(DASHBOARD_PROJECTS_TSX, [
    (
        "hasScore gains sufficiency gate (fixes both compact card badges via shared variable)",
        '''            const hasScore = projectScore && typeof projectScore.score === 'number';''',
        '''            const hasScore = projectScore && typeof projectScore.score === 'number' && projectScore.has_sufficient_data !== false;''',
    ),
    (
        "add confirmingIssue state",
        '''  const [loadingModalScore, setLoadingModalScore] = useState(false);
  const [recalculatingScore, setRecalculatingScore] = useState(false);''',
        '''  const [loadingModalScore, setLoadingModalScore] = useState(false);
  const [recalculatingScore, setRecalculatingScore] = useState(false);
  const [confirmingIssue, setConfirmingIssue] = useState<string | null>(null);''',
    ),
    (
        "add handleConfirmCompliance handler after handleRecalculateModalScore",
        '''  async function handleRecalculateModalScore() {
    if (!selectedModalProject) return;
    setRecalculatingScore(true);
    try {
      const res = await api.runGoNoGo(selectedModalProject.id);
      setModalAnalysis(res);
      setScoresMap((prev) => ({ ...prev, [selectedModalProject.id]: res }));
    } catch (err: any) {
      alert('Erreur calcul Go/No-Go : ' + (err?.message || err));
    } finally {
      setRecalculatingScore(false);
    }
  }''',
        '''  async function handleRecalculateModalScore() {
    if (!selectedModalProject) return;
    setRecalculatingScore(true);
    try {
      const res = await api.runGoNoGo(selectedModalProject.id);
      setModalAnalysis(res);
      setScoresMap((prev) => ({ ...prev, [selectedModalProject.id]: res }));
    } catch (err: any) {
      alert('Erreur calcul Go/No-Go : ' + (err?.message || err));
    } finally {
      setRecalculatingScore(false);
    }
  }

  // "Je confirme être conforme" — ajoute le critère manquant au corpus entreprise (via l'endpoint
  // existant /knowledge/assets) puis relance un vrai recalcul Go/No-Go (pas de score simulé
  // côté client) pour refléter instantanément l'information nouvellement disponible.
  async function handleConfirmCompliance(issue: string) {
    if (!selectedModalProject) return;
    setConfirmingIssue(issue);
    try {
      const label = issue.includes(':') ? issue.split(':').slice(1).join(':').trim() : issue;
      await api.addKnowledgeAsset({
        category: 'certificat_qualibat',
        title: label || issue,
        description: `Conformité confirmée manuellement par l'utilisateur depuis le module Go/No-Go, suite au point bloquant : "${issue}".`,
        tags: ['confirmation_manuelle', 'go_no_go'],
      });
      const refreshed = await api.runGoNoGo(selectedModalProject.id);
      setModalAnalysis(refreshed);
      setScoresMap((prev) => ({ ...prev, [selectedModalProject.id]: refreshed }));
    } catch (err: any) {
      alert("Erreur lors de la confirmation de conformité : " + (err?.message || err));
    } finally {
      setConfirmingIssue(null);
    }
  }''',
    ),
    (
        "Score Banner: always-visible Taux de Complétion bar + hide Score Stratégique when insufficient data",
        '''                {/* Score Banner */}
                <div className="p-5 rounded-2xl bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 flex items-center justify-between gap-4">''',
        '''                {/* Taux de Complétion — avancement factuel du remplissage du dossier, toujours affiché */}
                <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wide">Taux de Complétion du Dossier</span>
                    <span className="text-sm font-black font-mono text-slate-900 dark:text-white">
                      {Math.round(modalAnalysis.completion_rate ?? 0)}%
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-amber-500 transition-all"
                      style={{ width: `${Math.min(100, Math.max(0, modalAnalysis.completion_rate ?? 0))}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-slate-500 dark:text-slate-500">
                    Données trouvées vs. requises pour ce dossier (sections du mémoire technique générées).
                  </p>
                </div>

                {/* Score Stratégique — masqué si aucune donnée réelle ne permet de le justifier (jamais de score arbitraire) */}
                {modalAnalysis.has_sufficient_data === false ? (
                  <div className="p-5 rounded-2xl bg-slate-50 dark:bg-slate-950/80 border border-dashed border-slate-300 dark:border-slate-700 text-center space-y-1.5">
                    <p className="text-xs font-bold text-slate-600 dark:text-slate-400">Score Stratégique non disponible</p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-500 max-w-sm mx-auto">
                      Données insuffisantes (DCE, qualifications, délais, historique) pour évaluer la pertinence stratégique de cet AO. Complétez le profil entreprise ou le DCE pour débloquer ce score.
                    </p>
                  </div>
                ) : (
                <div className="p-5 rounded-2xl bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 flex items-center justify-between gap-4">''',
    ),
    (
        "Score Banner closing div gains the ternary's else-branch close",
        '''                    <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Score Global</span>
                  </div>
                </div>''',
        '''                    <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Score Global</span>
                  </div>
                </div>
                )}''',
    ),
    (
        "blocking issues list gains the 'Je confirme être conforme' button per issue",
        '''                {modalAnalysis.blocking_issues && modalAnalysis.blocking_issues.length > 0 && (
                  <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-500/30 space-y-1.5">
                    <p className="text-[11px] font-bold text-rose-700 dark:text-rose-300 uppercase tracking-wide">Points bloquants identifiés</p>
                    <ul className="space-y-1">
                      {modalAnalysis.blocking_issues.map((issue, idx) => (
                        <li key={idx} className="text-[11px] text-rose-700 dark:text-rose-300 flex items-start gap-1.5">
                          <span className="mt-0.5">•</span>
                          <span>{issue}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}''',
        '''                {modalAnalysis.blocking_issues && modalAnalysis.blocking_issues.length > 0 && (
                  <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-500/30 space-y-1.5">
                    <p className="text-[11px] font-bold text-rose-700 dark:text-rose-300 uppercase tracking-wide">Points bloquants identifiés</p>
                    <ul className="space-y-2">
                      {modalAnalysis.blocking_issues.map((issue, idx) => (
                        <li key={idx} className="text-[11px] text-rose-700 dark:text-rose-300 flex items-start justify-between gap-2">
                          <span className="flex items-start gap-1.5">
                            <span className="mt-0.5">•</span>
                            <span>{issue}</span>
                          </span>
                          <button
                            type="button"
                            onClick={() => handleConfirmCompliance(issue)}
                            disabled={confirmingIssue === issue}
                            className="shrink-0 flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-700 dark:text-emerald-400 text-[10px] font-semibold disabled:opacity-50 transition-colors cursor-pointer"
                          >
                            {confirmingIssue === issue ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <Check className="w-3 h-3" />
                            )}
                            <span>Je confirme être conforme</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 8. dashboard/page.tsx — compact per-row badge hidden when has_sufficient_data===false
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(DASHBOARD_TSX, [
    (
        "compact badge gains sufficiency gate",
        '''                      {p.go_no_go && (
                        <span
                          className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${''',
        '''                      {p.go_no_go && p.go_no_go.has_sufficient_data !== false && (
                        <span
                          className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 9. projects/[id]/page.tsx — hero badge hidden when has_sufficient_data===false
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(PROJECT_DETAIL_TSX, [
    (
        "hero badge gains sufficiency gate",
        '''            {project.go_no_go && (
              <span
                className={`text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full border ${''',
        '''            {project.go_no_go && project.go_no_go.has_sufficient_data !== false && (
              <span
                className={`text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full border ${''',
    ),
]))

if not all(results):
    print("\nFAILED — see ABORT lines above. Each file's patch is atomic (all-or-nothing per file).")
    sys.exit(1)

print("\nALL BATCH-8 GO/NO-GO SPLIT PATCHES APPLIED SUCCESSFULLY.")
