-- Migration 00037 : planning hiérarchique (phases > tâches > sous-tâches) + couleur/lot.
--
-- Retour Charbel du 11/09 : « le Gantt n'est pas assez détaillé dans les tâches et
-- sous-tâches, trop macro ». La table ne connaissait qu'une liste plate : les 5 phases
-- du phasage déclaré (Installation, Gros œuvre, Second œuvre, Finitions, Réception),
-- sans aucun moyen de les décomposer.
--
-- parent_id : NULL pour une phase ; l'id de la phase (ou de la tâche) parente sinon.
--             ON DELETE CASCADE : supprimer une phase supprime son détail.
-- lot       : corps d'état / lot du marché (ex. "Lot 02 — Gros œuvre"). Sert à colorer
--             le planning par lot et à le relire avec le CCTP.
-- color     : couleur imposée pour cette ligne (#RRGGBB), prioritaire sur la palette.
--
-- Purement additive : les lignes existantes deviennent des phases (parent_id NULL),
-- aucun comportement antérieur ne change.

ALTER TABLE public.project_gantt_tasks
    ADD COLUMN IF NOT EXISTS parent_id UUID NULL REFERENCES public.project_gantt_tasks(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS lot TEXT NULL,
    ADD COLUMN IF NOT EXISTS color TEXT NULL;

CREATE INDEX IF NOT EXISTS idx_project_gantt_tasks_parent ON public.project_gantt_tasks(parent_id);
