'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  ArrowLeft,
  UploadCloud,
  ClipboardList,
  FileEdit,
  BarChart2,
  Download,
  CheckCircle2,
  ChevronRight,
  Loader2,
  Building2,
  Calendar,
  Banknote,
  Sparkles,
  Calculator,
} from 'lucide-react';
import { Project } from '@/lib/types';
import { api } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';
import { ProjectCountryBanner } from '@/components/projects/project-country-banner';

const PIPELINE_STEPS = [
  { key: 'dce', labelKey: 'projects.hub.step1_label', icon: UploadCloud, descKey: 'projects.hub.step1_desc' },
  { key: 'decisions', labelKey: 'projects.hub.step2_label', icon: ClipboardList, descKey: 'projects.hub.step2_desc' },
  { key: 'editor', labelKey: 'projects.hub.step3_label', icon: FileEdit, descKey: 'projects.hub.step3_desc' },
  { key: 'visuals', labelKey: 'projects.hub.step4_label', icon: BarChart2, descKey: 'projects.hub.step4_desc' },
  { key: 'export', labelKey: 'projects.hub.step5_label', icon: Download, descKey: 'projects.hub.step5_desc' },
  { key: 'chiffrage', labelKey: 'projects.hub.step6_label', icon: Calculator, descKey: 'projects.hub.step6_desc' },
] as const;

export default function ProjectHubPage() {
  const { t } = useTranslation();
  const params = useParams();
  const projectId = params.id as string;
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getProject(projectId)
      .then(setProject)
      .catch(console.warn)
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-[13px] text-muted-foreground font-mono">
        <Loader2 className="w-6 h-6 animate-spin text-hl" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-20 text-muted-foreground font-mono">
        <p>{t('projects.hub.not_found')}</p>
        <Link href="/dashboard/projects" className="btn-secondary text-[12px] mt-4 inline-flex">
          {t('projects.hub.back_to_projects')}
        </Link>
      </div>
    );
  }

  return (
    <div className="page-container max-w-5xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground font-sans">
        <Link href="/dashboard/projects" className="hover:text-hl transition-colors flex items-center gap-1 font-medium cursor-pointer">
          <ArrowLeft className="w-3.5 h-3.5" /> {t('projects.hub.breadcrumb_projects')}
        </Link>
        <ChevronRight className="w-3 h-3 opacity-50" />
        <span className="text-foreground font-semibold truncate max-w-sm">{project.title}</span>
      </div>

      {/* Hero Card */}
      <div className="card-elevated p-6 sm:p-7 space-y-4 rounded-2xl">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="badge-pill-slate font-mono text-[9px]">
            {project.reference_code || 'REF-AO'}
          </span>
          {project.go_no_go && project.go_no_go.has_sufficient_data !== false && (
            <span
              className={`badge-pill font-mono text-[9px] ${
                project.go_no_go.recommendation === 'GO'
                  ? 'badge-pill-emerald'
                  : project.go_no_go.recommendation === 'RESERVES' || project.go_no_go.recommendation === 'RÉSERVES'
                  ? 'bg-hl/10 text-hl border border-hl/20'
                  : 'badge-pill-red'
              }`}
            >
              {t('projects.hub.go_no_go_score', { score: String(Math.round(project.go_no_go.score)), recommendation: project.go_no_go.recommendation })}
            </span>
          )}
          <span className="badge-pill-slate text-[9px]">
            {t('projects.hub.badge_active')}
          </span>
        </div>

        <h1 className="text-xl sm:text-2xl font-extrabold text-foreground font-heading tracking-tight">{project.title}</h1>

        <div className="flex flex-wrap gap-4 text-[12px] text-muted-foreground pt-1">
          <div className="flex items-center gap-1.5">
            <Building2 className="w-3.5 h-3.5 text-hl shrink-0" />
            <span>{t('projects.hub.client_label', { name: '' })}<strong className="text-foreground font-semibold">{project.client_name}</strong></span>
          </div>
          {project.budget_estimate && (
            <div className="flex items-center gap-1.5">
              <Banknote className="w-3.5 h-3.5 text-positive shrink-0" />
              <span>{t('projects.hub.budget_prefix')}<strong className="text-foreground font-mono font-bold">{project.budget_estimate.toLocaleString('fr-FR')}</strong> {t('projects.hub.budget_suffix')}</span>
            </div>
          )}
          {project.submission_deadline && (
            <div className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-hl shrink-0" />
              <span>{t('projects.hub.deadline_label', { date: '' })}<strong className="text-foreground font-mono font-bold">{new Date(project.submission_deadline).toLocaleDateString('fr-FR')}</strong></span>
            </div>
          )}
        </div>

        {/* Pays du marche : place juste sous l'entete du dossier, car il conditionne tout
            le contenu genere en aval (normes, sources officielles, qualifications). */}
        <ProjectCountryBanner projectId={projectId} />
      </div>

      {/* Pipeline Steps Cards */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="section-title text-[15px]">{t('projects.hub.workflow_title')}</h2>
          <span className="badge-pill-slate text-[10px] font-mono">{t('projects.hub.steps_count')}</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {PIPELINE_STEPS.map((step, index) => {
            const Icon = step.icon;
            return (
              <Link
                key={step.key}
                href={`/projects/${projectId}/${step.key}`}
                className="card-modern-hover p-4 space-y-3 flex flex-col justify-between cursor-pointer group rounded-2xl"
              >
                <div className="space-y-2.5">
                  <div className="w-9 h-9 rounded-xl bg-hl/10 text-hl flex items-center justify-center group-hover:bg-hl group-hover:text-hl-contrast transition-all duration-200 shadow-xs">
                    <Icon className="w-4 h-4" />
                  </div>

                  <div className="space-y-1">
                    <div className="text-[13px] font-bold text-foreground group-hover:text-hl transition-colors font-heading">
                      {t(step.labelKey)}
                    </div>
                    <p className="text-[11px] text-muted-foreground leading-relaxed">{t(step.descKey)}</p>
                  </div>
                </div>

                <div className="flex items-center justify-end text-hl text-[11px] font-semibold pt-2 border-t border-line group-hover:translate-x-0.5 transition-all">
                  <span>{t('projects.hub.access_btn')}</span>
                  <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
