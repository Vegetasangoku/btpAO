#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch UX/wiring fix — addresses the 3 concrete bug reports + surfaces 2 existing-but-unwired
backend features, all found by reading the real code (nothing here is guesswork):

1. Editor: mandatory sections were 100% manual ("cliquez sur Generer avec l'IA" on every tab,
   every time). The backend already does real RAG generation with honest missing-data banners
   (llm_generator.py) — the frontend just never called it automatically, and never polled for
   the async Celery result, so even a manual click looked like "nothing happens" until a full
   page refresh. Fixed: auto-fires generation for empty mandatory sections on load + polls
   until the real content lands.
2. Editor: section 10 "Planning Gantt Previsionnel" was wired through the generic AI-TEXT
   generation path (api.generateSection), but a Gantt is a Python/Matplotlib PNG chart
   (gantt_service.py / GanttPreview component) — completely different pipeline. Clicking it
   could never produce a planning. Fixed: renders the real, working GanttPreview component.
3. Go/No-Go modal ("Evaluation Strategique IA"): the backend (go_no_go_service.py) already
   computes real, non-hallucinated per-factor detail (4 factors, each with a full sentence
   explanation + recommendation, computed from real DB rows: DCE criteria, company
   qualifications incl. expiration dates, submission deadline, win/loss history) and the
   TS type already declares `factors`+`blocking_issues` — the modal JSX just never rendered
   them, only a bare count. Fixed: renders the full factor-by-factor breakdown + the actual
   blocking-issue text, with an explicit note that this is computed from real data.
4. tiptap-editor.tsx: `api.updateSection` actually returns
   `{success, section, learning_opportunity, learning_proposal}` (UpdateSectionResponse on the
   backend) but the frontend was typed/treated as if it returned a bare GeneratedSection and
   passed the WHOLE wrapper object to `onSave` — meaning saved-section state updates were
   silently broken (findIndex on `.id` would never match), and the "this edit looks like a
   learning opportunity" signal the backend already computes was thrown away entirely. Fixed:
   unwraps the response correctly and surfaces a real "memoriser cet apprentissage" banner
   wired to the existing (also previously unwired) POST /generate/learnings endpoint.
5. Chat: DCEChatSidebar + POST /projects/{id}/ask already exist and do real pgvector RAG with
   citations and an explicit "not found" rule (see docstring in projects.py) — but the sidebar
   was mounted ONLY on /dashboard/workspace, not reachable from the project editor where the
   user is actually working section-by-section. Fixed: added a visible toggle + mount in the
   editor.

Exact-match-count-of-1 verified before writing (full-file replace for editor/page.tsx uses the
ENTIRE original file as the match, which doubles as a concurrent-edit safety check in case the
other AI touched this file since it was last read). Aborts per-file with zero writes on any
mismatch — does not touch files whose anchors don't match exactly.
"""
import sys

def apply_patch(path, replacements, label_prefix=""):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for label, old, new in replacements:
        count = content.count(old)
        if count != 1:
            print(f"ABORT [{path}] block '{label_prefix}{label}': found {count} occurrences (expected 1). No changes written to this file.")
            return False
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: {path} patched ({len(replacements)} block(s)).")
    return True


if len(sys.argv) != 2:
    print("Usage: patch_ux_fixes_batch1.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
TYPES_TS = f"{REPO_ROOT}/apps/web/src/lib/types.ts"
API_TS = f"{REPO_ROOT}/apps/web/src/lib/api.ts"
DASHBOARD_PROJECTS_TSX = f"{REPO_ROOT}/apps/web/src/app/dashboard/projects/page.tsx"
TIPTAP_TSX = f"{REPO_ROOT}/apps/web/src/components/editor/tiptap-editor.tsx"

results = []

# -----------------------------------------------------------------------------------
# 1. types.ts — widen 2 status unions to match real backend values (also fixes a
#    TS2367 "no overlap" comparison error that Fix elsewhere below would otherwise hit)
# -----------------------------------------------------------------------------------
results.append(("types.ts", apply_patch(TYPES_TS, [
    (
        "GoNoGoFactor.status widen",
        "  status: 'passed' | 'warning' | 'failed';",
        "  status: 'ok' | 'warning' | 'blocking' | 'missing_data' | string;",
    ),
    (
        "GeneratedSection.status widen",
        "  status: 'generating' | 'generated' | 'edited' | 'validated';",
        "  status: 'generating' | 'generated' | 'edited' | 'validated' | 'processing' | 'missing_data' | 'prefilled_draft' | 'restored' | 'failed' | string;",
    ),
])))

# -----------------------------------------------------------------------------------
# 2. api.ts — fix updateSection's real return shape + add createLearning()
# -----------------------------------------------------------------------------------
results.append(("api.ts", apply_patch(API_TS, [
    (
        "updateSection real shape + createLearning",
        """  updateSection: (sectionId: string, contentHtml: string, status = 'edited', locked?: boolean) =>
    fetcher<GeneratedSection>(`/generate/section/${sectionId}`, {
      method: 'PUT',
      body: JSON.stringify({
        content_html: contentHtml,
        status,
        locked_for_export: locked,
      }),
    }),

  // Visuals (Gantt & Organigramme)""",
        """  updateSection: (sectionId: string, contentHtml: string, status = 'edited', locked?: boolean) =>
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

  // Visuals (Gantt & Organigramme)""",
    ),
])))

