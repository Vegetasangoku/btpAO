#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 12 (cahier des charges majeur) -- i18n rollout, step 1: the i18n-provider.tsx
engine itself.
  1. Extends t() to support {varName} interpolation (needed by editor.* strings like
     "Score RC : {score}%") while staying 100% backward compatible with every existing
     t(key)-only call site (vars is optional).
  2. Appends ~27 new 'editor.*' dictionary keys (FR/EN/AR) used by the editor page patch
     (patch_batch12_editor_page.py), which must be applied AFTER this script.
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


NEW_EDITOR_KEYS = """  'common.status_completed': { fr: 'Terminé', en: 'Completed', ar: 'مكتمل' },

  // Editor Page (Mémoire Technique -- Batch 12, rollout i18n)
  'editor.sections_title': { fr: 'Sections du Mémoire', en: 'Proposal Sections', ar: 'أقسام المذكرة' },
  'editor.section.presentation_entreprise': { fr: "1. Présentation de l'Entreprise", en: '1. Company Presentation', ar: '١. تقديم الشركة' },
  'editor.section.references_similaires': { fr: '2. Références de Travaux Similaires', en: '2. Similar Project References', ar: '٢. مراجع أعمال مماثلة' },
  'editor.section.moyens_humains': { fr: '3. Moyens Humains & Encadrement', en: '3. Human Resources & Supervision', ar: '٣. الموارد البشرية والإشراف' },
  'editor.section.moyens_materiels': { fr: '4. Moyens Matériels & Engins', en: '4. Equipment & Machinery', ar: '٤. المعدات والآليات' },
  'editor.section.methodologie_phasage': { fr: '5. Méthodologie & Planning Prévisionnel', en: '5. Methodology & Projected Schedule', ar: '٥. المنهجية والجدول الزمني' },
  'editor.section.qualite_controle': { fr: '6. Démarche Qualité & Autocontrôle', en: '6. Quality Approach & Self-Inspection', ar: '٦. الجودة والفحص الذاتي' },
  'editor.section.securite_ppsps': { fr: '7. Sécurité, Prévention & PPSPS', en: '7. Safety, Prevention & Site Safety Plan', ar: '٧. السلامة والوقاية' },
  'editor.section.rse_environnement': { fr: '8. RSE, Déchets BTP & Bilan Carbone', en: '8. CSR, Construction Waste & Carbon Footprint', ar: '٨. المسؤولية البيئية والكربون' },
  'editor.section.sous_traitance': { fr: '9. Politique de Sous-Traitance', en: '9. Subcontracting Policy', ar: '٩. سياسة المقاولة من الباطن' },
  'editor.section.planning_gantt': { fr: '10. Planning Gantt Prévisionnel', en: '10. Projected Gantt Schedule', ar: '١٠. الجدول الزمني التقديري' },
  'editor.studio_visuals': { fr: 'Studio Visuels', en: 'Visuals Studio', ar: 'استوديو الرسوم البيانية' },
  'editor.generation_failed': { fr: 'Échec de génération', en: 'Generation Failed', ar: 'فشل التوليد' },
  'editor.generating': { fr: 'Génération en cours…', en: 'Generating…', ar: 'جاري التوليد…' },
  'editor.score_rc': { fr: 'Score RC : {score}%', en: 'RC Score: {score}%', ar: 'نتيجة RC: {score}%' },
  'editor.not_generated': { fr: 'Non générée', en: 'Not generated', ar: 'لم يتم التوليد' },
  'editor.optional_tag': { fr: 'opt.', en: 'opt.', ar: 'اختياري' },
  'editor.optional_note': { fr: 'Section optionnelle — peut être omise si non requise par le RC', en: 'Optional section — may be omitted if not required by the tender rules', ar: 'قسم اختياري — يمكن حذفه إذا لم يكن مطلوباً وفق دفتر الشروط' },
  'editor.gantt_note': { fr: 'Généré automatiquement (Python/Matplotlib) — voir aussi le Studio Visuels', en: 'Automatically generated (Python/Matplotlib) — also available in the Visuals Studio', ar: 'يُنشأ تلقائياً (Python/Matplotlib) — متوفر أيضاً في استوديو الرسوم البيانية' },
  'editor.generating_ai': { fr: 'Génération IA…', en: 'AI Generating…', ar: 'التوليد بالذكاء الاصطناعي…' },
  'editor.btn_generate_ai': { fr: "Générer avec l'IA", en: 'Generate with AI', ar: 'توليد بالذكاء الاصطناعي' },
  'editor.fallback_section_title': { fr: 'Section', en: 'Section', ar: 'القسم' },
  'editor.default_project_title': { fr: 'Projet BTP', en: 'Construction Project', ar: 'مشروع بناء' },
  'editor.fallback_failed_html': { fr: 'La génération automatique de cette section n\\'a pas abouti (service de génération indisponible ou surchargé). Cliquez sur « Générer avec l\\'IA » pour réessayer, ou rédigez cette section manuellement.', en: 'Automatic generation for this section did not complete (generation service unavailable or overloaded). Click "Generate with AI" to retry, or write this section manually.', ar: 'لم تكتمل عملية التوليد التلقائي لهذا القسم (الخدمة غير متوفرة أو محملة بشكل زائد). انقر على "توليد بالذكاء الاصطناعي" لإعادة المحاولة، أو قم بالصياغة يدوياً.' },
  'editor.fallback_generating_html': { fr: 'Génération automatique en cours à partir de votre base de connaissances (RAG)… Cela peut prendre jusqu\\'à une minute.', en: 'Automatic generation in progress from your knowledge base (RAG)… This may take up to a minute.', ar: 'جارٍ التوليد التلقائي استناداً إلى قاعدة معارفكم (RAG)… قد يستغرق ذلك حتى دقيقة واحدة.' },
  'editor.fallback_empty_html': { fr: 'Cliquez sur "Générer avec l\\'IA" ou commencez à rédiger...', en: 'Click "Generate with AI" or start writing...', ar: 'انقر على "توليد بالذكاء الاصطناعي" أو ابدأ الصياغة...' },
  'editor.badge_failed': { fr: 'Échec de la génération automatique — aucun score de conformité disponible. Réessayez ou rédigez manuellement.', en: 'Automatic generation failed — no compliance score available. Retry or write this section manually.', ar: 'فشل التوليد التلقائي — لا توجد نتيجة مطابقة متاحة. أعد المحاولة أو قم بالصياغة يدوياً.' },
  'editor.badge_generating': { fr: 'Génération en cours — le score de conformité RC sera calculé à la fin.', en: 'Generation in progress — the RC compliance score will be calculated once complete.', ar: 'التوليد قيد التنفيذ — سيتم احتساب نتيجة المطابقة عند الانتهاء.' },
  'editor.badge_score_prefix': { fr: 'Score de conformité RC : ', en: 'RC Compliance Score: ', ar: 'نتيجة مطابقة RC: ' },
  'editor.badge_score_warning': { fr: ' — Des critères RC manquent dans cette section. Régénérez ou complétez manuellement.', en: ' — Some tender criteria are missing from this section. Regenerate or complete it manually.', ar: ' — تنقص بعض معايير دفتر الشروط في هذا القسم. أعد التوليد أو أكمل يدوياً.' },
  'editor.badge_not_generated': { fr: 'Section non encore générée — aucun score de conformité pour l\\'instant.', en: 'Section not yet generated — no compliance score available yet.', ar: 'لم يتم توليد هذا القسم بعد — لا توجد نتيجة مطابقة حالياً.' },
};"""

