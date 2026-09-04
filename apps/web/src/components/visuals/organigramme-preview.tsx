'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Users, RefreshCw, AlertTriangle, Plus, Trash2 } from 'lucide-react';
import { api, fetchAuthenticatedBlobUrl } from '@/lib/api';
import { OrganigrammeNode } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

interface OrganigrammePreviewProps {
  projectId: string;
  projectTitle?: string;
  initialImageUrl?: string;
}

export function OrganigrammePreview({ projectId, projectTitle = 'Projet BTP', initialImageUrl }: OrganigrammePreviewProps) {
  const { t } = useTranslation();
  const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');

  // --- Image preview state (existing PNG panel, unchanged) ---
  const [rawPath, setRawPath] = useState<string>(
    // Pas de tenant hardcodé ici : "self/" est résolu côté backend depuis le token
    // d'auth réel de l'utilisateur courant (voir get_visual_file).
    initialImageUrl || `${apiBase}/api/visuals/file/self/visuals/${projectId}/organigramme_chantier.png`
  );
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'missing' | 'error'>('loading');
  const [authExpired, setAuthExpired] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const objectUrlRef = useRef<string | null>(null);

  // --- Editable team list state (03/09, boucle d'apprentissage "schemas/tableaux") ---
  const [nodes, setNodes] = useState<OrganigrammeNode[]>([]);
  const [nodesLoadState, setNodesLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [fieldEdits, setFieldEdits] = useState<Record<string, Record<string, string>>>({});
  // Retour d'erreur par champ (cle `${nodeId}:${field}`) et par ligne. Avant le
  // correctif du 04/09, un echec de sauvegarde n'etait ecrit QUE dans la console :
  // l'utilisateur voyait sa saisie disparaitre sans la moindre explication.
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [savingFields, setSavingFields] = useState<Record<string, boolean>>({});
  const [rowError, setRowError] = useState<string | null>(null);
  const [learningProposal, setLearningProposal] = useState<{
    section_type: string;
    summary: string;
    suggested_content: string;
    diff_percentage: number;
  } | null>(null);
  const [savingLearning, setSavingLearning] = useState(false);
  const [learningScope, setLearningScope] = useState<'this_ao' | 'similar_aos' | 'all_future'>('similar_aos');

  async function loadImage(path: string) {
    setLoadState('loading');
    setAuthExpired(false);
    try {
      const url = await fetchAuthenticatedBlobUrl(path);
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = url;
      setBlobUrl(url);
      setLoadState('ready');
    } catch (err: any) {
      if (err?.status === 404 || String(err?.message || '').includes('404')) {
        setLoadState('missing');
      } else {
        console.error('Failed to load organigramme image', err);
        setAuthExpired(err?.status === 401);
        setLoadState('error');
      }
    }
  }

  useEffect(() => {
    loadImage(rawPath);
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawPath]);

  /** Verifie l'ecart a l'equipe initiale. Extrait de reloadNodes le 04/09 pour pouvoir
   *  aussi le declencher depuis le chemin "erreur reseau mais ecriture reellement
   *  passee" -- sinon une correction bien enregistree ne proposait jamais son
   *  apprentissage. Lecture seule et non bloquant : un echec ici ne casse rien. */
  const runLearningCheck = useCallback(async () => {
    try {
      const check = await api.checkOrganigrammeLearning(projectId);
      if (check.learning_opportunity && check.learning_proposal) {
        setLearningProposal(check.learning_proposal);
      }
    } catch (checkErr) {
      console.error('Organigramme learning check failed', checkErr);
    }
  }, [projectId]);

  const reloadNodes = useCallback(async () => {
    try {
      const res = await api.listOrganigrammeNodes(projectId);
      setNodes(res);
      setNodesLoadState('ready');
      // Boucle d'apprentissage par corrections (03/09) : verifie apres chaque mutation
      // si l'ecart a l'equipe initiale (equipe_cadres) merite d'etre memorise -- meme
      // pattern que InteractiveGanttChart.reload().
      await runLearningCheck();
    } catch (err) {
      console.error('Failed to load organigramme nodes', err);
      setNodesLoadState('error');
    }
  }, [projectId, runLearningCheck]);

  // Chargement initial : PAS de learning-check ici (mirroir volontaire de
  // InteractiveGanttChart -- le check ne doit se declencher qu'apres une vraie
  // mutation de l'utilisateur, jamais sur un simple refresh de page).
  useEffect(() => {
    let cancelled = false;
    setNodesLoadState('loading');
    api.listOrganigrammeNodes(projectId)
      .then((res) => {
        if (cancelled) return;
        setNodes(res);
        setNodesLoadState('ready');
      })
      .catch((err) => {
        console.error('Failed to load organigramme nodes', err);
        if (!cancelled) setNodesLoadState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  function fieldValue(node: OrganigrammeNode, field: 'nom' | 'role' | 'experience_ans' | 'presence_hebdo_pct'): string {
    const edited = fieldEdits[node.id]?.[field];
    if (edited !== undefined) return edited;
    const v = node[field];
    return v === null || v === undefined ? '' : String(v);
  }

  function setFieldEdit(nodeId: string, field: string, value: string) {
    setFieldEdits((prev) => ({ ...prev, [nodeId]: { ...prev[nodeId], [field]: value } }));
  }

  /**
   * Un PATCH de champ ecrit une valeur ABSOLUE (jamais un increment), il est donc
   * idempotent : le rejouer une fois ne peut pas doubler l'effet. C'est ce qui rend
   * ce retry sur : le serveur de developpement redemarre regulierement en pleine
   * requete (editions de fichiers concurrentes) et renvoie alors un 503 ou coupe la
   * connexion. A ne SURTOUT pas faire sur la creation (POST), elle n'est pas
   * idempotente -- c'est exactement comme ca que des doublons ont ete crees en test.
   */
  async function patchNodeWithRetry(nodeId: string, patch: Record<string, unknown>) {
    try {
      return await api.updateOrganigrammeNode(projectId, nodeId, patch as any);
    } catch (firstErr) {
      await new Promise((r) => setTimeout(r, 800));
      return await api.updateOrganigrammeNode(projectId, nodeId, patch as any);
    }
  }

  async function commitField(node: OrganigrammeNode, field: 'nom' | 'role' | 'experience_ans' | 'presence_hebdo_pct') {
    const raw = fieldEdits[node.id]?.[field];
    if (raw === undefined) return;
    const trimmed = raw.trim();
    const editKey = `${node.id}:${field}`;
    const clearEdit = () =>
      setFieldEdits((prev) => {
        if (!prev[node.id] || !(field in prev[node.id])) return prev;
        const next = { ...prev };
        const inner = { ...next[node.id] };
        delete inner[field];
        next[node.id] = inner;
        return next;
      });

    let value: string | number;
    if (field === 'experience_ans' || field === 'presence_hebdo_pct') {
      const n = parseInt(trimmed, 10);
      if (Number.isNaN(n)) {
        clearEdit();
        return;
      }
      value = field === 'presence_hebdo_pct' ? Math.min(100, Math.max(0, n)) : Math.max(0, n);
    } else {
      if (!trimmed) {
        clearEdit();
        return;
      }
      value = trimmed;
    }
    if (value === node[field]) {
      clearEdit();
      return;
    }

    // Affichage optimiste. Avant le correctif du 04/09, l'edition locale etait effacee
    // AVANT l'appel reseau : le champ revenait donc visuellement a l'ancienne valeur
    // pendant toute la duree de la requete (2 s et bien plus quand la base est lente),
    // ce qui donnait l'impression que la saisie avait ete refusee.
    setNodes((prev) => prev.map((nd) => (nd.id === node.id ? { ...nd, [field]: value } : nd)));
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next[editKey];
      return next;
    });
    setSavingFields((prev) => ({ ...prev, [editKey]: true }));

    try {
      await patchNodeWithRetry(node.id, { [field]: value });
      clearEdit();
      await reloadNodes();
    } catch (err) {
      console.error('Failed to update organigramme node', err);
      // L'ecriture a PEUT-ETRE abouti malgre l'erreur -- cas reel observe le 04/09 :
      // PATCH repondu 503 alors que la ligne etait deja commitee en base. On va donc
      // TOUJOURS redemander l'etat au serveur avant de conclure (meme discipline que
      // InteractiveGanttChart sur ses drags), et on n'affiche une erreur que si le
      // serveur n'a effectivement pas la valeur.
      try {
        const fresh = await api.listOrganigrammeNodes(projectId);
        setNodes(fresh);
        const saved = fresh.find((n) => n.id === node.id);
        if (saved && String((saved as any)[field]) === String(value)) {
          // L'ecriture est bien passee malgre l'erreur reseau : on traite ce cas comme
          // un succes complet, apprentissage compris.
          clearEdit();
          await runLearningCheck();
          return;
        }
      } catch (resyncErr) {
        console.error('Failed to resync organigramme nodes', resyncErr);
      }
      setFieldErrors((prev) => ({ ...prev, [editKey]: t('visuals.organigramme.save_failed') }));
    } finally {
      setSavingFields((prev) => {
        const next = { ...prev };
        delete next[editKey];
        return next;
      });
    }
  }

  const handleAddNode = async () => {
    setRowError(null);
    try {
      // Pas de retry ici : un POST n'est pas idempotent, le rejouer creerait un doublon.
      await api.createOrganigrammeNode(projectId, {
        nom: t('visuals.organigramme.new_node_default_name'),
        role: t('visuals.organigramme.new_node_default_role'),
        experience_ans: 10,
        presence_hebdo_pct: 100,
      });
      await reloadNodes();
    } catch (err) {
      console.error('Failed to add organigramme node', err);
      // La ligne a peut-etre ete creee malgre l'erreur : on resynchronise pour la faire
      // apparaitre si c'est le cas, plutot que de laisser l'utilisateur recliquer et
      // fabriquer un doublon (ce qui est arrive en test le 04/09).
      try {
        const fresh = await api.listOrganigrammeNodes(projectId);
        setNodes(fresh);
        if (fresh.length > nodes.length) return;
      } catch (resyncErr) {
        console.error('Failed to resync organigramme nodes', resyncErr);
      }
      setRowError(t('visuals.organigramme.action_failed'));
    }
  };

  const handleDeleteNode = async (nodeId: string) => {
    setRowError(null);
    try {
      await api.deleteOrganigrammeNode(projectId, nodeId);
      await reloadNodes();
    } catch (err) {
      console.error('Failed to delete organigramme node', err);
      try {
        const fresh = await api.listOrganigrammeNodes(projectId);
        setNodes(fresh);
        if (!fresh.some((n) => n.id === nodeId)) return;
      } catch (resyncErr) {
        console.error('Failed to resync organigramme nodes', resyncErr);
      }
      setRowError(t('visuals.organigramme.action_failed'));
    }
  };

  const handleSaveLearning = async () => {
    if (!learningProposal) return;
    setSavingLearning(true);
    try {
      await api.createLearning({
        title: `Ajustement organigramme — ${projectTitle}`,
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
      console.error('Organigramme learning save failed', err);
    } finally {
      setSavingLearning(false);
    }
  };

  const handleRegenerate = async () => {
    setIsGenerating(true);
    try {
      // nodes=[] : le backend prefere desormais les project_organigramme_nodes
      // persistes s'ils existent (voir generate_project_organigramme) -- ce payload
      // ne sert plus que de repli pour un projet sans aucun noeud persiste.
      const res = await api.generateOrganigramme(projectId, projectTitle, []);
      setRawPath(`${apiBase}/api/visuals/file/${res.s3_key}?t=${Date.now()}`);
    } catch (err) {
      console.error('Failed to generate organigramme', err);
      setLoadState('error');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="card-modern p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-200/60 dark:border-zinc-800/40">
        <div>
          <h3 className="text-[13px] font-bold text-foreground flex items-center gap-2 font-heading">
            <Users className="w-4 h-4 text-hl" />
            {t('visuals.organigramme.title')}
          </h3>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            {t('visuals.organigramme.subtitle')}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleAddNode}
            className="btn-secondary !py-1.5 !px-2.5 !text-[11px] cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            {t('visuals.organigramme.add_node_btn')}
          </button>
          <button
            onClick={handleRegenerate}
            disabled={isGenerating}
            className="btn-primary !py-1.5 !px-3 !text-[11px]"
          >
            <RefreshCw className={`w-3 h-3 ${isGenerating ? 'animate-spin' : ''}`} />
            <span>{isGenerating ? t('visuals.organigramme.generating') : t('visuals.organigramme.regenerate_btn')}</span>
          </button>
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

      {/* Editable supervisory team list (03/09) */}
      <div className="space-y-1.5">
        <div className="text-[10px] font-mono font-bold text-muted-foreground uppercase tracking-wider">
          {t('visuals.organigramme.nodes_count', { count: nodes.length })}
        </div>
        {rowError && (
          <p className="text-[10px] text-danger flex items-center gap-1">
            <AlertTriangle className="w-3 h-3 shrink-0" /> {rowError}
          </p>
        )}
        {nodesLoadState === 'loading' ? (
          <div className="flex items-center gap-2 text-muted-foreground text-xs py-3">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> {t('visuals.organigramme.loading_nodes')}
          </div>
        ) : nodesLoadState === 'error' ? (
          <div className="flex items-center gap-2 text-danger text-xs py-3">
            <AlertTriangle className="w-3.5 h-3.5" /> {t('visuals.organigramme.error_title_nodes')}
          </div>
        ) : nodes.length === 0 ? (
          <div className="text-xs text-muted-foreground py-3 text-center">
            <p>{t('visuals.organigramme.empty_nodes_title')}</p>
            <button onClick={handleAddNode} className="text-hl font-semibold underline cursor-pointer mt-1">
              {t('visuals.organigramme.empty_nodes_add_btn')}
            </button>
          </div>
        ) : (
          <div className="max-h-56 overflow-y-auto space-y-1.5 pr-1">
            {nodes.map((node, idx) => {
              const rowFieldErrors = (['nom', 'role', 'experience_ans', 'presence_hebdo_pct'] as const)
                .map((f) => fieldErrors[`${node.id}:${f}`])
                .filter(Boolean);
              const rowSaving = (['nom', 'role', 'experience_ans', 'presence_hebdo_pct'] as const)
                .some((f) => savingFields[`${node.id}:${f}`]);
              return (
              <div key={node.id} className={`flex flex-wrap items-center gap-1.5 px-2.5 py-2 rounded-lg text-xs border bg-card ${rowFieldErrors.length ? 'border-danger/60' : 'border-line'}`}>
                <span className="text-[9px] font-mono font-bold text-hl shrink-0 w-9 uppercase tracking-wide">
                  {idx === 0 ? t('visuals.organigramme.lead_badge') : `#${idx + 1}`}
                </span>
                <input
                  value={fieldValue(node, 'nom')}
                  onChange={(e) => setFieldEdit(node.id, 'nom', e.target.value)}
                  onBlur={() => commitField(node, 'nom')}
                  placeholder={t('visuals.organigramme.nom_placeholder')}
                  className="flex-1 min-w-[110px] bg-transparent text-slate-800 dark:text-zinc-200 font-semibold focus:outline-none focus:ring-1 focus:ring-hl rounded px-1"
                />
                <input
                  value={fieldValue(node, 'role')}
                  onChange={(e) => setFieldEdit(node.id, 'role', e.target.value)}
                  onBlur={() => commitField(node, 'role')}
                  placeholder={t('visuals.organigramme.role_placeholder')}
                  className="flex-[1.4] min-w-[140px] bg-transparent text-muted-foreground focus:outline-none focus:ring-1 focus:ring-hl rounded px-1"
                />
                <input
                  type="number"
                  min={0}
                  max={60}
                  value={fieldValue(node, 'experience_ans')}
                  onChange={(e) => setFieldEdit(node.id, 'experience_ans', e.target.value)}
                  onBlur={() => commitField(node, 'experience_ans')}
                  title={t('visuals.organigramme.experience_title')}
                  className="w-12 bg-transparent text-muted-foreground text-right focus:outline-none focus:ring-1 focus:ring-hl rounded px-1 tabular-nums"
                />
                <span className="text-[10px] text-muted-foreground shrink-0">{t('visuals.organigramme.experience_suffix')}</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={fieldValue(node, 'presence_hebdo_pct')}
                  onChange={(e) => setFieldEdit(node.id, 'presence_hebdo_pct', e.target.value)}
                  onBlur={() => commitField(node, 'presence_hebdo_pct')}
                  title={t('visuals.organigramme.presence_title')}
                  className="w-12 bg-transparent text-muted-foreground text-right focus:outline-none focus:ring-1 focus:ring-hl rounded px-1 tabular-nums"
                />
                <span className="text-[10px] text-muted-foreground shrink-0">%</span>
                {rowSaving && <RefreshCw className="w-3 h-3 animate-spin text-hl shrink-0" />}
                <button
                  onClick={() => handleDeleteNode(node.id)}
                  className="text-slate-300 dark:text-zinc-600 hover:text-danger dark:hover:text-danger shrink-0 cursor-pointer p-0.5"
                  title={t('visuals.organigramme.delete_node_title')}
                >
                  <Trash2 className="w-3 h-3" />
                </button>
                {rowFieldErrors.length > 0 && (
                  <p className="w-full text-[10px] text-danger flex items-center gap-1 mt-0.5">
                    <AlertTriangle className="w-3 h-3 shrink-0" /> {rowFieldErrors[0]}
                  </p>
                )}
              </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Image Preview */}
      <div className="relative rounded-xl border border-slate-200/60 dark:border-zinc-800/50 overflow-hidden card-inset flex items-center justify-center p-2 min-h-[320px]">
        {loadState === 'ready' && blobUrl ? (
          <img
            src={blobUrl}
            alt={t('visuals.organigramme.alt_text')}
            className="w-full h-auto rounded-lg shadow-md object-contain max-h-[500px]"
          />
        ) : loadState === 'loading' || isGenerating ? (
          <div className="flex flex-col items-center gap-2 text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin" />
            {t('visuals.organigramme.loading')}
          </div>
        ) : loadState === 'missing' ? (
          <div className="flex flex-col items-center gap-2 text-slate-500 text-xs text-center px-6">
            <Users className="w-8 h-8 text-slate-400 dark:text-slate-600" />
            {t('visuals.organigramme.empty_title')}
            <span>{t('visuals.organigramme.empty_hint')}</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-danger text-xs text-center px-6">
            <AlertTriangle className="w-8 h-8" />
            {t(authExpired ? 'visuals.organigramme.error_title_auth' : 'visuals.organigramme.error_title')}
            <span>{t('visuals.organigramme.error_hint')}</span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400 pt-2 border-t border-slate-100 dark:border-slate-900">
        <span>{t('visuals.organigramme.footer_text')}</span>
        <span className="text-positive font-medium">{t('visuals.organigramme.footer_badge')}</span>
      </div>
    </div>
  );
}