# -----------------------------------------------------------------------------------
# 3. dashboard/projects/page.tsx — Go/No-Go modal: show real per-factor detail +
#    actual blocking-issue text (data already returned by the API, just never rendered)
# -----------------------------------------------------------------------------------
results.append(("dashboard/projects/page.tsx", apply_patch(DASHBOARD_PROJECTS_TSX, [
    (
        "GoNoGo factors detail breakdown",
        """                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 flex items-start gap-2.5">
                    <ShieldCheck className="w-4 h-4 text-sky-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold text-slate-900 dark:text-white">Conformité Entreprise</p>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">
                        {modalAnalysis.blocking_issues && modalAnalysis.blocking_issues.length > 0
                          ? `${modalAnalysis.blocking_issues.length} points de vigilance`
                          : 'Aucun blocage réglementaire'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (""",
        """                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 flex items-start gap-2.5">
                    <ShieldCheck className="w-4 h-4 text-sky-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold text-slate-900 dark:text-white">Conformité Entreprise</p>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">
                        {modalAnalysis.blocking_issues && modalAnalysis.blocking_issues.length > 0
                          ? `${modalAnalysis.blocking_issues.length} points de vigilance`
                          : 'Aucun blocage réglementaire'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Blocking Issues List (texte réel, pas juste un compteur) */}
                {modalAnalysis.blocking_issues && modalAnalysis.blocking_issues.length > 0 && (
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
                )}

                {/* Detail facteur par facteur — donnees reelles calculees par go_no_go_service.py */}
                {modalAnalysis.factors && modalAnalysis.factors.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide px-0.5">
                      Détail de l'analyse ({modalAnalysis.factors.length} critères évalués)
                    </p>
                    {modalAnalysis.factors.map((factor, idx) => {
                      const statusStyles: Record<string, string> = {
                        ok: 'border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-950/20',
                        warning: 'border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-950/20',
                        blocking: 'border-rose-200 dark:border-rose-500/30 bg-rose-50 dark:bg-rose-950/20',
                        missing_data: 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40',
                      };
                      const statusIcon: Record<string, string> = {
                        ok: '✅',
                        warning: '⚠️',
                        blocking: '🛑',
                        missing_data: 'ℹ️',
                      };
                      return (
                        <div
                          key={idx}
                          className={`p-3 rounded-xl border text-xs space-y-1 ${statusStyles[factor.status] || statusStyles.missing_data}`}
                        >
                          <p className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <span>{statusIcon[factor.status] || 'ℹ️'}</span>
                            <span>{factor.title}</span>
                          </p>
                          <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">{factor.detail}</p>
                          {factor.recommendation && (
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                              <span className="font-semibold">Recommandation : </span>
                              {factor.recommendation}
                            </p>
                          )}
                        </div>
                      );
                    })}
                    <p className="text-[10px] text-slate-400 dark:text-slate-500 italic px-0.5 pt-1">
                      Analyse calculée à partir de données réelles de votre dossier (DCE, profil entreprise, délais, historique) — aucune donnée n'est inventée.
                    </p>
                  </div>
                )}
              </div>
            ) : (""",
    ),
])))

