#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 11 (cahier des charges majeur) -- Interactive Gantt frontend text edits.
(The vendored frappe-gantt files + the new InteractiveGanttChart component are new
files, transferred directly rather than patched.)
Applies 4 exact-match patches:
  1. apps/web/src/lib/types.ts   -- new GanttTask interface
  2. apps/web/src/lib/api.ts     -- new listGanttTasks/createGanttTask/updateGanttTask/
                                     deleteGanttTask + extended generateGantt return type
  3. apps/web/src/app/projects/[id]/editor/page.tsx  -- swap GanttPreview -> InteractiveGanttChart
  4. apps/web/src/app/projects/[id]/visuals/page.tsx -- same swap
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
                  f"No changes written to this file. Anchor snippet: {old[:120]!r}")
            sys.exit(1)
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: patched {relpath}")


# ─── 1. types.ts ─────────────────────────────────────────────────────────────
patch_file("apps/web/src/lib/types.ts", [
    (
        "export interface SuggestedTemplate {\n"
        "  has_template: boolean;\n"
        "  source_type?: 'export_template' | 'recent_dossier' | 'reference_document' | null;\n"
        "  source?: string;\n"
        "  name?: string | null;\n"
        "  title?: string | null;\n"
        "  description?: string | null;\n"
        "  reason?: string | null;\n"
        "  id?: string | null;\n"
        "  created_at?: string | null;\n"
        "}\n",
        "export interface SuggestedTemplate {\n"
        "  has_template: boolean;\n"
        "  source_type?: 'export_template' | 'recent_dossier' | 'reference_document' | null;\n"
        "  source?: string;\n"
        "  name?: string | null;\n"
        "  title?: string | null;\n"
        "  description?: string | null;\n"
        "  reason?: string | null;\n"
        "  id?: string | null;\n"
        "  created_at?: string | null;\n"
        "}\n"
        "\n"
        "// Interactive Gantt task (Batch 11, cahier des charges majeur)\n"
        "export interface GanttTask {\n"
        "  id: string;\n"
        "  project_id: string;\n"
        "  name: string;\n"
        "  start_date: string;\n"
        "  end_date: string;\n"
        "  progress: number;\n"
        "  sequence: number;\n"
        "  is_milestone: boolean;\n"
        "  milestone_label: string | null;\n"
        "  depends_on: string[];\n"
        "  is_critical: boolean;\n"
        "}\n",
        1,
    ),
])

# ─── 2. api.ts ───────────────────────────────────────────────────────────────
patch_file("apps/web/src/lib/api.ts", [
    (
        "  CustomLLMProvider,\n"
        "  TeamMember,\n"
        "  TeamInvitation,\n"
        "  SuggestedTemplate,\n"
        "} from './types';",
        "  CustomLLMProvider,\n"
        "  TeamMember,\n"
        "  TeamInvitation,\n"
        "  SuggestedTemplate,\n"
        "  GanttTask,\n"
        "} from './types';",
        1,
    ),
    (
        "  // Visuals (Gantt & Organigramme)\n"
        "  generateGantt: (projectId: string, projectTitle: string, phases: any[]) =>\n"
        "    fetcher<{ s3_key: string; url: string; total_weeks: number; completion_date: string }>('/visuals/gantt', {\n"
        "      method: 'POST',\n"
        "      body: JSON.stringify({ project_id: projectId, project_title: projectTitle, phases }),\n"
        "    }),",
        "  // Visuals (Gantt & Organigramme)\n"
        "  generateGantt: (projectId: string, projectTitle: string, phases: any[]) =>\n"
        "    fetcher<{ s3_key: string; url: string; total_weeks: number; completion_date: string; critical_task_count?: number }>('/visuals/gantt', {\n"
        "      method: 'POST',\n"
        "      body: JSON.stringify({ project_id: projectId, project_title: projectTitle, phases }),\n"
        "    }),\n"
        "\n"
        "  // Interactive Gantt tasks (Batch 11, cahier des charges majeur)\n"
        "  listGanttTasks: (projectId: string) =>\n"
        "    fetcher<GanttTask[]>(`/visuals/gantt-tasks/${projectId}`),\n"
        "  createGanttTask: (\n"
        "    projectId: string,\n"
        "    payload: {\n"
        "      name: string;\n"
        "      start_date: string;\n"
        "      end_date: string;\n"
        "      progress?: number;\n"
        "      is_milestone?: boolean;\n"
        "      milestone_label?: string | null;\n"
        "      depends_on?: string[];\n"
        "    }\n"
        "  ) =>\n"
        "    fetcher<GanttTask>(`/visuals/gantt-tasks/${projectId}`, {\n"
        "      method: 'POST',\n"
        "      body: JSON.stringify(payload),\n"
        "    }),\n"
        "  updateGanttTask: (\n"
        "    projectId: string,\n"
        "    taskId: string,\n"
        "    payload: Partial<{\n"
        "      name: string;\n"
        "      start_date: string;\n"
        "      end_date: string;\n"
        "      progress: number;\n"
        "      is_milestone: boolean;\n"
        "      milestone_label: string | null;\n"
        "      depends_on: string[];\n"
        "    }>\n"
        "  ) =>\n"
        "    fetcher<GanttTask>(`/visuals/gantt-tasks/${projectId}/${taskId}`, {\n"
        "      method: 'PATCH',\n"
        "      body: JSON.stringify(payload),\n"
        "    }),\n"
        "  deleteGanttTask: (projectId: string, taskId: string) =>\n"
        "    fetcher<{ success: boolean }>(`/visuals/gantt-tasks/${projectId}/${taskId}`, {\n"
        "      method: 'DELETE',\n"
        "    }),",
        1,
    ),
])

# ─── 3. editor/page.tsx ───────────────────────────────────────────────────────
patch_file("apps/web/src/app/projects/[id]/editor/page.tsx", [
    (
        "import { GanttPreview } from '@/components/visuals/gantt-preview';",
        "import { InteractiveGanttChart } from '@/components/visuals/interactive-gantt-chart';",
        1,
    ),
    (
        "        ) : isGanttSection ? (\n"
        "          <GanttPreview projectId={projectId} projectTitle={project?.title || 'Projet BTP'} />\n"
        "        ) : (",
        "        ) : isGanttSection ? (\n"
        "          <InteractiveGanttChart projectId={projectId} projectTitle={project?.title || 'Projet BTP'} />\n"
        "        ) : (",
        1,
    ),
])

# ─── 4. visuals/page.tsx ──────────────────────────────────────────────────────
patch_file("apps/web/src/app/projects/[id]/visuals/page.tsx", [
    (
        "import { GanttPreview } from '@/components/visuals/gantt-preview';",
        "import { InteractiveGanttChart } from '@/components/visuals/interactive-gantt-chart';",
        1,
    ),
    (
        "        <GanttPreview projectId={projectId} />",
        "        <InteractiveGanttChart projectId={projectId} />",
        1,
    ),
])

print("All batch-11 frontend patches applied.")
