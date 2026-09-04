-- ==============================================================================
-- 00027_add_output_language_to_projects.sql
-- Ajoute la langue de rédaction du mémoire technique généré par IA (fr/en/ar).
--
-- Contexte (30/08) : l'utilisateur a demandé que la réponse à l'appel d'offres
-- puisse être produite en anglais, français ou arabe. Un sélecteur de langue
-- existait déjà visuellement dans le wizard (étape 5, "wizard.output_language")
-- mais n'était connecté à AUCUN appel API -- purement décoratif, sans aucun
-- effet. Cette migration ajoute la colonne qui permet enfin de persister ce
-- choix ; voir app/models/entities.py::Project.output_language,
-- app/models/schemas.py (ProjectCreate/ProjectUpdate/ProjectOut) et
-- app/services/llm_generator.py::build_btp_system_prompt() pour le câblage
-- complet (génération LLM + moteur de secours + export Word RTL).
--
-- Appliquée en direct sur le projet le 30/08 (Claude, via mcp__Supabase__apply_migration).
-- Ce fichier existe pour que le correctif soit suivi en contrôle de version et
-- reproductible sur tout environnement neuf, selon la convention du projet
-- (voir supabase/migrations/00019+).
-- ==============================================================================

ALTER TABLE public.projects
ADD COLUMN IF NOT EXISTS output_language TEXT NOT NULL DEFAULT 'fr';

ALTER TABLE public.projects
ADD CONSTRAINT projects_output_language_check
CHECK (output_language IN ('fr', 'en', 'ar'));

COMMENT ON COLUMN public.projects.output_language IS
'Langue de redaction du memoire technique genere par IA (fr/en/ar). Ajoutee le 30/08 -- corrige un selecteur UI (etape 5 du wizard) qui existait deja visuellement mais n''etait connecte a aucun appel API et ne persistait donc jamais le choix de langue.';