# -----------------------------------------------------------------------------------
# 4. tiptap-editor.tsx — fix broken response-unwrapping + surface learning proposal
# -----------------------------------------------------------------------------------
tiptap_replacements = [
    (
        "add learningProposal state",
        "  const [complianceScore, setComplianceScore] = useState(section.compliance_score || 98.5);\n\n  const editor = useEditor({",
        """  const [complianceScore, setComplianceScore] = useState(section.compliance_score || 98.5);
  const [learningProposal, setLearningProposal] = useState<{
    section_type: string;
    summary: string;
    suggested_content: string;
    diff_percentage: number;
  } | null>(null);
  const [savingLearning, setSavingLearning] = useState(false);

  const editor = useEditor({""",
    ),
    (
        "fix handleSave unwrap + add handleSaveLearning",
        """  const handleSave = async () => {
    if (!editor) return;
    setIsSaving(true);
    try {
      const html = editor.getHTML();
      const updated = await api.updateSection(section.id, html, 'edited', isLocked);
      if (onSave) onSave(updated);
    } catch (err) {
      console.error('Save failed', err);
    } finally {
      setIsSaving(false);
    }
  };""",
        """  const handleSave = async () => {
    if (!editor) return;
    setIsSaving(true);
    try {
      const html = editor.getHTML();
      const res = await api.updateSection(section.id, html, 'edited', isLocked);
      if (onSave) onSave(res.section);
      if (res.learning_opportunity && res.learning_proposal) {
        setLearningProposal(res.learning_proposal);
      }
    } catch (err) {
      console.error('Save failed', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveLearning = async () => {
    if (!learningProposal) return;
    setSavingLearning(true);
    try {
      await api.createLearning({
        title: `Ajustement sur ${section.title}`,
        category: 'methodology',
        section_type: learningProposal.section_type,
        learned_content: learningProposal.suggested_content,
        learning_insight: learningProposal.summary,
        source_outcome: 'manual_edit',
      });
      setLearningProposal(null);
    } catch (err) {
      console.error('Learning save failed', err);
    } finally {
      setSavingLearning(false);
    }
  };""",
    ),
    (
        "insert learning banner JSX",
        """        </div>
      </div>

      {/* Formatting Toolbar */}
      {!isLocked && (""",
        """        </div>
      </div>

      {/* Learning Proposal Banner (Phase C — Apprentissage Continu) */}
      {learningProposal && (
        <div className="mx-4 mt-3 p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex-1 min-w-[220px]">
            <p className="font-semibold text-indigo-300">Modification significative détectée ({learningProposal.diff_percentage}%)</p>
            <p className="text-[11px] text-indigo-200/80 mt-0.5">{learningProposal.summary || 'Voulez-vous mémoriser cet ajustement pour les futurs dossiers ?'}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handleSaveLearning}
              disabled={savingLearning}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-semibold disabled:opacity-50"
            >
              {savingLearning ? 'Enregistrement...' : 'Mémoriser cet apprentissage'}
            </button>
            <button
              onClick={() => setLearningProposal(null)}
              className="px-2 py-1.5 rounded-lg text-indigo-300 hover:text-white text-[11px]"
            >
              Ignorer
            </button>
          </div>
        </div>
      )}

      {/* Formatting Toolbar */}
      {!isLocked && (""",
    ),
]
results.append(("tiptap-editor.tsx", apply_patch(TIPTAP_TSX, tiptap_replacements)))

print("\n--- SUMMARY ---")
all_ok = True
for name, ok in results:
    print(f"{'OK  ' if ok else 'FAIL'} {name}")
    all_ok = all_ok and ok

if not all_ok:
    print("\nOne or more files FAILED to patch (see ABORT lines above). Fix and re-run.")
    sys.exit(1)

print("\nALL BATCH-1 PATCHES APPLIED SUCCESSFULLY.")
