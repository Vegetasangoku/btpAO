#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fixes a real section-key mismatch found while investigating the user's "generation quality
will be crap" fear:

- The editor UI's real section keys are: presentation_entreprise, references_similaires,
  moyens_humains, moyens_materiels, methodologie_phasage, qualite_controle, securite_ppsps,
  rse_environnement, sous_traitance (+ planning_gantt, handled separately as a visual).
- generate.py's SECTION_DEFINITIONS only knew 5 of these 9 (and one of the 5, "qse_environnement",
  doesn't even match the real "rse_environnement" key the frontend sends). Every unmatched key
  fell back to a generic "Section <key>" title with order=99 — meaning 5 of 9 real sections
  would be saved to the DB (and therefore exported to Word) under a wrong title and dumped at
  the end regardless of their real position (1st, 2nd, 6th, 8th, 9th).
- Separately, llm_generator.py's _generate_specialized_btp_section() — the FALLBACK template
  engine used only when the real Claude/Mistral/OpenAI API call fails — had an if/elif/elif/elif/
  else with only 4 real branches; the catch-all `else` was hardcoded to ALWAYS render a
  "Securite, Sante et Assurance Qualite" section regardless of which section was actually being
  generated. So presentation_entreprise / references_similaires / qualite_controle /
  sous_traitance / rse_environnement would all silently render the WRONG (security-themed)
  content under their own heading if that fallback path ever fired. Confirmed the real API path
  IS configured (ANTHROPIC_API_KEY is set) so this fallback is secondary, not primary — but it's
  a real correctness bug worth closing rather than leaving as a landmine.

Fix:
1. generate.py: SECTION_DEFINITIONS now lists all 9 real text-section keys with correct
   titles/order, matching the editor UI exactly.
2. llm_generator.py: the environmental branch now matches BOTH "qse_environnement" (kept for
   backward compat with existing tests) AND the real "rse_environnement" key. securite_ppsps
   is promoted to its own explicit branch. The catch-all fallback no longer hardcodes an
   unrelated "Securite" heading — it uses the REAL section_title and clearly flags itself as a
   generic/secondary template needing review, instead of silently presenting wrong-topic
   content as a finished answer.

