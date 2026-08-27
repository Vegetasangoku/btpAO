'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { BarChart3, RefreshCw, Calendar, AlertTriangle, Plus, Trash2, Flag, Sparkles } from 'lucide-react';
// @ts-ignore -- vendored, untyped-by-upstream JS bundle; see index.d.ts for the hand-written surface we rely on.
import Gantt from '@/vendor/frappe-gantt/frappe-gantt.es.js';
import '@/vendor/frappe-gantt/frappe-gantt.css';
import '@/vendor/frappe-gantt/frappe-gantt-overrides.css';
import { api } from '@/lib/api';
import { GanttTask } from '@/lib/types';

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
  const [tasks, setTasks] = useState<GanttTask[]>([]);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [isExporting, setIsExporting] = useState(false);
  const [exportInfo, setExportInfo] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'Day' | 'Week' | 'Month'>('Week');
  const [nameEdits, setNameEdits] = useState<Record<string, string>>({});
  const containerRef = useRef<HTMLDivElement | null>(null);
  const ganttRef = useRef<any>(null);

  const reload = useCallback(async () => {
    try {
      const res = await api.listGanttTasks(projectId);
      setTasks(res);
      setLoadState('ready');
    } catch (err) {
      console.error('Failed to load Gantt tasks', err);
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
      .catch((err) => {
        console.error('Failed to load Gantt tasks', err);
        if (!cancelled) setLoadState('error');
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

    const frappeTasks = tasks.map((t) => ({
      id: t.id,
      name: t.is_milestone ? `◆ ${t.name}${t.milestone_label ? ' — ' + t.milestone_label : ''}` : t.name,
      start: t.start_date,
      end: t.end_date,
      progress: t.progress,
      dependencies: t.depends_on.join(','),
      custom_class: t.is_critical ? 'gantt-critical' : t.is_milestone ? 'gantt-milestone' : '',
    }));

    if (!ganttRef.current) {
      ganttRef.current = new Gantt(containerRef.current, frappeTasks, {
        view_mode: viewMode,
        language: 'fr',
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
    // Deliberately excludes persistDateChange/persistProgressChange/viewMode: the
    // handlers are captured once at instantiation and stay valid (they always fetch
    // fresh state via reload() rather than closing over stale `tasks`); viewMode has
    // its own effect below via change_view_mode so it doesn't need to force a rebuild.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks, loadState]);

  useEffect(() => {
    if (ganttRef.current && tasks.length > 0) {
      ganttRef.current.change_view_mode(viewMode);
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

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const res = await api.generateGantt(projectId, projectTitle, []);
      const criticalCount = (res as any).critical_task_count;
      setExportInfo(
        `${res.total_weeks} semaines` +
        (typeof criticalCount === 'number' ? ` · ${criticalCount} tâche(s) critique(s)` : '') +
        ` · Livraison le ${res.completion_date}`
      );
    } catch (err) {
      console.error('Failed to export Gantt', err);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xl dark:shadow-2xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-amber-600 dark:text-amber-400" />
            Planning Prévisionnel Interactif (Gantt BTP)
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Glissez une barre pour changer les dates, glissez sa progression. Chaînage fin-à-début automatique, chemin critique en rouge.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden text-xs">
            {(['Day', 'Week', 'Month'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setViewMode(m)}
                className={`px-2.5 py-1.5 font-medium transition-colors ${
                  viewMode === m
                    ? 'bg-amber-600 text-white'
                    : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
                }`}
              >
                {m === 'Day' ? 'Jour' : m === 'Week' ? 'Semaine' : 'Mois'}
              </button>
            ))}
          </div>
          <button
            onClick={handleAddTask}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-semibold transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            Tâche
          </button>
          <button
            onClick={handleExport}
            disabled={isExporting || tasks.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow-sm disabled:opacity-50 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isExporting ? 'animate-spin' : ''}`} />
            {isExporting ? 'Génération...' : 'Exporter en HD'}
          </button>
        </div>
      </div>

      {exportInfo && (
        <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 text-emerald-700 dark:text-emerald-300 text-xs flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 shrink-0" />
          Image HD régénérée, prête pour l'export Word : {exportInfo}
        </div>
      )}

      <div className="relative rounded-xl border border-slate-200 dark:border-slate-800 overflow-x-auto bg-slate-50 dark:bg-slate-950 min-h-[300px]">
        {loadState === 'loading' ? (
          <div className="flex flex-col items-center justify-center gap-2 text-slate-400 text-xs py-16">
            <RefreshCw className="w-6 h-6 animate-spin" />
            Chargement du planning...
          </div>
        ) : loadState === 'error' ? (
          <div className="flex flex-col items-center justify-center gap-2 text-rose-500 text-xs text-center px-6 py-16">
            <AlertTriangle className="w-8 h-8" />
            Impossible de charger le planning (session expirée ou service indisponible).
          </div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 text-slate-400 text-xs text-center px-6 py-16">
            <Calendar className="w-8 h-8 text-slate-300 dark:text-slate-600" />
            Aucune tâche pour l'instant.
            <button onClick={handleAddTask} className="text-amber-600 dark:text-amber-400 font-semibold underline">
              Ajouter la première tâche
            </button>
          </div>
        ) : (
          <div ref={containerRef} className="gantt-target p-2" />
        )}
      </div>

      {tasks.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide flex items-center gap-1.5">
            <Flag className="w-3 h-3" /> Tâches ({tasks.length})
          </div>
          <div className="max-h-56 overflow-y-auto space-y-1 pr-1">
            {tasks.map((t) => (
              <div
                key={t.id}
                className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs border ${
                  t.is_critical
                    ? 'border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-500/5'
                    : 'border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40'
                }`}
              >
                {t.is_critical && (
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" title="Sur le chemin critique" />
                )}
                <input
                  value={nameEdits[t.id] ?? t.name}
                  onChange={(e) => setNameEdits((prev) => ({ ...prev, [t.id]: e.target.value }))}
                  onBlur={(e) => handleRenameCommit(t, e.target.value)}
                  className="flex-1 min-w-0 bg-transparent text-slate-700 dark:text-slate-200 font-medium focus:outline-none focus:ring-1 focus:ring-amber-500 rounded px-1"
                />
                <span className="text-slate-400 dark:text-slate-500 shrink-0 tabular-nums">
                  {t.start_date} → {t.end_date}
                </span>
                <span className="text-slate-400 dark:text-slate-500 shrink-0 tabular-nums w-10 text-right">{t.progress}%</span>
                <button
                  onClick={() => handleDelete(t.id)}
                  className="text-slate-300 dark:text-slate-600 hover:text-red-500 dark:hover:text-red-400 shrink-0"
                  title="Supprimer cette tâche"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-slate-400 dark:text-slate-500 pt-2 border-t border-slate-100 dark:border-slate-900">
        <span>Glisser-déposer + dépendances fin-à-début + chemin critique • Export HD 300 DPI pour Word</span>
        <span className="text-amber-600 dark:text-amber-400 font-medium">Inclus dans la section 3 (Méthodologie & Phasage)</span>
      </div>
    </div>
  );
}