patch_file("apps/web/src/components/i18n-provider.tsx", [
    # 1. Append new dictionary keys right before the closing `};` of `dictionary`.
    (
        "  'common.status_completed': { fr: 'Terminé', en: 'Completed', ar: 'مكتمل' },\n};",
        NEW_EDITOR_KEYS,
        1,
    ),
    # 2. Widen the context type to accept optional interpolation vars.
    (
        "interface I18nContextType {\n"
        "  language: Language;\n"
        "  setLanguage: (lang: Language) => void;\n"
        "  t: (key: string) => string;\n"
        "  isRtl: boolean;\n"
        "}",
        "interface I18nContextType {\n"
        "  language: Language;\n"
        "  setLanguage: (lang: Language) => void;\n"
        "  t: (key: string, vars?: Record<string, string | number>) => string;\n"
        "  isRtl: boolean;\n"
        "}",
        1,
    ),
    # 3. Extend the real t() implementation with {varName} substitution, backward compatible
    #    (vars is optional -- every existing t(key)-only call site keeps working unchanged).
    (
        "  function t(key: string): string {\n"
        "    const entry = dictionary[key];\n"
        "    if (!entry) return key;\n"
        "    return entry[language] || entry['fr'] || key;\n"
        "  }",
        "  function t(key: string, vars?: Record<string, string | number>): string {\n"
        "    const entry = dictionary[key];\n"
        "    let str = entry ? (entry[language] || entry['fr'] || key) : key;\n"
        "    if (vars) {\n"
        "      for (const [varKey, varValue] of Object.entries(vars)) {\n"
        "        str = str.split(`{${varKey}}`).join(String(varValue));\n"
        "      }\n"
        "    }\n"
        "    return str;\n"
        "  }",
        1,
    ),
])

print("i18n-provider.tsx patched.")
