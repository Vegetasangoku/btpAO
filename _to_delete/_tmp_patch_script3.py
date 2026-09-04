import sys

def patch(path, replacements, label):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    original = content
    for i, (old, new, expect) in enumerate(replacements):
        cnt = content.count(old)
        if cnt != expect:
            print(f"[{label}] FAIL at replacement #{i}: expected {expect} occurrences, found {cnt}")
            print("----- OLD (repr) -----")
            print(repr(old[:400]))
            sys.exit(1)
        content = content.replace(old, new)
    if content == original:
        print(f"[{label}] WARNING: no changes made")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[{label}] OK -- {len(replacements)} replacements applied")


# ========== 1. learning_service.py : new calculate_gantt_diff_significance ==========
ls_old = """        return is_significant, diff_pct, summary[:250]

    async def aggregate_prefill_knowledge("""
ls_new = '''        return is_significant, diff_pct, summary[:250]

    @staticmethod
    def calculate_gantt_diff_significance(
        baseline_phases: List[Dict[str, Any]],
        current_tasks: List[Dict[str, Any]],
        threshold_pct: float = 15.0,
    ) -> tuple[bool, float, str]:
        """
        Structural equivalent of calculate_diff_significance for the interactive
        Gantt (03/09, demande client -- la boucle d'apprentissage doit aussi couvrir
        les plannings, pas seulement le texte). Compare les project_gantt_tasks
        actuels au plan initial encore intact dans
        ProjectDecision.form_data['phasage_travaux'] -- les deux sont deliberement
        gardes separes depuis la migration 00026, ce qui permet cette comparaison sans
        snapshot dedie. Volontairement base sur des metriques globales (nombre de
        phases, duree totale) plutot qu'un appariement phase-par-phase par nom : un
        rapprochement par nom serait fragile face a un simple renommage ou
        reordonnancement, qui n'indiquent pas en soi un enseignement a capitaliser.
        """
        if not baseline_phases or not current_tasks:
            return False, 0.0, ""

        baseline_count = len(baseline_phases)
        current_count = len(current_tasks)
        baseline_days = sum(int(p.get("duree_semaines") or 4) for p in baseline_phases) * 7
        if baseline_days <= 0:
            return False, 0.0, ""

        starts = [t["start_date"] for t in current_tasks]
        ends = [t["end_date"] for t in current_tasks]
        current_days = max((max(ends) - min(starts)).days, 1)

        diff_pct = round(abs(current_days - baseline_days) / baseline_days * 100, 1)
        count_changed = baseline_count != current_count
        is_significant = count_changed or diff_pct >= threshold_pct

        if not is_significant:
            return False, diff_pct, ""

        direction = "allongee" if current_days > baseline_days else "raccourcie"
        parts = []
        if count_changed:
            parts.append(f"{current_count} phases au lieu de {baseline_count} initialement proposees")
        if diff_pct >= 1:
            parts.append(f"duree totale {direction} de {diff_pct}% ({current_days}j vs {baseline_days}j initialement)")
        summary = "Planning ajuste par rapport a la proposition initiale : " + ", ".join(parts) + "."

        return True, diff_pct, summary[:250]

    async def aggregate_prefill_knowledge('''

patch("apps/api/app/services/learning_service.py", [(ls_old, ls_new, 1)], "learning_service.py")


# ========== 2. schemas.py : new GanttLearningCheckResponse ==========
sc_old = """class UpdateSectionResponse(BaseModel):
    success: bool
    section: GeneratedSectionOut
    learning_opportunity: bool = False
    learning_proposal: Optional[LearningProposal] = None"""
sc_new = """class UpdateSectionResponse(BaseModel):
    success: bool
    section: GeneratedSectionOut
    learning_opportunity: bool = False
    learning_proposal: Optional[LearningProposal] = None


class GanttLearningCheckResponse(BaseModel):
    learning_opportunity: bool = False
    learning_proposal: Optional[LearningProposal] = None"""

patch("apps/api/app/models/schemas.py", [(sc_old, sc_new, 1)], "schemas.py (Gantt learning)")


# ========== 3. visuals.py : imports + new endpoint ==========
vi_import_schemas_old = """from app.models.schemas import (
    DiagramGenerationRequest,
    GanttGenerationRequest,
    GanttTaskCreate,
    GanttTaskOut,
    GanttTaskUpdate,
)"""
vi_import_schemas_new = """from app.models.schemas import (
    DiagramGenerationRequest,
    GanttGenerationRequest,
    GanttLearningCheckResponse,
    GanttTaskCreate,
    GanttTaskOut,
    GanttTaskUpdate,
    LearningProposal,
)"""

vi_import_services_old = """from app.services.diagram_service import diagram_service
from app.services.gantt_service import gantt_service"""
vi_import_services_new = """from app.services.diagram_service import diagram_service
from app.services.gantt_service import gantt_service
from app.services.learning_service import learning_service"""

