-- Migration 00036: Interactive organigramme (site supervision org chart) nodes.
--
-- Mirrors migration 00026 (project_gantt_tasks) exactly, for the same reason: the
-- organigramme PNG (diagram_service.generate_organigramme_png) was, until this batch,
-- entirely stateless -- the frontend always called POST /visuals/organigramme with an
-- EMPTY nodes list, so the rendered chart NEVER reflected the client's real
-- equipe_cadres (entered in the Go/No-Go "Conducteur de Travaux" form) and instead
-- always showed the same 4 hardcoded fictional names. This table is the new source of
-- truth for the interactive, editable organigramme (03/09, demande client : boucle
-- d'apprentissage par corrections "y compris pour les schemas / tableaux etc" +
-- visibilite des echecs de sites de reference).
--
-- Deliberately separate from decision_form.equipe_cadres (edited in the Go/No-Go
-- form), exactly like project_gantt_tasks is kept separate from phasage_travaux: that
-- JSON field keeps feeding the AI text-generation fallback and the export narrative
-- exactly as before -- untouched by this migration. On first read, if a project has no
-- rows here yet, the API lazily seeds them from decision_form.equipe_cadres (same
-- names/roles/experience/presence, in the same order) so existing projects get a
-- sensible starting point instead of an empty chart. After that one-time seed, this
-- table alone drives the organigramme -- the two lists can drift apart if a user edits
-- both after the fact; this is the same known, documented limitation as the Gantt
-- (see claude/etat-technique-btpao.md).
--
-- `sequence` encodes the organigramme's hierarchy exactly like diagram_service expects
-- it today: the node at sequence 0 is the lead (rendered as the large central
-- "Conducteur Principal" box), every following node is a sub-cadre (rendered as one of
-- the boxes on the row below) -- same convention as cadres[0] / cadres[1:] in
-- diagram_service.generate_organigramme_png.

CREATE TABLE IF NOT EXISTS public.project_organigramme_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    nom TEXT NOT NULL,
    role TEXT NOT NULL,
    experience_ans INTEGER NOT NULL DEFAULT 10,
    presence_hebdo_pct INTEGER NOT NULL DEFAULT 100 CHECK (presence_hebdo_pct >= 0 AND presence_hebdo_pct <= 100),
    qualif TEXT,
    sequence INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_organigramme_nodes_project ON public.project_organigramme_nodes(project_id);
CREATE INDEX IF NOT EXISTS idx_project_organigramme_nodes_tenant ON public.project_organigramme_nodes(tenant_id);

ALTER TABLE public.project_organigramme_nodes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_project_organigramme_nodes ON public.project_organigramme_nodes;
DROP POLICY IF EXISTS project_organigramme_nodes_superadmin_all ON public.project_organigramme_nodes;

CREATE POLICY tenant_isolation_project_organigramme_nodes ON public.project_organigramme_nodes
    FOR ALL
    USING (tenant_id = current_tenant_id() OR auth.role() = 'service_role')
    WITH CHECK (tenant_id = current_tenant_id() OR auth.role() = 'service_role');

CREATE POLICY project_organigramme_nodes_superadmin_all ON public.project_organigramme_nodes
    FOR ALL
    USING (is_superadmin())
    WITH CHECK (is_superadmin());
