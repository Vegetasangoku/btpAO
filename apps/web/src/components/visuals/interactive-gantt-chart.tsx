'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { BarChart3, RefreshCw, Calendar, AlertTriangle, Plus, Trash2, Flag, Sparkles } from 'lucide-react';
// @ts-ignore -- vendored, untyped-by-upstream JS bundle; see index.d.ts for the hand-written surface we rely on.
import Gantt from '@/vendor/frappe-gantt/frappe-gantt.es.js';
import '@/vendor/frappe-gantt/frappe-gantt.css';
import '@/vendor/frappe-gantt/frappe-gantt-overrides.css';
import { api } from '@/lib/api';
import { GanttTask } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

const HEX_RE = /^#?[0-9a-fA-F]{6}$/;

function parseHex(hex: unknown): [number, number, number] | null {
  if (typeof hex !== 'string' || !HEX_RE.test(hex.trim())) return null;
  const n = parseInt(hex.trim().replace('#', ''), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Eclaircit (amount > 0) ou fonce (amount < 0) une couleur hex. Sert a deriver la
 *  teinte de progression et le liseré depuis la seule primary_color de la charte,
 *  pour ne pas demander trois couleurs a l'utilisateur. */
function shade(hex: string, amount: number): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  const out = rgb.map((v) => Math.max(0, Math.min(255, Math.round(v * (1 + amount)))));
  return `#${((out[0] << 16) | (out[1] << 8) | out[2]).toString(16).padStart(6, '0')}`;
}

/** Noir ou blanc selon la luminance percue (ITU-R BT.601) -- meme regle que
 *  _readable_text_color cote backend, pour que le Gantt interactif et le PNG genere
 *  prennent la meme decision sur une charte claire (jaune, cyan...). */
function readableOn(hex: string): string {
  const rgb = parseHex(hex);
  if (!rgb) return '#ffffff';
  return (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000 > 150 ? '#0f172a' : '#ffffff';
}

/** shape_style de la charte -> arrondi des barres. Memes trois valeurs que le backend
 *  (_boxstyle_for dans diagram_service), pour que planning interactif et PNG exporte
 *  aient la meme silhouette. */
const SHAPE_RADIUS: Record<string, string> = {
  anguleux: '0px',
  arrondi: '4px',
  pilule: '999px',
};

/** Luminance relative percue, 0 (noir) a 1 (blanc). */
function luminance(hex: string): number {
  const rgb = parseHex(hex);
  if (!rgb) return 0.5;
  return (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000 / 255;
}

/**
 * Une couleur de charte peut etre inexploitable pour une barre de planning : le
 * secondary_color de ce tenant est #0f172a, quasi noir, donc invisible sur le fond
 * sombre du graphique (#111A24) -- et symetriquement une charte tres claire
 * disparaitrait en theme clair. On n'ecrase pas la charte pour autant : on se contente
 * d'ecarter la couleur quand elle sort de la bande lisible, et l'appelant retombe alors
 * sur une teinte derivee de la couleur primaire.
 */
function isUsableBarColor(hex: string): boolean {
  const l = luminance(hex);
  return l > 0.16 && l < 0.9;
}

function buildGanttBrandVars(cfg: Record<string, any> | null | undefined): Record<string, string> {
  const vars: Record<string, string> = {};
  if (!cfg) return vars;
  const primary = typeof cfg.primary_color === 'string' && HEX_RE.test(cfg.primary_color.trim())
    ? cfg.primary_color.trim() : null;
  const rawSecondary = typeof cfg.secondary_color === 'string' && HEX_RE.test(cfg.secondary_color.trim())
    ? cfg.secondary_color.trim() : null;
  // Jalons : on n'accepte la couleur secondaire que si elle reste lisible (voir
  // isUsableBarColor). Sinon on derive du primaire plus bas.
  const secondary = rawSecondary && isUsableBarColor(rawSecondary) ? rawSecondary : null;
  if (primary) {
    vars['--btp-gantt-bar'] = primary;
    vars['--btp-gantt-bar-progress'] = shade(primary, -0.28);
    vars['--btp-gantt-bar-stroke'] = shade(primary, -0.45);
    vars['--btp-gantt-bar-text'] = readableOn(primary);
    vars['--btp-gantt-today'] = primary;
    if (!secondary) {
      vars['--btp-gantt-milestone'] = shade(primary, 0.22);
      vars['--btp-gantt-milestone-progress'] = primary;
    }
  }
  if (secondary) {
    vars['--btp-gantt-milestone'] = secondary;
    vars['--btp-gantt-milestone-progress'] = shade(secondary, -0.28);
  }
  const radius = SHAPE_RADIUS[String(cfg.shape_style || '').toLowerCase()];
  if (radius) vars['--btp-gantt-radius'] = radius;
  return vars;
}

interface InteractiveGanttChartProps {
  projectId: string;
  projectTitle?: string;
}

/** Adds `days` to an ISO "YYYY-MM-DD" string via a UTC-noon pivot (sidesteps any DST
 *  edge case entirely) -- used for pure date-only arithmetic that never touches a
 *  timezone-sensitive `Date` object constructed by the browser. */
function addDaysIso(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number);
  const t = Date.UTC(y, (m || 1) - 1, d || 1, 12) + days * 86400000;
  const dt = new Date(t);
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}-${String(dt.getUTCDate()).padStart(2, '0')}`;
}

/** Reads a `Date` object's LOCAL calendar fields (never `.toISOString()`, which
 *  converts to UTC and can silently shift the date by a day depending on the
 *  viewer's timezone offset) -- used to convert the Date objects frappe-gantt hands
 *  back from on_date_change into the "YYYY-MM-DD" strings the API expects. */
function localIso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function InteractiveGanttChart({ projectId, projectTitle = 'Projet BTP' }: InteractiveGanttChartProps) {
  const { t, language } = useTranslation();
  const [tasks, setTasks] = useState<GanttTask[]>([]);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [authExpired, setAuthExpired] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportInfo, setExportInfo] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'Day' | 'Week' | 'Month'>('Week');
  // Voir scrollToFirstBar() : la vue n'est recalee automatiquement qu'une fois, pour ne
  // pas ecraser le defilement que l'utilisateur fait lui-meme ensuite.
  const hasAutoScrolledRef = useRef(false);
  // Charte graphique du tenant appliquee au planning (04/09, demande Charbel : le Gantt
  // doit reprendre les couleurs de la charte comme le font deja les PNG generes).
  const [brandVars, setBrandVars] = useState<Record<string, string>>({});
  const [nameEdits, setNameEdits] = useState<Record<string, string>>({});
  const [learningProposal, setLearningProposal] = useState<{
    section_type: string;
    summary: string;
    suggested_content: string;
    diff_percentage: number;
  } | null>(null);
  const [savingLearning, setSavingLearning] = useState(false);
  const [learningScope, setLearningScope] = useState<'this_ao' | 'similar_aos' | 'all_future'>('similar_aos');
  const containerRef = useRef<HTMLDivElement | null>(null);
  const ganttRef = useRef<any>(null);

  const reload = useCallback(async () => {
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
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;
    setLoadState('loading');
    ganttRef.current = null;
    api.listGanttTasks(projectId)
      .then((res) => {
        if (cancelled) return;
        setTasks(res);
        setLoadState('ready');
      })
      .catch((err: any) => {
        console.error('Failed to load Gantt tasks', err);
        if (!cancelled) {
          setAuthExpired(err?.status === 401);
          setLoadState('error');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const persistDateChange = useCallback(async (taskId: string, start: Date, end: Date) => {
    try {
      await api.updateGanttTask(projectId, taskId, { start_date: localIso(start), end_date: localIso(end) });
      await reload();
    } catch (err) {
      console.error('Failed to persist Gantt date change', err);
      await reload(); // resync the chart with the server's authoritative state either way
    }
  }, [projectId, reload]);

  const persistProgressChange = useCallback(async (taskId: string, progress: number) => {
    try {
      await api.updateGanttTask(projectId, taskId, { progress: Math.round(progress) });
      await reload();
    } catch (err) {
      console.error('Failed to persist Gantt progress change', err);
      await reload();
    }
  }, [projectId, reload]);

  /**
   * frappe-gantt ouvre toujours la vue sur la date du jour. Or sur un appel d'offres
   * le chantier demarre presque toujours plus tard (ici : premiere tache au 01/10 alors
   * qu'on est le 04/09) : toutes les barres se retrouvent hors cadre a droite et
   * l'utilisateur voit une grille vide, en croyant que le planning est casse. Constate
   * en direct le 04/09 -- canvas de 4900 px pour une fenetre de 533 px, premiere barre
   * a x=600, scrollLeft a 0. On recale donc la vue sur la premiere tache.
   */
  useEffect(() => {
    let cancelled = false;
    api.getTenant()
      .then((tenant) => {
        if (!cancelled) setBrandVars(buildGanttBrandVars(tenant?.branding_config));
      })
      .catch((err) => {
        // La charte est un confort, jamais une dependance : en cas d'echec on laisse les
        // valeurs par defaut definies dans frappe-gantt-overrides.css.
        console.error('Failed to load tenant branding for Gantt', err);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const scrollToFirstBar = useCallback(() => {
    const container = containerRef.current?.querySelector('.gantt-container') as HTMLElement | null;
    if (!container) return;
    const xs = Array.from(container.querySelectorAll('.bar-wrapper .bar'))
      .map((b) => parseFloat(b.getAttribute('x') || ''))
      .filter((n) => !Number.isNaN(n));
    if (!xs.length) return;
    const firstX = Math.min(...xs);
    // Deja visible : on ne bouge pas (chantier deja commence, ou vue Month tres large).
    if (firstX < container.clientWidth - 40) return;
    container.scrollLeft = Math.max(0, firstX - 40);
  }, []);

  useEffect(() => {
    if (loadState !== 'ready') return;

    if (tasks.length === 0) {
      // Container isn't rendered in the empty state (see JSX below) -- any prior
      // instance is now bound to a detached node, so drop it. The next time tasks
      // becomes non-empty a fresh instance gets created against the freshly-mounted div.
      ganttRef.current = null;
      return;
    }
    if (!containerRef.current) return;

    // Un chemin critique n'informe que s'il DISTINGUE des taches. Sur un planning
    // enchaine bout a bout (le cas courant d'un phasage BTP), 100 % des taches sont
    // critiques : tout peindre en rouge ne dit plus rien et masque completement la
    // charte graphique du client. Dans ce cas on laisse les barres a la couleur de
    // marque -- l'information "tout est critique" reste portee par le compteur de
    // taches et l'infobulle, pas par un aplat rouge integral.
    const allCritical = tasks.length > 0 && tasks.every((t) => t.is_critical);

    const frappeTasks = tasks.map((task) => ({
      id: task.id,
      name: task.is_milestone ? `◆ ${task.name}${task.milestone_label ? ' — ' + task.milestone_label : ''}` : task.name,
      start: task.start_date,
      end: task.end_date,
      progress: task.progress,
      dependencies: task.depends_on.join(','),
      custom_class: task.is_critical && !allCritical
        ? 'gantt-critical'
        : task.is_milestone
          ? 'gantt-milestone'
          : '',
    }));

    if (!ganttRef.current) {
      ganttRef.current = new Gantt(containerRef.current, frappeTasks, {
        view_mode: viewMode,
        language,
        readonly: false,
        move_dependencies: true,
        popup_on: 'click',
        on_date_change: (task: any, start: Date, end: Date) => {
          persistDateChange(task.id, start, end);
        },
        on_progress_change: (task: any, progress: number) => {
          persistProgressChange(task.id, progress);
        },
      });
    } else {
      ganttRef.current.refresh(frappeTasks);
    }
    // Apres le rendu du SVG (d'ou le rAF), une seule fois : cf. scrollToFirstBar.
    if (!hasAutoScrolledRef.current) {
      requestAnimationFrame(() => {
        scrollToFirstBar();
        hasAutoScrolledRef.current = true;
      });
    }
    // Deliberately excludes persistDateChange/persistProgressChange/viewMode: the
    // handlers are captured once at instantiation and stay valid (they always fetch
    // fresh state via reload() rather than closing over stale `tasks`); viewMode has
    // its own effect below via change_view_mode so it doesn't need to force a rebuild.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks, loadState]);

  useEffect(() => {
    if (ganttRef.current && tasks.length > 0) {
      ganttRef.current.change_view_mode(viewMode);
      // Changer d'echelle recalcule toute la geometrie : on repositionne la vue.
      hasAutoScrolledRef.current = false;
      requestAnimationFrame(() => {
        scrollToFirstBar();
        hasAutoScrolledRef.current = true;
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode]);

  const handleAddTask = async () => {
    const last = tasks.length > 0 ? [...tasks].sort((a, b) => a.end_date.localeCompare(b.end_date)).pop() : undefined;
    const start = last ? last.end_date : new Date().toISOString().slice(0, 10);
    try {
      await api.createGanttTask(projectId, {
        name: 'Nouvelle tâche',
        start_date: start,
        end_date: addDaysIso(start, 7),
        progress: 0,
        is_milestone: false,
        depends_on: last ? [last.id] : [],
      });
      await reload();
    } catch (err) {
      console.error('Failed to add Gantt task', err);
    }
  };

  const handleDelete = async (taskId: string) => {
    try {
      await api.deleteGanttTask(projectId, taskId);
      await reload();
    } catch (err) {
      console.error('Failed to delete Gantt task', err);
    }
  };

  const handleRenameCommit = async (task: GanttTask, newName: string) => {
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
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const res = await api.generateGantt(projectId, projectTitle, []);
      const criticalCount = (res as any).critical_task_count;
      setExportInfo(
        t('visuals.gantt_interactive.export_weeks', { weeks: res.total_weeks }) +
        (typeof criticalCount === 'number' ? t('visuals.gantt_interactive.export_critical', { count: criticalCount }) : '') +
        t('visuals.gantt_interactive.export_delivery', { date: res.completion_date })
      );
    } catch (err) {
      console.error('Failed to export Gantt', err);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="card-modern p-5 space-y-4 font-sans">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-line">
        <div>
          <h3 className="text-[13px] font-bold text-foreground flex items-center gap-2 font-heading">
            <BarChart3 className="w-4 h-4 text-hl" />
            {t('visuals.gantt_interactive.title')}
          </h3>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            {t('visuals.gantt_interactive.subtitle')}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="tab-group !p-0.5">
            {(['Day', 'Week', 'Month'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setViewMode(m)}
                className={`px-2.5 py-1 text-[11px] font-mono font-medium transition-all duration-200 cursor-pointer rounded-md ${
                  viewMode === m
                    ? 'bg-hl text-hl-contrast font-bold shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {m === 'Day' ? t('visuals.gantt_interactive.view_day') : m === 'Week' ? t('visuals.gantt_interactive.view_week') : t('visuals.gantt_interactive.view_month')}
              </button>
            ))}
          </div>
          <button
            onClick={handleAddTask}
            className="btn-secondary !py-1.5 !px-2.5 !text-[11px] cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            {t('visuals.gantt_interactive.add_task_btn')}
          </button>
          <button
            onClick={handleExport}
            disabled={isExporting || tasks.length === 0}
            className="btn-primary !py-1.5 !px-2.5 !text-[11px] cursor-pointer"
          >
            <RefreshCw className={`w-3 h-3 ${isExporting ? 'animate-spin' : ''}`} />
            {isExporting ? t('visuals.gantt_interactive.exporting') : t('visuals.gantt_interactive.export_btn')}
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

      {exportInfo && (
        <div className="p-2.5 rounded-xl bg-positive/8 border border-positive/20 text-positive text-[12px] flex items-center gap-2 font-mono">
          <Sparkles className="w-3.5 h-3.5 shrink-0 text-positive" />
          <span>{t('visuals.gantt_interactive.export_success_prefix')} {exportInfo}</span>
        </div>
      )}

      <div className="relative rounded-xl border border-line overflow-x-auto card-inset min-h-[280px]">
        {loadState === 'loading' ? (
          <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground text-xs py-14 font-mono">
            <RefreshCw className="w-5 h-5 animate-spin text-hl" />
            {t('visuals.gantt_interactive.loading')}
          </div>
        ) : loadState === 'error' ? (
          <div className="flex flex-col items-center justify-center gap-2 text-danger text-xs text-center px-6 py-14">
            <AlertTriangle className="w-6 h-6" />
            {t(authExpired ? 'visuals.gantt_interactive.error_title_auth' : 'visuals.gantt_interactive.error_title')}
          </div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground text-xs text-center px-6 py-14">
            <Calendar className="w-7 h-7 opacity-40" />
            <p>{t('visuals.gantt_interactive.empty_title')}</p>
            <button onClick={handleAddTask} className="text-hl font-semibold underline cursor-pointer">
              {t('visuals.gantt_interactive.empty_add_btn')}
            </button>
          </div>
        ) : (
          <div ref={containerRef} className="gantt-target p-2" style={brandVars as React.CSSProperties} />
        )}
      </div>

      {tasks.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] font-mono font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <Flag className="w-3 h-3 text-hl" /> {t('visuals.gantt_interactive.tasks_count', { count: tasks.length })}
          </div>
          <div className="max-h-48 overflow-y-auto space-y-1 pr-1 divide-y divide-transparent">
            {tasks.map((task) => (
              <div
                key={task.id}
                className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs border transition-colors ${
                  task.is_critical
                    ? 'border-danger/25 bg-danger/50 dark:bg-danger/20'
                    : 'border-line bg-card'
                }`}
              >
                {task.is_critical && (
                  <span className="w-1.5 h-1.5 rounded-full bg-danger shrink-0" title={t('visuals.gantt_interactive.critical_path_title')} />
                )}
                <input
                  value={nameEdits[task.id] ?? task.name}
                  onChange={(e) => setNameEdits((prev) => ({ ...prev, [task.id]: e.target.value }))}
                  onBlur={(e) => handleRenameCommit(task, e.target.value)}
                  className="flex-1 min-w-0 bg-transparent text-slate-800 dark:text-zinc-200 font-medium focus:outline-none focus:ring-1 focus:ring-hl rounded px-1 text-xs"
                />
                <span className="text-[10px] font-mono text-muted-foreground shrink-0 tabular-nums">
                  {task.start_date} → {task.end_date}
                </span>
                <span className="text-[10px] font-mono text-muted-foreground shrink-0 tabular-nums w-8 text-right font-semibold">{task.progress}%</span>
                <button
                  onClick={() => handleDelete(task.id)}
                  className="text-slate-300 dark:text-zinc-600 hover:text-danger dark:hover:text-danger shrink-0 cursor-pointer p-0.5"
                  title={t('visuals.gantt_interactive.delete_task_title')}
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground pt-2 border-t border-line">
        <span>{t('visuals.gantt_interactive.footer_text')}</span>
        <span className="text-hl font-semibold">{t('visuals.section3_badge')}</span>
      </div>
    </div>
  );
}
