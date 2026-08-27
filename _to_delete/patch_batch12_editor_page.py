#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 12 (cahier des charges majeur) -- i18n rollout, step 2: convert the editor page
(apps/web/src/app/projects/[id]/editor/page.tsx) -- the single most-used screen in the
app (technical-memo section editor) -- from hardcoded French strings to t() calls.

Must be applied AFTER patch_batch12_i18n_provider.py (depends on the new 'editor.*' keys
and the interpolation-capable t() signature it adds).

Scope: the page's own chrome (section navigator, header, status badges, generate button,
fallback content). Does NOT touch components/editor/tiptap-editor.tsx (the embedded
rich-text editor's own toolbar/AI-modal strings) -- that is a separate, large unit of
work, intentionally left for a subsequent i18n batch (see project doc).
"""
import sys

ROOT = sys.argv[1]


def patch_file(relpath, replacements):
    path = f"{ROOT}/{relpath}"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for old, new, expected_count in replacements:
        actual = content.count(old)
        if actual != expected_count:
            print(f"ABORT [{relpath}]: expected {expected_count} occurrence(s), found {actual}. "
                  f"No changes written to this file. Anchor snippet: {old[:160]!r}")
            sys.exit(1)
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: patched {relpath}")


patch_file("apps/web/src/app/projects/[id]/editor/page.tsx", [
    # 1. Import the translation hook.
    (
        "import { GeneratedSection, Project } from '@/lib/types';\n",
        "import { GeneratedSection, Project } from '@/lib/types';\n"
        "import { useTranslation } from '@/components/i18n-provider';\n",
        1,
    ),
    # 2. SECTION_KEYS: literal `label` -> `labelKey` referencing the new dictionary entries.
    #    (module-level const, so it cannot call t() itself -- resolved at render time instead).
    (
        "const SECTION_KEYS: { key: string; label: string; mandatory: boolean }[] = [\n"
        "  { key: 'presentation_entreprise',   label: \"1. Présentation de l'Entreprise\",                   mandatory: true },\n"
        "  { key: 'references_similaires',     label: '2. Références de Travaux Similaires',                mandatory: true },\n"
        "  { key: 'moyens_humains',            label: '3. Moyens Humains & Encadrement',                    mandatory: true },\n"
        "  { key: 'moyens_materiels',          label: '4. Moyens Matériels & Engins',                       mandatory: true },\n"
        "  { key: 'methodologie_phasage',      label: '5. Méthodologie & Planning Prévisionnel',            mandatory: true },\n"
        "  { key: 'qualite_controle',          label: '6. Démarche Qualité & Autocontrôle',                 mandatory: true },\n"
        "  { key: 'securite_ppsps',            label: '7. Sécurité, Prévention & PPSPS',                   mandatory: true },\n"
        "  { key: 'rse_environnement',         label: '8. RSE, Déchets BTP & Bilan Carbone',               mandatory: false },\n"
        "  { key: 'sous_traitance',            label: '9. Politique de Sous-Traitance',                     mandatory: false },\n"
        "  { key: 'planning_gantt',            label: '10. Planning Gantt Prévisionnel',                    mandatory: true },\n"
        "];",
        "const SECTION_KEYS: { key: string; labelKey: string; mandatory: boolean }[] = [\n"
        "  { key: 'presentation_entreprise',   labelKey: 'editor.section.presentation_entreprise',   mandatory: true },\n"
        "  { key: 'references_similaires',     labelKey: 'editor.section.references_similaires',     mandatory: true },\n"
        "  { key: 'moyens_humains',            labelKey: 'editor.section.moyens_humains',            mandatory: true },\n"
        "  { key: 'moyens_materiels',          labelKey: 'editor.section.moyens_materiels',          mandatory: true },\n"
        "  { key: 'methodologie_phasage',      labelKey: 'editor.section.methodologie_phasage',      mandatory: true },\n"
        "  { key: 'qualite_controle',          labelKey: 'editor.section.qualite_controle',          mandatory: true },\n"
        "  { key: 'securite_ppsps',            labelKey: 'editor.section.securite_ppsps',            mandatory: true },\n"
        "  { key: 'rse_environnement',         labelKey: 'editor.section.rse_environnement',         mandatory: false },\n"
        "  { key: 'sous_traitance',            labelKey: 'editor.section.sous_traitance',            mandatory: false },\n"
        "  { key: 'planning_gantt',            labelKey: 'editor.section.planning_gantt',            mandatory: true },\n"
        "];",
        1,
    ),
    # 3. Grab `t` from the hook.
    (
        "  const params = useParams();\n"
        "  const projectId = params.id as string;\n",
        "  const params = useParams();\n"
        "  const projectId = params.id as string;\n"
        "  const { t } = useTranslation();\n",
        1,
    ),
    # 4. fallbackSection.title
    (
        "    title: activeMetaSection?.label || 'Section',",
        "    title: activeMetaSection ? t(activeMetaSection.labelKey) : t('editor.fallback_section_title'),",
        1,
    ),
    # 5. The 3 fallback content_html strings.
    (
        "    content_html:\n"
        "      isActiveFailed\n"
        "        ? '<p style=\"color:#fca5a5\">⚠️ La génération automatique de cette section n\\'a pas abouti (service de génération indisponible ou surchargé). Cliquez sur « Générer avec l\\'IA » pour réessayer, ou rédigez cette section manuellement.</p>'\n"
        "        : (isActiveGenerating || isActiveProcessing)\n"
        "          ? '<p>⏳ Génération automatique en cours à partir de votre base de connaissances (RAG)… Cela peut prendre jusqu\\'à une minute.</p>'\n"
        "          : (activeSection?.content_html || '<p>Cliquez sur \"Générer avec l\\'IA\" ou commencez à rédiger...</p>'),",
        "    content_html:\n"
        "      isActiveFailed\n"
        "        ? `<p style=\"color:#fca5a5\">⚠️ ${t('editor.fallback_failed_html')}</p>`\n"
        "        : (isActiveGenerating || isActiveProcessing)\n"
        "          ? `<p>⏳ ${t('editor.fallback_generating_html')}</p>`\n"
        "          : (activeSection?.content_html || `<p>${t('editor.fallback_empty_html')}</p>`),",
        1,
    ),
    # 6. Sidebar column header.
    (
        '<p className="text-[10px] font-bold uppercase text-slate-500 px-2 pb-2 tracking-widest">Sections du Mémoire</p>',
        '<p className="text-[10px] font-bold uppercase text-slate-500 px-2 pb-2 tracking-widest">{t(\'editor.sections_title\')}</p>',
        1,
    ),
    # 7. Per-item label in the sidebar list.
    (
        '<p className="text-[11px] font-semibold leading-tight line-clamp-2">{meta.label}</p>',
        '<p className="text-[11px] font-semibold leading-tight line-clamp-2">{t(meta.labelKey)}</p>',
        1,
    ),
    # 8-11. The 4-way status line under each sidebar item (Gantt / failed / generating / score / not generated).
    (
        "                {meta.key === 'planning_gantt' ? (\n"
        '                  <p className="text-[10px] font-mono mt-0.5 text-sky-400">Studio Visuels</p>\n'
        "                ) : hasFailed ? (\n"
        '                  <p className="text-[10px] font-mono mt-0.5 text-rose-400">Échec de génération</p>\n'
        "                ) : isKeyGenerating ? (\n"
        '                  <p className="text-[10px] font-mono mt-0.5 text-sky-400">Génération en cours…</p>\n'
        "                ) : isDone && score !== undefined ? (\n"
        '                  <p className={`text-[10px] font-mono mt-0.5 ${score >= 90 ? \'text-emerald-400\' : score >= 70 ? \'text-amber-400\' : \'text-rose-400\'}`}>\n'
        "                    Score RC : {score}%\n"
        "                  </p>\n"
        "                ) : (\n"
        '                  <p className="text-[10px] font-mono mt-0.5 text-slate-600">Non générée</p>\n'
        "                )}",
        "                {meta.key === 'planning_gantt' ? (\n"
        '                  <p className="text-[10px] font-mono mt-0.5 text-sky-400">{t(\'editor.studio_visuals\')}</p>\n'
        "                ) : hasFailed ? (\n"
        '                  <p className="text-[10px] font-mono mt-0.5 text-rose-400">{t(\'editor.generation_failed\')}</p>\n'
        "                ) : isKeyGenerating ? (\n"
        '                  <p className="text-[10px] font-mono mt-0.5 text-sky-400">{t(\'editor.generating\')}</p>\n'
        "                ) : isDone && score !== undefined ? (\n"
        '                  <p className={`text-[10px] font-mono mt-0.5 ${score >= 90 ? \'text-emerald-400\' : score >= 70 ? \'text-amber-400\' : \'text-rose-400\'}`}>\n'
        "                    {t('editor.score_rc', { score })}\n"
        "                  </p>\n"
        "                ) : (\n"
        '                  <p className="text-[10px] font-mono mt-0.5 text-slate-600">{t(\'editor.not_generated\')}</p>\n'
        "                )}",
        1,
    ),
    # 12. "opt." badge.
    (
        '<span className="text-[9px] font-semibold text-slate-600 bg-slate-800 px-1 py-0.5 rounded shrink-0">opt.</span>',
        '<span className="text-[9px] font-semibold text-slate-600 bg-slate-800 px-1 py-0.5 rounded shrink-0">{t(\'editor.optional_tag\')}</span>',
        1,
    ),
    # 13. Header title.
    (
        '<h2 className="text-sm font-bold text-white">{activeMetaSection?.label}</h2>',
        '<h2 className="text-sm font-bold text-white">{activeMetaSection ? t(activeMetaSection.labelKey) : \'\'}</h2>',
        1,
    ),
    # 14. Optional-section note.
    (
        '<p className="text-[11px] text-slate-500">Section optionnelle — peut être omise si non requise par le RC</p>',
        '<p className="text-[11px] text-slate-500">{t(\'editor.optional_note\')}</p>',
        1,
    ),
    # 15. Gantt note.
    (
        '<p className="text-[11px] text-slate-500">Généré automatiquement (Python/Matplotlib) — voir aussi le Studio Visuels</p>',
        '<p className="text-[11px] text-slate-500">{t(\'editor.gantt_note\')}</p>',
        1,
    ),
    # 16. Generate button.
    (
        "                {isActiveGenerating\n"
        "                  ? <><Loader2 className=\"w-3.5 h-3.5 animate-spin\" /> Génération IA…</>\n"
        "                  : <><Sparkles className=\"w-3.5 h-3.5\" /> Générer avec l'IA</>\n"
        "                }",
        "                {isActiveGenerating\n"
        "                  ? <><Loader2 className=\"w-3.5 h-3.5 animate-spin\" /> {t('editor.generating_ai')}</>\n"
        "                  : <><Sparkles className=\"w-3.5 h-3.5\" /> {t('editor.btn_generate_ai')}</>\n"
        "                }",
        1,
    ),
    # 17. InteractiveGanttChart projectTitle fallback.
    (
        '<InteractiveGanttChart projectId={projectId} projectTitle={project?.title || \'Projet BTP\'} />',
        '<InteractiveGanttChart projectId={projectId} projectTitle={project?.title || t(\'editor.default_project_title\')} />',
        1,
    ),
    # 18. Compliance badge -- the 4 states.
    (
        '            <div className="p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 bg-rose-500/10 border-rose-500/30 text-rose-300">\n'
        '              <AlertTriangle className="w-4 h-4" />\n'
        "              Échec de la génération automatique — aucun score de conformité disponible. Réessayez ou rédigez manuellement.\n"
        "            </div>\n"
        "          ) : (isActiveGenerating || isActiveProcessing) ? (\n"
        '            <div className="p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 bg-sky-500/10 border-sky-500/30 text-sky-300">\n'
        '              <Loader2 className="w-4 h-4 animate-spin" />\n'
        "              Génération en cours — le score de conformité RC sera calculé à la fin.\n"
        "            </div>",
        '            <div className="p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 bg-rose-500/10 border-rose-500/30 text-rose-300">\n'
        '              <AlertTriangle className="w-4 h-4" />\n'
        "              {t('editor.badge_failed')}\n"
        "            </div>\n"
        "          ) : (isActiveGenerating || isActiveProcessing) ? (\n"
        '            <div className="p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 bg-sky-500/10 border-sky-500/30 text-sky-300">\n'
        '              <Loader2 className="w-4 h-4 animate-spin" />\n'
        "              {t('editor.badge_generating')}\n"
        "            </div>",
        1,
    ),
    (
        "              Score de conformité RC : <span className=\"font-mono text-lg\">{currentSection.compliance_score ?? 0}%</span>\n"
        "              {(currentSection.compliance_score ?? 0) < 80 && ' — Des critères RC manquent dans cette section. Régénérez ou complétez manuellement.'}\n"
        "            </div>\n"
        "          ) : (\n"
        '            <div className="p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 bg-slate-800/60 border-slate-700 text-slate-400">\n'
        "              Section non encore générée — aucun score de conformité pour l'instant.\n"
        "            </div>",
        "              {t('editor.badge_score_prefix')}<span className=\"font-mono text-lg\">{currentSection.compliance_score ?? 0}%</span>\n"
        "              {(currentSection.compliance_score ?? 0) < 80 && t('editor.badge_score_warning')}\n"
        "            </div>\n"
        "          ) : (\n"
        '            <div className="p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 bg-slate-800/60 border-slate-700 text-slate-400">\n'
        "              {t('editor.badge_not_generated')}\n"
        "            </div>",
        1,
    ),
])

print("editor/page.tsx patched.")
