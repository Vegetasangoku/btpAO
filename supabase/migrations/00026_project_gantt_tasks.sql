-- Migration 00026: Interactive Gantt tasks (Batch 11 -- cahier des charges majeur)
--
-- Structured per-project planning tasks, replacing the previously stateless Gantt PNG
-- generation (which always used a hardcoded 5-phase default because the frontend never
-- actually forwarded the real per-project phase data). This table is the new source of
-- truth for the interactive Gantt chart (both the on-screen interactive view and the
-- exported HD PNG embedded in the Word memo).
--
-- Deliberately separate from decision_form.phasage_travaux (edited in the Go/No-Go
-- form): that JSON field keeps feeding the AI text-generation fallback and the export
-- narrative exactly as before -- untouched by this migration. On first read, if a
-- project has no rows here yet, the API lazily seeds them from
-- decision_form.phasage_travaux (same phase names/durations/milestones, converted into
-- a sequential finish-to-start chain) so existing projects get a sensible starting
-- point instead of an empty chart. After that one-time seed, this table alone drives
-- the Gantt -- the two lists can drift apart if a user edits both after the fact; this
-- is a known, documented limitation (see claude/etat-technique-btpao.md).

CREATE TABLE IF NOT EXISTS public.project_gantt_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    sequence INTEGER NOT NULL DEFAULT 0,
    is_milestone BOOLEAN NOT NULL DEFAULT false,
    milestone_label TEXT,
    depends_on UUID[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_gantt_tasks_project ON public.project_gantt_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_project_gantt_tasks_tenant ON public.project_gantt_tasks(tenant_id);

ALTER TABLE public.project_gantt_tasks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_project_gantt_tasks ON public.project_gantt_tasks;
DROP POLICY IF EXISTS project_gantt_tasks_superadmin_all ON public.project_gantt_tasks;

CREATE POLICY tenant_isolation_project_gantt_tasks ON public.project_gantt_tasks
    FOR ALL
    USING (tenant_id = current_tenant_id() OR auth.role() = 'service_role')
    WITH CHECK (tenant_id = current_tenant_id() OR auth.role() = 'service_role');

CREATE POLICY project_gantt_tasks_superadmin_all ON public.project_gantt_tasks
    FOR ALL
    USING (is_superadmin())
    WITH CHECK (is_superadmin());
