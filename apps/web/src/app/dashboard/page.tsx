'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Sparkles,
  FolderKanban,
  CheckCircle2,
  Building2,
  Palette,
  Loader2,
  FileText,
  ChevronRight,
  HardHat,
  Plus,
} from 'lucide-react';
import { api } from '@/lib/api';
import { Project } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

export default function DashboardOverviewPage() {
  const { t } = useTranslation();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const list = await api.getProjects().catch(() => []);
        setProjects(list || []);
      } catch (err) {
        console.warn('Erreur chargement projets:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const totalDossiers = projects.length;
  const inProgress = projects.filter((p) => p.status === 'draft' || p.status === 'in_progress').length;
  const completed = projects.filter((p) => p.status === 'completed' || p.outcome_status === 'won' || p.outcome_status === 'submitted').length;

  return (
    <div className="space-y-8 pb-16">
      {/* Top Welcome Banner */}
      <div className="p-6 sm:p-8 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] shadow-subtle flex flex-wrap items-center justify-between gap-6">
        <div className="space-y-1.5 max-w-xl">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
              {t('dash.badge')}
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white font-heading">
            {t('dash.title')}
          </h1>
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400">
            {t('dash.desc')}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Link
            href="/dashboard/wizard"
            className="flex items-center gap-2 px-5 py-3 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs shadow-subtle transition-all cursor-pointer font-heading"
          >
            <Sparkles className="w-4 h-4" />
            <span>{t('dash.btn_new')}</span>
          </Link>
          <Link
            href="/dashboard/projects"
            className="flex items-center gap-2 px-4 py-3 rounded-lg bg-slate-100 dark:bg-[#1E2638] hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-semibold border border-slate-200 dark:border-[#1E2638] transition-all"
          >
            <FolderKanban className="w-4 h-4 text-slate-500 dark:text-slate-400" />
            <span>{t('dash.btn_all')} ({totalDossiers})</span>
          </Link>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1 */}
        <div className="p-5 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-3 shadow-subtle">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-semibold">{t('dash.kpi_in_progress')}</span>
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center">
              <FolderKanban className="w-4 h-4" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-slate-900 dark:text-white font-heading">
              {inProgress}
            </span>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">{t('dash.total_sub')}: {totalDossiers}</span>
          </div>
        </div>

        {/* Card 2 */}
        <div className="p-5 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-3 shadow-subtle">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-semibold">{t('dash.kpi_completed')}</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-slate-900 dark:text-white font-heading">
              {completed}
            </span>
            <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">{t('dash.ready_badge')}</span>
          </div>
        </div>

        {/* Card 3 */}
        <div className="p-5 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-3 shadow-subtle">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-semibold">{t('dash.kpi_active_model')}</span>
            <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center">
              <Palette className="w-4 h-4" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-xs font-bold text-slate-900 dark:text-white font-heading truncate">
              {t('dash.kpi_deduced')}
            </span>
          </div>
          <p className="text-[10px] text-slate-500 dark:text-slate-400">{t('dash.kpi_deduced_sub')}</p>
        </div>

        {/* Card 4 */}
        <div className="p-5 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-3 shadow-subtle">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
            <span className="text-xs font-semibold">{t('dash.kpi_knowledge')}</span>
            <div className="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center">
              <Building2 className="w-4 h-4" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-xs font-bold text-slate-900 dark:text-white font-heading">
              {t('dash.kpi_active_base')}
            </span>
          </div>
          <p className="text-[10px] text-slate-500 dark:text-slate-400">{t('dash.kpi_proofs_sub')}</p>
        </div>
      </div>

      {/* Main Section: Recent Tenders Table & Quick Navigation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Recent Tenders */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <FolderKanban className="w-4 h-4 text-amber-500" />
              <span>{t('dash.recent_title')}</span>
            </h2>
            <Link
              href="/dashboard/projects"
              className="text-xs text-amber-600 dark:text-amber-400 hover:underline font-semibold flex items-center gap-1"
            >
              <span>{t('dash.see_all')}</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] overflow-hidden shadow-subtle">
            {loading ? (
              <div className="p-12 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
                <span>{t('dash.loading')}</span>
              </div>
            ) : projects.length === 0 ? (
              <div className="p-8 text-center space-y-3">
                <FileText className="w-8 h-8 text-slate-400 mx-auto" />
                <p className="text-xs font-bold text-slate-700 dark:text-slate-300">
                  {t('dash.empty_title')}
                </p>
                <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                  {t('dash.empty_desc')}
                </p>
                <Link
                  href="/dashboard/wizard"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-600 text-white text-xs font-bold font-heading"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>{t('dash.empty_btn')}</span>
                </Link>
              </div>
            ) : (
              <div className="divide-y divide-slate-200 dark:divide-[#1E2638]">
                {projects.slice(0, 5).map((p) => (
                  <Link
                    key={p.id}
                    href={`/projects/${p.id}`}
                    className="p-4 flex flex-wrap items-center justify-between gap-3 hover:bg-slate-50 dark:hover:bg-[#1A2130] transition-colors group"
                  >
                    <div className="space-y-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-amber-600 dark:text-amber-400">
                          {p.reference_code || 'AO-SANS-REF'}
                        </span>
                        <span className="text-xs font-bold text-slate-900 dark:text-white group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors truncate">
                          {p.title}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">
                        {p.client_name} • {p.location || 'France'}
                      </p>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {p.go_no_go && p.go_no_go.has_sufficient_data !== false && (
                        <span
                          className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                            p.go_no_go.recommendation === 'GO'
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                              : p.go_no_go.recommendation === 'RESERVES' || p.go_no_go.recommendation === 'RÉSERVES'
                              ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                              : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'
                          }`}
                        >
                          {Math.round(p.go_no_go.score)}% {p.go_no_go.recommendation}
                        </span>
                      )}
                      <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                        p.status === 'completed' || p.outcome_status === 'won'
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                          : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
                      }`}>
                        {p.status === 'completed' ? 'Finalisé' : 'En cours'}
                      </span>
                      <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-amber-500 transition-colors" />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right 1 Col: Quick Actions */}
        <div className="space-y-4">
          <h2 className="text-base font-bold text-slate-900 dark:text-white font-heading">
            Accès Rapides & Configuration
          </h2>

          <div className="space-y-3">
            <Link
              href="/dashboard/company"
              className="p-4 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] flex items-start gap-3 hover:border-amber-500/40 transition-colors group shadow-subtle block"
            >
              <div className="w-8 h-8 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                <Building2 className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                  {t('nav.company')}
                </p>
                <p className="text-[11px] text-slate-600 dark:text-slate-400 mt-0.5">
                  Fiches références, équipe de conducteurs et sites indexés.
                </p>
              </div>
            </Link>

            <Link
              href="/dashboard/branding"
              className="p-4 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] flex items-start gap-3 hover:border-amber-500/40 transition-colors group shadow-subtle block"
            >
              <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                <Palette className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                  {t('nav.branding')}
                </p>
                <p className="text-[11px] text-slate-600 dark:text-slate-400 mt-0.5">
                  Charte Word (.docx), couleurs de tableau et logo.
                </p>
              </div>
            </Link>

            <Link
              href="/dashboard/settings"
              className="p-4 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] flex items-start gap-3 hover:border-amber-500/40 transition-colors group shadow-subtle block"
            >
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
                <HardHat className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                  {t('nav.settings')}
                </p>
                <p className="text-[11px] text-slate-600 dark:text-slate-400 mt-0.5">
                  Taux horaires, marges cibles, quotas et thème clair/sombre.
                </p>
              </div>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
