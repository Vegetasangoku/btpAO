#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mega cahier des charges section 3 — "boucle d'apprentissage 3 portées" (this AO
only / similar AOs / all future dossiers) when the user edits AI-generated data.

Investigation this batch found the underlying detection + proposal machinery
was ALREADY correctly implemented: update_section_content (generate.py) already
runs learning_service.calculate_diff_significance on every section save and
returns a learning_opportunity + learning_proposal; tiptap-editor.tsx already
shows a banner and calls api.createLearning() to persist it. What was actually
missing was the SCOPE ITSELF: the banner had a single "Mémoriser" button with
no scope choice, createLearning always omitted project_id (TenantLearning rows
were always tenant-wide+section-type-scoped, functionally only "AOs similaires"
was reachable), and even if a project_id HAD been sent, nothing on the
retrieval side (aggregate_prefill_knowledge / generate_section_task's inline
learnings query) ever filtered by it -- so scoping would have been cosmetic.

Fixed end-to-end:
  1. schemas.py: CreateTenantLearningRequest gains project_id.
  2. generate.py: create_tenant_learning_endpoint resolves + verifies (tenant
     ownership) an optional project_id and persists it on TenantLearning.
  3. learning_service.py: get_active_tenant_learnings gains project_id/
     section_type filters (NULL on either side = applies broadly -- a "this AO
     only" learning has both set, "similar AOs" has section_type only, "all
     future dossiers" has neither); aggregate_prefill_knowledge's call site
     now passes them through (it already receives both as its own params).
  4. tasks.py: generate_section_task's inline, unscoped learnings query
     replaced with a call to the now-scope-aware learning_service method
     (removes ~9 lines of duplicated query logic, DRY, and actually respects
     scope for the real generation path, not just the prefill path).
  5. api.ts: createLearning payload gains project_id.
  6. tiptap-editor.tsx: the learning-proposal banner gains a 3-option scope
     selector (defaults to 'similar_aos', matching today's pre-existing
     behavior so nothing changes for a user who doesn't think about it);
     handleSaveLearning sends project_id/section_type per the selected scope.

(NOT touched, deliberately out of scope: the separate, older "Ajouter à la
mémoire" free-text box in workspace.tsx's floating helper, which writes to
tenants_settings.system_prompt_memory via /api/update-memory. That mechanism
is unrelated to TenantLearning / the diff-significance flow the mega-spec
describes, and investigation found system_prompt_memory is only ever read
back by the legacy apps/web/.../api/generate-offer/route.ts Next.js route --
NOT by the real apps/api generation pipeline. Logged as a separate discovered
gap in the project doc rather than folded into this fix, to keep this batch
scoped to what the spec actually asked for.)

Exact-match-count-of-1 verified live against the running files immediately
before writing this script. Aborts per-file with zero writes on any mismatch.
"""
import sys


def apply_patch(path, replacements):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for item in replacements:
        if len(item) == 4:
            label, old, new, expected_count = item
        else:
            label, old, new = item
            expected_count = 1
        count = content.count(old)
        if count != expected_count:
            print(f"ABORT [{path}] block '{label}': found {count} occurrences (expected {expected_count}). No changes written.")
            return False
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: {path} patched ({len(replacements)} block(s)).")
    return True


if len(sys.argv) != 2:
    print("Usage: patch_learning_loop_3scope.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
SCHEMAS_PY = f"{REPO_ROOT}/apps/api/app/models/schemas.py"
GENERATE_PY = f"{REPO_ROOT}/apps/api/app/api/generate.py"
LEARNING_SERVICE_PY = f"{REPO_ROOT}/apps/api/app/services/learning_service.py"
TASKS_PY = f"{REPO_ROOT}/apps/api/app/workers/tasks.py"
API_TS = f"{REPO_ROOT}/apps/web/src/lib/api.ts"
TIPTAP_TSX = f"{REPO_ROOT}/apps/web/src/components/editor/tiptap-editor.tsx"

results = []

# ─────────────────────────────────────────────────────────────────────────
# 1. schemas.py
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(SCHEMAS_PY, [
    (
        "CreateTenantLearningRequest gains project_id",
        '''class CreateTenantLearningRequest(BaseModel):
    title: str
    category: Optional[str] = "methodology"
    section_type: Optional[str] = None
    learned_content: str''',
        '''class CreateTenantLearningRequest(BaseModel):
    title: str
    category: Optional[str] = "methodology"
    section_type: Optional[str] = None
    project_id: Optional[str] = None
    learned_content: str''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 2. generate.py — create_tenant_learning_endpoint resolves + verifies project_id
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(GENERATE_PY, [
    (
        "resolve+verify optional project_id, persist on TenantLearning",
        '''    """
    Phase C: Persists an accepted learning adjustment consented by the user.
    """
    t_uuid = uuid.UUID(current_user.tenant_id)
    now = datetime.utcnow()
    learning = TenantLearning(
        id=uuid.uuid4(),
        tenant_id=t_uuid,
        title=payload.title,''',
        '''    """
    Phase C: Persists an accepted learning adjustment consented by the user.
    Scope ("boucle d'apprentissage 3 portees" du cahier des charges) is encoded
    via project_id / section_type: both set = "cette reponse AO uniquement",
    section_type only = "AOs similaires (meme type de section)", neither =
    "tous les futurs dossiers". See learning_service.get_active_tenant_learnings
    for the matching retrieval-side filter (NULL on either field = applies
    broadly, i.e. a narrower learning never fails to be found, it just also
    doesn't leak outside the scope the user actually picked).
    """
    t_uuid = uuid.UUID(current_user.tenant_id)

    p_uuid = None
    if payload.project_id:
        try:
            p_uuid = uuid.UUID(payload.project_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project_id")
        proj_check = await db.execute(
            select(Project.id).where(Project.id == p_uuid, Project.tenant_id == t_uuid)
        )
        if proj_check.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Projet introuvable ou acces non autorise pour la portee 'cette reponse AO uniquement'.",
            )

    now = datetime.utcnow()
    learning = TenantLearning(
        id=uuid.uuid4(),
        tenant_id=t_uuid,
        project_id=p_uuid,
        title=payload.title,''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 3. learning_service.py — scope-aware retrieval
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(LEARNING_SERVICE_PY, [
    (
        "import or_",
        "from sqlalchemy import select\n",
        "from sqlalchemy import or_, select\n",
    ),
    (
        "aggregate_prefill_knowledge: pass project_id/section_key through to learnings fetch",
        '''        # 3. Active Tenant Learnings
        learnings = await self.get_active_tenant_learnings(db=db, tenant_id=tenant_id, limit=5)''',
        '''        # 3. Active Tenant Learnings (scoped to this project + section per the
        # 3-portees learning loop -- a tenant-wide learning still applies, a
        # project/section-scoped one only applies where the user chose it to)
        learnings = await self.get_active_tenant_learnings(
            db=db, tenant_id=tenant_id, project_id=project_id, section_type=section_key, limit=5
        )''',
    ),
    (
        "get_active_tenant_learnings gains project_id/section_type scope filters",
        '''    async def get_active_tenant_learnings(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[TenantLearning]:
        """
        Retrieves active continuous learnings for LLM context injection or UI view.
        """
        stmt = (
            select(TenantLearning)
            .where(TenantLearning.tenant_id == tenant_id, TenantLearning.is_active == True)
        )
        if category:
            stmt = stmt.where(TenantLearning.category == category)

        stmt = stmt.order_by(TenantLearning.created_at.desc()).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())''',
        '''    async def get_active_tenant_learnings(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        category: Optional[str] = None,
        project_id: Optional[uuid.UUID] = None,
        section_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[TenantLearning]:
        """
        Retrieves active continuous learnings for LLM context injection or UI view.

        project_id / section_type implement the "boucle d'apprentissage 3
        portees" scoping: a learning with project_id=NULL (resp.
        section_type=NULL) was saved as "AOs similaires" / "tous les futurs
        dossiers" and applies regardless of the caller's project_id (resp.
        section_type); a learning with a concrete project_id (resp.
        section_type) was saved as "cette reponse AO uniquement" and only
        matches when the caller's value equals it. Passing project_id=None /
        section_type=None here (the default) preserves the original
        unrestricted behavior for any caller that doesn't scope its query.
        """
        stmt = (
            select(TenantLearning)
            .where(TenantLearning.tenant_id == tenant_id, TenantLearning.is_active == True)
        )
        if category:
            stmt = stmt.where(TenantLearning.category == category)
        if project_id:
            stmt = stmt.where(
                or_(TenantLearning.project_id.is_(None), TenantLearning.project_id == project_id)
            )
        if section_type:
            stmt = stmt.where(
                or_(TenantLearning.section_type.is_(None), TenantLearning.section_type == section_type)
            )

        stmt = stmt.order_by(TenantLearning.created_at.desc()).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 4. tasks.py — generate_section_task: use the scope-aware service method
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(TASKS_PY, [
    (
        "replace inline unscoped learnings query with scope-aware service call",
        '''                # 5. Fetch Active Tenant Learnings from Past AO debriefs
                from app.models.entities import TenantLearning
                learnings_stmt = (
                    select(TenantLearning)
                    .where(TenantLearning.tenant_id == tenant_uuid, TenantLearning.is_active == True)
                    .order_by(TenantLearning.created_at.desc())
                    .limit(5)
                )
                learnings_res = await db.execute(learnings_stmt)
                tenant_learnings_payload = [
                    {
                        "category": l.category,
                        "title": l.title,
                        "insight": l.learning_insight,
                        "directive": l.actionable_directive,
                    }
                    for l in learnings_res.scalars().all()
                ]''',
        '''                # 5. Fetch Active Tenant Learnings from Past AO debriefs, scoped to this
                # project + section per the "boucle d'apprentissage 3 portees" (this AO
                # only / AOs similaires / tous les futurs dossiers) -- a learning saved
                # with a narrower scope than the current generation never leaks outside it.
                from app.services.learning_service import learning_service
                active_learnings = await learning_service.get_active_tenant_learnings(
                    db=db,
                    tenant_id=tenant_uuid,
                    project_id=proj_uuid,
                    section_type=section_key,
                    limit=5,
                )
                tenant_learnings_payload = [
                    {
                        "category": l.category,
                        "title": l.title,
                        "insight": l.learning_insight,
                        "directive": l.actionable_directive,
                    }
                    for l in active_learnings
                ]''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 5. api.ts — createLearning payload gains project_id
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(API_TS, [
    (
        "createLearning payload type gains project_id",
        '''  createLearning: (payload: {
    title: string;
    category?: string;
    section_type?: string;
    learned_content: string;''',
        '''  createLearning: (payload: {
    title: string;
    category?: string;
    section_type?: string;
    project_id?: string;
    learned_content: string;''',
    ),
]))

# ─────────────────────────────────────────────────────────────────────────
# 6. tiptap-editor.tsx — 3-scope selector in the learning-proposal banner
# ─────────────────────────────────────────────────────────────────────────
results.append(apply_patch(TIPTAP_TSX, [
    (
        "add learningScope state",
        "  const [savingLearning, setSavingLearning] = useState(false);\n",
        "  const [savingLearning, setSavingLearning] = useState(false);\n"
        "  const [learningScope, setLearningScope] = useState<'this_ao' | 'similar_aos' | 'all_future'>('similar_aos');\n",
    ),
    (
        "handleSaveLearning sends scope-derived project_id/section_type",
        '''  const handleSaveLearning = async () => {
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
  };''',
        '''  const handleSaveLearning = async () => {
    if (!learningProposal) return;
    setSavingLearning(true);
    try {
      await api.createLearning({
        title: `Ajustement sur ${section.title}`,
        category: 'methodology',
        section_type: learningScope === 'all_future' ? undefined : learningProposal.section_type,
        project_id: learningScope === 'this_ao' ? projectId : undefined,
        learned_content: learningProposal.suggested_content,
        learning_insight: learningProposal.summary,
        source_outcome: 'manual_edit',
      });
      setLearningProposal(null);
      setLearningScope('similar_aos');
    } catch (err) {
      console.error('Learning save failed', err);
    } finally {
      setSavingLearning(false);
    }
  };''',
    ),
    (
        "banner gains 3-option scope selector",
        '''      {/* Learning Proposal Banner (Phase C — Apprentissage Continu) */}
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
      )}''',
        '''      {/* Learning Proposal Banner (Phase C — Apprentissage Continu, portée 3 niveaux) */}
      {learningProposal && (
        <div className="mx-4 mt-3 p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/30 space-y-2.5 text-xs">
          <div>
            <p className="font-semibold text-indigo-300">Modification significative détectée ({learningProposal.diff_percentage}%)</p>
            <p className="text-[11px] text-indigo-200/80 mt-0.5">{learningProposal.summary || 'Voulez-vous mémoriser cet ajustement ?'}</p>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] text-indigo-300/70 font-semibold uppercase tracking-wide mr-1">Portée :</span>
            {([
              { value: 'this_ao' as const, label: 'Cette réponse AO uniquement' },
              { value: 'similar_aos' as const, label: 'AOs similaires (même section)' },
              { value: 'all_future' as const, label: 'Tous les futurs dossiers' },
            ]).map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setLearningScope(opt.value)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-all ${
                  learningScope === opt.value
                    ? 'bg-indigo-600 border-indigo-500 text-white'
                    : 'bg-slate-900/60 border-slate-700 text-indigo-200/70 hover:text-indigo-100'
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
              className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-semibold disabled:opacity-50"
            >
              {savingLearning ? 'Enregistrement...' : 'Mémoriser cet apprentissage'}
            </button>
            <button
              onClick={() => { setLearningProposal(null); setLearningScope('similar_aos'); }}
              className="px-2 py-1.5 rounded-lg text-indigo-300 hover:text-white text-[11px]"
            >
              Ignorer
            </button>
          </div>
        </div>
      )}''',
    ),
]))

if not all(results):
    print("\nFAILED — see ABORT lines above. Each file's patch is atomic (all-or-nothing per file).")
    sys.exit(1)

print("\nALL LEARNING-LOOP 3-SCOPE PATCHES APPLIED SUCCESSFULLY.")