vi_endpoint_old = """    task_dicts = [_row_to_task_dict(r) for r in rows]
    critical_ids = gantt_service.compute_critical_path(task_dicts)
    return [_row_to_out(r, critical_ids) for r in rows]


@router.post("/gantt-tasks/{project_id}", response_model=GanttTaskOut)
async def create_gantt_task("""
vi_endpoint_new = '''    task_dicts = [_row_to_task_dict(r) for r in rows]
    critical_ids = gantt_service.compute_critical_path(task_dicts)
    return [_row_to_out(r, critical_ids) for r in rows]


@router.get("/gantt-tasks/{project_id}/learning-check", response_model=GanttLearningCheckResponse)
async def check_gantt_learning_opportunity(
    project_id: str,
    current_user: CurrentTenantUser = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Boucle d'apprentissage par corrections (03/09, demande client), volet planning :
    compare le Gantt actuel (project_gantt_tasks, librement edite par le tenant) au
    plan initial encore intact dans ProjectDecision.form_data['phasage_travaux'] --
    voir learning_service.calculate_gantt_diff_significance pour la logique de
    comparaison. Additif et sans effet de bord : lecture seule, n'ecrit jamais rien --
    contrairement a POST /generate/learnings qui persiste l'ajustement une fois
    confirme par l'utilisateur (meme flux de confirmation que pour le texte, voir
    TiptapEditor.handleSaveLearning, reutilise tel quel cote frontend).
    """
    try:
        p_uuid = uuid.UUID(project_id)
        t_uuid = uuid.UUID(current_user.tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifiant de projet invalide.")

    project = await db.get(Project, p_uuid)
    if not project or str(project.tenant_id) != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Projet introuvable.")

    dec_stmt = select(ProjectDecision).where(
        ProjectDecision.project_id == p_uuid, ProjectDecision.tenant_id == t_uuid
    )
    dec_res = await db.execute(dec_stmt)
    decision = dec_res.scalar_one_or_none()
    baseline_phases = (decision.form_data.get("phasage_travaux") or []) if decision and decision.form_data else []

    rows = await _fetch_gantt_task_rows(db, current_user.tenant_id, project_id)
    current_tasks = [_row_to_task_dict(r) for r in rows]

    is_significant, diff_pct, summary = learning_service.calculate_gantt_diff_significance(
        baseline_phases=baseline_phases,
        current_tasks=current_tasks,
        threshold_pct=15.0,
    )

    if not is_significant:
        return GanttLearningCheckResponse(learning_opportunity=False)

    return GanttLearningCheckResponse(
        learning_opportunity=True,
        learning_proposal=LearningProposal(
            section_type="planning_phasage",
            summary=summary,
            suggested_content=summary,
            diff_percentage=diff_pct,
        ),
    )


@router.post("/gantt-tasks/{project_id}", response_model=GanttTaskOut)
async def create_gantt_task('''

patch("apps/api/app/api/visuals.py", [
    (vi_import_schemas_old, vi_import_schemas_new, 1),
    (vi_import_services_old, vi_import_services_new, 1),
    (vi_endpoint_old, vi_endpoint_new, 1),
], "visuals.py")


# ========== 4. api.ts : new checkGanttLearning ==========
api_old = """  listGanttTasks: (projectId: string) =>
    fetcher<GanttTask[]>(`/visuals/gantt-tasks/${projectId}`),
  createGanttTask: ("""
api_new = """  listGanttTasks: (projectId: string) =>
    fetcher<GanttTask[]>(`/visuals/gantt-tasks/${projectId}`),
  checkGanttLearning: (projectId: string) =>
    fetcher<{
      learning_opportunity: boolean;
      learning_proposal?: {
        section_type: string;
        summary: string;
        suggested_content: string;
        diff_percentage: number;
      } | null;
    }>(`/visuals/gantt-tasks/${projectId}/learning-check`),
  createGanttTask: ("""

patch("apps/web/src/lib/api.ts", [(api_old, api_new, 1)], "api.ts")


# ========== 5. interactive-gantt-chart.tsx : state + reload + handler + banner ==========
gc_state_old = """  const [nameEdits, setNameEdits] = useState<Record<string, string>>({});
  const containerRef = useRef<HTMLDivElement | null>(null);"""
gc_state_new = """  const [nameEdits, setNameEdits] = useState<Record<string, string>>({});
  const [learningProposal, setLearningProposal] = useState<{
    section_type: string;
    summary: string;
    suggested_content: string;
    diff_percentage: number;
  } | null>(null);
  const [savingLearning, setSavingLearning] = useState(false);
  const [learningScope, setLearningScope] = useState<'this_ao' | 'similar_aos' | 'all_future'>('similar_aos');
  const containerRef = useRef<HTMLDivElement | null>(null);"""

gc_reload_old = """  const reload = useCallback(async () => {
    try {
      const res = await api.listGanttTasks(projectId);
      setTasks(res);
      setLoadState('ready');
    } catch (err: any) {
      console.error('Failed to load Gantt tasks', err);
      setAuthExpired(err?.status === 401);
      setLoadState('error');
    }
  }, [projectId]);"""