Exact-match-count-of-1 verified before writing; aborts per-file with zero writes on mismatch.
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
    print("Usage: patch_backend_section_keys.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
GENERATE_PY = f"{REPO_ROOT}/apps/api/app/api/generate.py"
LLM_GEN_PY = f"{REPO_ROOT}/apps/api/app/services/llm_generator.py"

ok1 = apply_patch(GENERATE_PY, [
    (
        "SECTION_DEFINITIONS full 9-key alignment",
        '''SECTION_DEFINITIONS = {
    "moyens_humains": {"title": "1. Moyens Humains & Organisation du Chantier", "order": 1},
    "moyens_materiels": {"title": "2. Moyens Matériels & Plan d'Installation de Chantier (PIC)", "order": 2},
    "methodologie_phasage": {"title": "3. Méthodologie d'Exécution & Phasage des Travaux", "order": 3},
    "qse_environnement": {"title": "4. Démarche RSE, Environnement & Gestion des Déchets", "order": 4},
    "securite_ppsps": {"title": "5. Sécurité, Santé (PPSPS) & Plan d'Assurance Qualité (PAQ)", "order": 5},
}''',
        '''SECTION_DEFINITIONS = {
    # Aligné sur les clés réelles envoyées par l'éditeur (apps/web .../projects/[id]/editor/page.tsx).
    # "qse_environnement" est conservé en alias pour compatibilité ascendante (tests, anciennes
    # données) — voir llm_generator.py qui accepte les deux clés pour la génération.
    "presentation_entreprise": {"title": "1. Présentation de l'Entreprise", "order": 1},
    "references_similaires": {"title": "2. Références de Travaux Similaires", "order": 2},
    "moyens_humains": {"title": "3. Moyens Humains & Encadrement", "order": 3},
    "moyens_materiels": {"title": "4. Moyens Matériels & Engins", "order": 4},
    "methodologie_phasage": {"title": "5. Méthodologie & Planning Prévisionnel", "order": 5},
    "qualite_controle": {"title": "6. Démarche Qualité & Autocontrôle", "order": 6},
    "securite_ppsps": {"title": "7. Sécurité, Prévention & PPSPS", "order": 7},
    "rse_environnement": {"title": "8. RSE, Déchets BTP & Bilan Carbone", "order": 8},
    "qse_environnement": {"title": "8. RSE, Déchets BTP & Bilan Carbone", "order": 8},  # alias
    "sous_traitance": {"title": "9. Politique de Sous-Traitance", "order": 9},
    # "planning_gantt" (10) n'est PAS une section texte : c'est un visuel Matplotlib généré
    # par /api/visuals/gantt, jamais par cet endpoint.
}''',
    ),
])

ok2 = apply_patch(LLM_GEN_PY, [
    (
        "environmental + securite branches + honest generic fallback",
        '''        elif section_key == "qse_environnement":
            html = f"""
            <h2>4. Démarche Environnementale (RSE) & Gestion des Déchets</h2>
            <p>Notre démarche s'inscrit dans les plus hauts standards de la construction durable :</p>
            <p><strong>Engagements environnementaux :</strong> {rse}. [Source : Entreprise - Charte RSE]</p>
            {internal_cite}
            <p><strong>Plan de gestion et valorisation des déchets :</strong> {dechets}.</p>
            <h3>4.1 Traçabilité des déchets et filières agréées</h3>
            <p>Chaque rotation de benne fait l'objet d'un suivi strict sous le régime : <strong>{reg.get('waste_tracking_regime', 'BSD dématérialisé')}</strong>.</p>
            {missing_data_alert}
            {learnings_html}
            {web_cites_html}
            """
            score = 99.0
            notes = "Taux de valorisation 88%, béton bas carbone et sources web intégrées."

        else:  # securite_ppsps
            html = f"""
            <h2>5. Sécurité, Santé et Assurance Qualité</h2>
            <p>La politique Zéro Accident constitue l'engagement fondamental de notre encadrement sous le régime : <strong>{reg.get('safety_plan_regime')}</strong>.</p>
            <p><strong>Mesures de sécurité opérationnelles :</strong> {securite}.</p>
            {internal_cite}
            {missing_data_alert}
            {learnings_html}
            {web_cites_html}
            """

            score = 98.0
            notes = "Procédure de sécurité complète avec PAQ et causeries hebdomadaires."

        return {''',
        '''        elif section_key in ("qse_environnement", "rse_environnement"):
            html = f"""
            <h2>{section_title}</h2>
            <p>Notre démarche s'inscrit dans les plus hauts standards de la construction durable :</p>
            <p><strong>Engagements environnementaux :</strong> {rse}. [Source : Entreprise - Charte RSE]</p>
            {internal_cite}
            <p><strong>Plan de gestion et valorisation des déchets :</strong> {dechets}.</p>
            <h3>Traçabilité des déchets et filières agréées</h3>
            <p>Chaque rotation de benne fait l'objet d'un suivi strict sous le régime : <strong>{reg.get('waste_tracking_regime', 'BSD dématérialisé')}</strong>.</p>
            {missing_data_alert}
            {learnings_html}
            {web_cites_html}
            """
            score = 99.0
            notes = "Taux de valorisation 88%, béton bas carbone et sources web intégrées."

        elif section_key == "securite_ppsps":
            html = f"""
            <h2>{section_title}</h2>
            <p>La politique Zéro Accident constitue l'engagement fondamental de notre encadrement sous le régime : <strong>{reg.get('safety_plan_regime')}</strong>.</p>
            <p><strong>Mesures de sécurité opérationnelles :</strong> {securite}.</p>
            {internal_cite}
            {missing_data_alert}
            {learnings_html}
            {web_cites_html}
            """

            score = 98.0
            notes = "Procédure de sécurité complète avec PAQ et causeries hebdomadaires."

        else:
            # Gabarit générique mais honnête pour toute clé sans template dédié
            # (presentation_entreprise, references_similaires, qualite_controle,
            # sous_traitance, ou toute clé future). N'invente JAMAIS un contenu hors-sujet :
            # utilise le vrai section_title au lieu d'un intitulé codé en dur. Ce chemin ne
            # s'exécute que si l'appel LLM réel (Claude/Mistral/OpenAI) a échoué au-dessus.
            html = f"""
            <h2>{section_title}</h2>
            <p>Cette section est rédigée pour le projet <strong>{project_title}</strong>, conformément au cadre réglementaire applicable ({reg.get('technical_standards_reference', 'normes en vigueur')}).</p>
            {internal_cite}
            {missing_data_alert or "<p style='color: #b91c1c; background: #fef2f2; padding: 8px; border-left: 4px solid #ef4444;'><strong>[A compléter :</strong> le moteur de génération de secours ne dispose pas encore d'un gabarit dédié pour cette section précise — merci de relire et compléter ce contenu manuellement, ou de relancer la génération (un nouvel essai peut aboutir sur un appel IA réel).]</p>"}
            {learnings_html}
            {web_cites_html}
            """
            score = 75.0
            notes = "Contenu généré par le moteur de secours générique — relecture et complément manuel recommandés."

        return {''',
    ),
])

if not (ok1 and ok2):
    print("\\nFAILED — see ABORT lines above.")
    sys.exit(1)

print("\\nALL BACKEND SECTION-KEY PATCHES APPLIED SUCCESSFULLY.")
