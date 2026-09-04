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
  const [templateInfo, setTemplateInfo] = useState<any>(null);
  const [assetsCount, setAssetsCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [list, template, assets] = await Promise.all([
          api.getProjects().catch(() => []),
          api.getSuggestedTemplate().catch(() => null),
          api.getKnowledgeAssets().catch(() => []),
        ]);
        setProjects(list || []);
        setTemplateInfo(template);
        setAssetsCount(Array.isArray(assets) ? assets.length : 0);
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
    <div className="page-container space-y-7 font-sans">
      {/* ─── Vision UI Welcome Hero Banner ─── */}
      <div className="on-ink vision-card-hero flex flex-wrap items-center justify-between gap-6">
        <div className="space-y-2 max-w-xl">
          <div className="flex items-center gap-2.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-hl/20 text-hl-contrast border border-hl/40 text-[10px] font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-positive animate-pulse"></span>
              {t('dash.badge')}
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-white font-heading tracking-tight">
            {t('dash.title')}
          </h1>
          <p className="text-[13px] text-zinc-300">
            {t('dash.desc')}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Link href="/dashboard/wizard" className="btn-primary shadow-lg shadow-hl/25 cursor-pointer">
            <Sparkles className="w-4 h-4" />
            <span>{t('dash.btn_new')}</span>
          </Link>
          <Link href="/dashboard/projects" className="btn-secondary !bg-white/10 hover:!bg-white/15 !text-white !border-white/20 cursor-pointer">
            <FolderKanban className="w-4 h-4 text-white" />
            <span>{t('dash.btn_all')} ({totalDossiers})</span>
          </Link>
        </div>
      </div>

      {/* ─── Vision UI KPI Cards Grid ─── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Card 1: En cours */}
        <div className="vision-card p-5 space-y-3 hover:border-hl/40 group">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{t('dash.kpi_in_progress')}</span>
            <div className="vision-kpi-icon group-hover:scale-105 transition-transform">
              <FolderKanban className="w-5 h-5 text-white" />
            </div>
          </div>
          <div className="flex items-baseline gap-2.5">
            <span className="text-3xl font-extrabold font-heading text-foreground tracking-tight">
              {inProgress}
            </span>
            <span className="text-[11px] text-muted-foreground font-mono">{t('dash.total_sub')}: {totalDossiers}</span>
          </div>
        </div>

        {/* Card 2: Finalisés */}
        <div className="vision-card p-5 space-y-3 hover:border-positive/40 group">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{t('dash.kpi_completed')}</span>
            <div className="vision-kpi-icon-emerald group-hover:scale-105 transition-transform">
              <CheckCircle2 className="w-5 h-5 text-white" />
            </div>
          </div>
          <div className="flex items-baseline gap-2.5">
            <span className="text-3xl font-extrabold font-heading text-foreground tracking-tight">
              {completed}
            </span>
            <span className="text-[11px] text-positive flex items-center gap-1.5 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-positive"></span>
              {t('dash.ready_badge')}
            </span>
          </div>
        </div>

        {/* Card 3: Modèle actif */}
        <div className="vision-card p-5 space-y-3 hover:border-hl/40 group">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{t('dash.kpi_active_model')}</span>
            <div className="vision-kpi-icon-indigo group-hover:scale-105 transition-transform">
              <Palette className="w-5 h-5 text-white" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold font-heading text-foreground truncate">
              {templateInfo?.has_custom_template ? 'Matrice Word Perso' : 'Template Standard'}
            </span>
          </div>
          <p className="text-[11px] text-muted-foreground truncate mt-1">Police: Arial / Bleu BTP</p>
        </div>

        {/* Card 4: Base de Savoir-faire */}
        <div className="vision-card p-5 space-y-3 hover:border-slate-500/40 group">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{t('dash.kpi_proofs_count')}</span>
            <div className="vision-kpi-icon-slate group-hover:scale-105 transition-transform">
              <FileText className="w-5 h-5 text-hl" />
            </div>
          </div>
          <div>
            <span className="text-3xl font-extrabold font-heading text-foreground tracking-tight">
              {assetsCount}
            </span>
            <p className="text-[11px] text-muted-foreground truncate mt-1">{t('dash.kpi_proofs_sub')}</p>
          </div>
        </div>
      </div>

      {/* ─── Main Section: Recent Tenders & Quick Actions ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left: Recent Tenders */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="section-title text-[15px]">
              <FolderKanban className="w-4 h-4 text-hl" />
              <span>{t('dash.recent_title')}</span>
            </h2>
            <Link
              href="/dashboard/projects"
              className="text-[13px] text-muted-foreground hover:text-hl font-medium flex items-center gap-1 transition-colors"
            >
              <span>{t('dash.see_all')}</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="card-modern overflow-hidden">
            {loading ? (
              <div className="p-12 text-center text-[13px] text-muted-foreground flex items-center justify-center gap-2.5">
                <Loader2 className="w-4 h-4 animate-spin text-hl" />
                <span>{t('dash.loading')}</span>
              </div>
            ) : projects.length === 0 ? (
              <div className="p-10 text-center space-y-3">
                <FileText className="w-10 h-10 text-slate-300 dark:text-zinc-600 mx-auto" />
                <p className="text-[14px] font-semibold text-foreground font-heading">
                  {t('dash.empty_title')}
                </p>
                <p className="text-[13px] text-muted-foreground max-w-sm mx-auto">
                  {t('dash.empty_desc')}
                </p>
                <Link href="/dashboard/wizard" className="btn-primary mt-3 cursor-pointer">
                  <Plus className="w-4 h-4" />
                  <span>{t('dash.empty_btn')}</span>
                </Link>
              </div>
            ) : (
              <div className="divide-y divide-line">
                {projects.slice(0, 5).map((p) => (
                  <Link
                    key={p.id}
                    href={`/projects/${p.id}`}
                    className="p-4 flex flex-wrap items-center justify-between gap-3 hover:bg-slate-50/60 dark:hover:bg-raised/50 transition-colors duration-150 group"
                  >
                    <div className="space-y-1 min-w-0 flex-1">
                      <div className="flex items-center gap-2.5">
                        <span className="text-[10px] text-muted-foreground bg-sunken px-2 py-0.5 rounded-full font-mono font-medium border border-slate-200/50 dark:border-line">
                          {p.reference_code || 'AO-SANS-REF'}
                        </span>
                        <span className="text-[13px] font-semibold text-foreground group-hover:text-hl transition-colors truncate">
                          {p.title}
                        </span>
                      </div>
                      <p className="text-[12px] text-muted-foreground">
                        {p.client_name} • {p.location || 'France'}
                      </p>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      {p.go_no_go && p.go_no_go.has_sufficient_data !== false && (
                        <span className="font-mono text-[11px] font-bold px-2.5 py-1 rounded-md bg-sunken border border-slate-200/60 dark:border-line text-slate-600 dark:text-zinc-300">
                          <span className={
                            p.go_no_go.recommendation === 'GO'
                              ? 'text-positive'
                              : p.go_no_go.recommendation === 'RESERVES' || p.go_no_go.recommendation === 'RÉSERVES'
                              ? 'text-hl'
                              : 'text-danger'
                          }>
                            {Math.round(p.go_no_go.score)}%
                          </span>
                          {' '}{p.go_no_go.recommendation}
                        </span>
                      )}
                      <span className="text-[11px] text-muted-foreground flex items-center gap-1.5 min-w-[70px]">
                        <span className={`w-2 h-2 rounded-full ${p.status === 'completed' || p.outcome_status === 'won' ? 'bg-positive' : 'bg-hl'}`}></span>
                        {p.status === 'completed' ? 'Finalisé' : 'En cours'}
                      </span>
                      <ChevronRight className="w-4 h-4 text-slate-300 dark:text-zinc-600 group-hover:text-hl transition-colors" />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Quick Actions */}
        <div className="space-y-3">
          <h2 className="section-title text-[15px]">
            Accès Rapides & Configuration
          </h2>

          <div className="space-y-2.5">
            <Link
              href="/dashboard/company"
              className="card-modern-hover p-4 flex items-start gap-3.5 group block"
            >
              <div className="w-9 h-9 rounded-lg bg-sunken text-muted-foreground flex items-center justify-center shrink-0 group-hover:text-hl group-hover:bg-hl/10 transition-all duration-200">
                <Building2 className="w-[18px] h-[18px]" />
              </div>
              <div className="min-w-0">
                <p className="text-[13px] font-semibold text-foreground group-hover:text-hl transition-colors font-heading">
                  {t('nav.company')}
                </p>
                <p className="text-[12px] text-muted-foreground mt-0.5 leading-relaxed">
                  Fiches références, équipe de conducteurs et sites indexés.
                </p>
              </div>
            </Link>

            <Link
              href="/dashboard/branding"
              className="card-modern-hover p-4 flex items-start gap-3.5 group block"
            >
              <div className="w-9 h-9 rounded-lg bg-sunken text-muted-foreground flex items-center justify-center shrink-0 group-hover:text-hl group-hover:bg-hl/10 transition-all duration-200">
                <Palette className="w-[18px] h-[18px]" />
              </div>
              <div className="min-w-0">
                <p className="text-[13px] font-semibold text-foreground group-hover:text-hl transition-colors font-heading">
                  {t('nav.branding')}
                </p>
                <p className="text-[12px] text-muted-foreground mt-0.5 leading-relaxed">
                  Charte Word (.docx), couleurs de tableau et logo.
                </p>
              </div>
            </Link>

            <Link
              href="/dashboard/settings"
              className="card-modern-hover p-4 flex items-start gap-3.5 group block"
            >
              <div className="w-9 h-9 rounded-lg bg-sunken text-muted-foreground flex items-center justify-center shrink-0 group-hover:text-hl group-hover:bg-hl/10 transition-all duration-200">
                <HardHat className="w-[18px] h-[18px]" />
              </div>
              <div className="min-w-0">
                <p className="text-[13px] font-semibold text-foreground group-hover:text-hl transition-colors font-heading">
                  {t('nav.settings')}
                </p>
                <p className="text-[12px] text-muted-foreground mt-0.5 leading-relaxed">
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