gc_reload_new = """  const reload = useCallback(async () => {
    try {
      const res = await api.listGanttTasks(projectId);
      setTasks(res);
      setLoadState('ready');
      // Boucle d'apprentissage par corrections (03/09) : verifie apres chaque
      // mutation si l'ecart au plan initial merite d'etre memorise. Lecture seule et
      // non-bloquant -- un echec ici ne doit jamais casser l'affichage du Gantt.
      try {
        const check = await api.checkGanttLearning(projectId);
        if (check.learning_opportunity && check.learning_proposal) {
          setLearningProposal(check.learning_proposal);
        }
      } catch (checkErr) {
        console.error('Gantt learning check failed', checkErr);
      }
    } catch (err: any) {
      console.error('Failed to load Gantt tasks', err);
      setAuthExpired(err?.status === 401);
      setLoadState('error');
    }
  }, [projectId]);"""

gc_handler_old = """  const handleRenameCommit = async (task: GanttTask, newName: string) => {
    setNameEdits((prev) => {
      const next = { ...prev };
      delete next[task.id];
      return next;
    });
    const trimmed = newName.trim();
    if (!trimmed || trimmed === task.name) return;
    try {
      await api.updateGanttTask(projectId, task.id, { name: trimmed });
      await reload();
    } catch (err) {
      console.error('Failed to rename Gantt task', err);
    }
  };"""
gc_handler_new = """  const handleRenameCommit = async (task: GanttTask, newName: string) => {
    setNameEdits((prev) => {
      const next = { ...prev };
      delete next[task.id];
      return next;
    });
    const trimmed = newName.trim();
    if (!trimmed || trimmed === task.name) return;
    try {
      await api.updateGanttTask(projectId, task.id, { name: trimmed });
      await reload();
    } catch (err) {
      console.error('Failed to rename Gantt task', err);
    }
  };

  const handleSaveLearning = async () => {
    if (!learningProposal) return;
    setSavingLearning(true);
    try {
      await api.createLearning({
        title: `Ajustement planning — ${projectTitle}`,
        category: 'planning',
        section_type: learningScope === 'all_future' ? undefined : learningProposal.section_type,
        project_id: learningScope === 'this_ao' ? projectId : undefined,
        learned_content: learningProposal.suggested_content,
        learning_insight: learningProposal.summary,
        source_outcome: 'manual_edit',
      });
      setLearningProposal(null);
      setLearningScope('similar_aos');
    } catch (err) {
      console.error('Gantt learning save failed', err);
    } finally {
      setSavingLearning(false);
    }
  };"""

gc_banner_old = """          </button>
        </div>
      </div>

      {exportInfo && ("""
gc_banner_new = """          </button>
        </div>
      </div>

      {learningProposal && (
        <div className="p-3.5 rounded-xl bg-hl/8 border border-hl/20 space-y-2.5 text-xs">
          <div>
            <p className="font-semibold text-hl">{t('editor.tiptap.learning_title', { percent: learningProposal.diff_percentage })}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">{learningProposal.summary || t('editor.tiptap.learning_default_summary')}</p>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] text-muted-foreground font-semibold uppercase tracking-wide mr-1">{t('editor.tiptap.learning_scope_label')}</span>
            {([
              { value: 'this_ao' as const, label: t('editor.tiptap.scope_this_ao') },
              { value: 'similar_aos' as const, label: t('editor.tiptap.scope_similar_aos') },
              { value: 'all_future' as const, label: t('editor.tiptap.scope_all_future') },
            ]).map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setLearningScope(opt.value)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-all cursor-pointer ${
                  learningScope === opt.value
                    ? 'bg-hl border-hl text-white'
                    : 'bg-card border-line text-foreground hover:text-hl'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handleSaveLearning}
              disabled={savingLearning}
              className="px-3 py-1.5 rounded-lg bg-hl hover:bg-hl-strong text-hl-contrast text-[11px] font-semibold disabled:opacity-50 cursor-pointer"
            >
              {savingLearning ? t('editor.tiptap.saving') : t('editor.tiptap.btn_memorize')}
            </button>
            <button
              onClick={() => { setLearningProposal(null); setLearningScope('similar_aos'); }}
              className="px-2 py-1.5 rounded-lg text-muted-foreground hover:text-foreground text-[11px] cursor-pointer"
            >
              {t('editor.tiptap.btn_ignore')}
            </button>
          </div>
        </div>
      )}

      {exportInfo && ("""

patch("apps/web/src/components/visuals/interactive-gantt-chart.tsx", [
    (gc_state_old, gc_state_new, 1),
    (gc_reload_old, gc_reload_new, 1),
    (gc_handler_old, gc_handler_new, 1),
    (gc_banner_old, gc_banner_new, 1),
], "interactive-gantt-chart.tsx")

print("ALL PATCHES APPLIED SUCCESSFULLY (script3)")
