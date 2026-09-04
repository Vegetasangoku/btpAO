'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  FileText,
  FileDown,
  Download,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Clock,
  Globe,
  Layers,
  ShieldCheck,
  Building2,
  Calendar,
  Banknote,
  ArrowLeft,
  ChevronRight,
  TrendingUp,
  AlertCircle,
  ExternalLink,
  RefreshCw,
  Award,
  Check,
  XCircle,
  Cpu,
  FileCheck,
} from 'lucide-react';
import { api, fetchAuthenticatedBlobUrl } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';
import { Project, SuggestedTemplate, GoNoGoAnalysis, GeneratedSection, ExportJob } from '@/lib/types';

const MANDATORY_SECTIONS = [
  { key: 'moyens_humains', title: '1. Moyens Humains & Encadrement Chantier' },
  { key: 'moyens_materiels', title: '2. Moyens Matériels & Équipements' },
  { key: 'methodologie_phasage', title: '3. Méthodologie & Phasage Travaux' },
  { key: 'qse_environnement', title: '4. Qualité, Sécurité & PPSPS' },
  { key: 'securite_ppsps', title: '5. RSE, Environnement & SOGED' },
];

export default function ExportPage() {
  const params = useParams();
  const projectId = params.id as string;
  const { t } = useTranslation();

  // Project & Context Data
  const [project, setProject] = useState<Project | null>(null);
  const [gonogo, setGonogo] = useState<GoNoGoAnalysis | null>(null);
  const [sections, setSections] = useState<GeneratedSection[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [calculatingGoNoGo, setCalculatingGoNoGo] = useState(false);

  // Standard Export States
  const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
  const [exporting, setExporting] = useState<'docx' | 'pdf' | null>(null);
  const [result, setResult] = useState<ExportJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [includeVisuals, setIncludeVisuals] = useState(true);
  const [includeCoverPage, setIncludeCoverPage] = useState(true);
  const [downloadingResult, setDownloadingResult] = useState(false);

  // Suggested Template State
  const [suggestedTemplate, setSuggestedTemplate] = useState<SuggestedTemplate | null>(null);
  const [loadingTemplate, setLoadingTemplate] = useState(true);

  // MEA / International Regional Export State
  const [meaCountry, setMeaCountry] = useState<'SA' | 'QA' | 'AE' | 'LB'>('SA');
  const [meaLanguage, setMeaLanguage] = useState<'fr' | 'en' | 'ar'>('fr');

  // 30/08 : pré-sélectionne la langue du dossier international sur celle déjà choisie
  // pour ce projet (output_language) -- réponse directe à la confusion "Word / PDF /
  // international, on comprend rien" : au moins la langue n'a plus besoin d'être
  // redevinée dans ce 2e formulaire séparé.
  useEffect(() => {
    if (project?.output_language === 'ar' || project?.output_language === 'en') {
      setMeaLanguage(project.output_language);
    }
  }, [project?.output_language]);
  const [exportingMea, setExportingMea] = useState(false);
  const [meaResult, setMeaResult] = useState<{ success: boolean; filename: string; docx_url?: string } | null>(null);
  const [meaError, setMeaError] = useState<string | null>(null);

  useEffect(() => {
    async function loadInitialData() {
      setLoadingData(true);
      try {
        const [projRes, gngRes, secRes, tmplRes] = await Promise.allSettled([
          api.getProject(projectId),
          api.getGoNoGo(projectId),
          api.getSections(projectId),
          api.getSuggestedTemplate(),
        ]);

        if (projRes.status === 'fulfilled' && projRes.value) {
          setProject(projRes.value);
        }
        if (gngRes.status === 'fulfilled' && gngRes.value) {
          setGonogo(gngRes.value);
        }
        if (secRes.status === 'fulfilled' && Array.isArray(secRes.value)) {
          setSections(secRes.value);
        }
        if (tmplRes.status === 'fulfilled' && tmplRes.value) {
          setSuggestedTemplate(tmplRes.value);
        }
      } catch (err) {
        console.error('Erreur chargement export page:', err);
      } finally {
        setLoadingData(false);
        setLoadingTemplate(false);
      }
    }

    if (projectId) {
      loadInitialData();
    }
  }, [projectId]);

  async function handleRunGoNoGo() {
    setCalculatingGoNoGo(true);
    setError(null);
    try {
      const res = await api.runGoNoGo(projectId);
      setGonogo(res);
    } catch (err: any) {
      setError(err?.message || t('projects.export.error_gonogo'));
    } finally {
      setCalculatingGoNoGo(false);
    }
  }

  async function handleExport(format: 'docx' | 'pdf') {
    setExporting(format);
    setError(null);
    setResult(null);
    try {
      const job = await api.exportProject(projectId, {
        format,
        include_visuals: includeVisuals,
        include_cover_page: includeCoverPage,
      });
      // /export/compile ne fait que déclencher la tâche Celery et répond immédiatement
      // avec status "processing" -- le .docx/.pdf n'existe pas encore à ce stade
      // (correctif tâche #66, 02/09 : avant ce correctif, le frontend affichait cette
      // réponse "processing" telle quelle comme si l'export était déjà terminé, avec des
      // champs qui de toute façon ne correspondaient à rien de ce que le backend renvoie
      // réellement). On interroge maintenant /export/job/{id} jusqu'à ce que le worker
      // ait fini (ou échoué).
      let attempts = 0;
      let finalJob: ExportJob = job;
      while (finalJob.status !== 'completed' && finalJob.status !== 'failed' && attempts < 30) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        finalJob = await api.getExportJob(job.id);
        attempts += 1;
      }
      setResult(finalJob);
      if (finalJob.status === 'failed') {
        setError(finalJob.error_message || t('projects.export.error_export'));
      }
    } catch (err: any) {
      setError(err?.message || t('projects.export.error_export'));
    } finally {
      setExporting(null);
    }
  }

  async function handleDownloadResult() {
    if (!result?.s3_docx_url) return;
    setDownloadingResult(true);
    try {
      // Le endpoint /export/download/{id} exige un Bearer token (get_current_tenant_user) --
      // une simple balise <a href> ne peut pas le transporter, donc un lien direct
      // échouerait systématiquement en 401. Même correctif que gantt-preview.tsx /
      // organigramme-preview.tsx : on récupère le fichier en tant que blob authentifié
      // avant de déclencher le téléchargement.
      const blobUrl = await fetchAuthenticatedBlobUrl(`${apiBase}${result.s3_docx_url}`);
      const ext = result.format === 'pdf' && result.s3_pdf_url ? 'pdf' : 'docx';
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `Memoire_Technique_${projectId}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
    } catch (err: any) {
      setError(err?.message || t('projects.export.error_export'));
    } finally {
      setDownloadingResult(false);
    }
  }

  async function handleMeaExport(e: React.FormEvent) {
    e.preventDefault();
    setExportingMea(true);
    setMeaError(null);
    setMeaResult(null);

    try {
      const res = await api.exportMeaDossier(projectId, meaCountry, meaLanguage);
      setMeaResult(res);
    } catch (err: any) {
      setMeaError(err?.message || t('projects.export.error_mea'));
    } finally {
      setExportingMea(false);
    }
  }

  const validatedSectionsCount = sections.filter(
    (s) => s.status === 'validated' || (s.content_html && s.content_html.length > 50)
  ).length;

  // Go/No-Go Score color and label helpers
  const score = gonogo ? Math.round(gonogo.score) : null;
  const isGo = gonogo?.recommendation === 'GO';
  const isReserves = gonogo?.recommendation === 'RESERVES' || gonogo?.recommendation === 'RÉSERVES';
  const isNoGo = gonogo?.recommendation === 'NO-GO';

  return (
    <div className="space-y-8 pb-20 max-w-5xl mx-auto font-sans">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link href="/projects" className="hover:text-hl transition-colors flex items-center gap-1">
          <ArrowLeft className="w-3.5 h-3.5" /> {t('projects.export.breadcrumb_projects')}
        </Link>
        <ChevronRight className="w-3 h-3 opacity-40" />
        <Link href={`/projects/${projectId}`} className="hover:text-hl transition-colors truncate max-w-[200px]">
          {project?.title || t('projects.export.default_title')}
        </Link>
        <ChevronRight className="w-3 h-3 opacity-40" />
        <span className="text-hl font-semibold">{t('projects.export.breadcrumb_current')}</span>
      </div>

      {/* Hero Header Card */}
      <div className="relative rounded-2xl p-6 sm:p-8 overflow-hidden bg-card border border-line shadow-xs transition-colors">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="badge-pill">
                {t('projects.export.phase_badge')}
              </span>
              <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-sunken text-slate-600 dark:text-zinc-300 border border-line">
                {project?.reference_code || 'REF-AO'}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-bold text-foreground tracking-tight font-heading">
              {t('projects.export.hero_title')}
            </h1>

            <div className="flex flex-wrap gap-4 sm:gap-6 text-xs text-muted-foreground pt-1">
              <div className="flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-hl" />
                <span>{t('projects.export.client_label', { name: '' })}<strong className="text-slate-900 dark:text-zinc-200">{project?.client_name || t('projects.export.client_fallback')}</strong></span>
              </div>
              {project?.budget_estimate && (
                <div className="flex items-center gap-1.5">
                  <Banknote className="w-3.5 h-3.5 text-positive" />
                  <span>{t('projects.export.budget_prefix')}<strong className="text-slate-900 dark:text-zinc-200 font-mono">{project.budget_estimate.toLocaleString('fr-FR')}</strong> {t('projects.export.budget_suffix')}</span>
                </div>
              )}
              {project?.submission_deadline && (
                <div className="flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-hl" />
                  <span>{t('projects.export.deadline_label', { date: '' })}<strong className="text-slate-900 dark:text-zinc-200">{new Date(project.submission_deadline).toLocaleDateString('fr-FR')}</strong></span>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href={`/projects/${projectId}/editor`}
              className="btn-secondary"
            >
              <span>{t('projects.export.open_editor')}</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </div>

      {/* Grid: Go/No-Go Decision + Sections Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Card 1 & 2: Go/No-Go Decision Matrix (2 Cols) */}
        <div className="lg:col-span-2 rounded-2xl bg-card border border-line p-6 space-y-5 shadow-xs transition-colors">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-hl/10 border border-hl/20 text-hl flex items-center justify-center">
                <TrendingUp className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-foreground font-heading">{t('projects.export.gonogo_title')}</h2>
                <p className="text-[11px] text-muted-foreground">{t('projects.export.gonogo_subtitle')}</p>
              </div>
            </div>

            <button
              type="button"
              onClick={handleRunGoNoGo}
              disabled={calculatingGoNoGo}
              className="btn-secondary !py-1.5 !px-3 !text-xs cursor-pointer"
            >
              <RefreshCw className={`w-3 h-3 ${calculatingGoNoGo ? 'animate-spin text-hl' : ''}`} />
              <span>{gonogo ? t('projects.export.gonogo_recalc') : t('projects.export.gonogo_calc')}</span>
            </button>
          </div>

          {gonogo ? (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-sunken border border-line flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-bold uppercase tracking-wider px-3 py-1 rounded-full border ${
                        isGo
                          ? 'bg-positive/15 text-positive border-positive/40'
                          : isReserves
                          ? 'bg-hl/15 text-hl border-hl/40'
                          : 'bg-danger/15 text-danger border-danger/40'
                      }`}
                    >
                      {gonogo.recommendation === 'GO'
                        ? t('projects.export.gonogo_go')
                        : isReserves
                        ? t('projects.export.gonogo_reserves')
                        : t('projects.export.gonogo_nogo')}
                    </span>
                    <span className="text-xs font-mono font-bold text-slate-800 dark:text-white">
                      {t('projects.export.gonogo_score_label', { score: String(score) })}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-zinc-300 pt-1 leading-relaxed">{gonogo.summary}</p>
                </div>

                {/* Score Circular / Progress Badge */}
                <div className="shrink-0 flex flex-col items-center justify-center p-3 rounded-xl bg-card border border-line text-center min-w-[90px] shadow-xs">
                  <span className={`text-2xl font-bold font-mono ${
                    (score || 0) >= 70 ? 'text-positive' : (score || 0) >= 50 ? 'text-hl' : 'text-danger'
                  }`}>
                    {score}%
                  </span>
                  <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider">{t('projects.export.ai_index')}</span>
                </div>
              </div>

              {/* Factors Highlights */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="p-3.5 rounded-xl bg-sunken border border-line flex items-start gap-2.5">
                  {gonogo.mandatory_criteria_met ? (
                    <Check className="w-4 h-4 text-positive shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-4 h-4 text-danger shrink-0 mt-0.5" />
                  )}
                  <div>
                    <p className="font-bold text-foreground">{t('projects.export.mandatory_criteria')}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {gonogo.mandatory_criteria_met ? t('projects.export.mandatory_criteria_ok') : t('projects.export.mandatory_criteria_ko')}
                    </p>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-sunken border border-line flex items-start gap-2.5">
                  <ShieldCheck className="w-4 h-4 text-hl shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-foreground">{t('projects.export.compliance')}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {gonogo.blocking_issues && gonogo.blocking_issues.length > 0
                        ? t('projects.export.compliance_issues', { count: String(gonogo.blocking_issues.length) })
                        : t('projects.export.compliance_ok')}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-6 rounded-xl bg-slate-50/50 dark:bg-raised/50 border border-dashed border-line text-center space-y-3">
              <Sparkles className="w-8 h-8 text-hl mx-auto animate-pulse" />
              <div>
                <p className="text-xs font-bold text-foreground">{t('projects.export.gonogo_empty_title')}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  {t('projects.export.gonogo_empty_desc')}
                </p>
              </div>
              <button
                type="button"
                onClick={handleRunGoNoGo}
                disabled={calculatingGoNoGo}
                className="btn-primary cursor-pointer"
              >
                {calculatingGoNoGo ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                <span>{t('projects.export.gonogo_empty_btn')}</span>
              </button>
            </div>
          )}
        </div>

        {/* Card 3: Sections & Readiness Summary (1 Col) */}
        <div className="rounded-2xl bg-card border border-line p-6 space-y-4 shadow-xs flex flex-col justify-between transition-colors">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
                <FileCheck className="w-4 h-4 text-positive" />
                <span>{t('projects.export.sections_status_title')}</span>
              </h2>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-positive/10 text-positive border border-positive/20">
                {t('projects.export.sections_ready_count', { n: String(validatedSectionsCount) })}
              </span>
            </div>

            <div className="space-y-2 pt-1">
              {MANDATORY_SECTIONS.map((sec) => {
                const found = sections.find((s) => s.section_key === sec.key);
                const isReady = found && (found.status === 'validated' || (found.content_html && found.content_html.length > 50));
                return (
                  <div
                    key={sec.key}
                    className="flex items-center justify-between p-2.5 rounded-xl bg-sunken border border-line text-xs"
                  >
                    <span className="text-foreground font-medium truncate text-[11px] max-w-[190px]">
                      {sec.title}
                    </span>
                    {isReady ? (
                      <span className="flex items-center gap-1 text-[10px] font-bold text-positive shrink-0">
                        <CheckCircle2 className="w-3.5 h-3.5" /> {t('projects.export.section_ready')}
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[10px] font-bold text-muted-foreground shrink-0">
                        <Clock className="w-3 h-3" /> {t('projects.export.section_pending')}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <Link
            href={`/projects/${projectId}/editor`}
            className="w-full text-center py-2.5 rounded-xl bg-sunken hover:bg-line/40 text-hl text-xs font-bold border border-line transition-colors block"
          >
            {t('projects.export.complete_in_editor')}
          </Link>
        </div>
      </div>

      {/* SECTION: TEMPLATE SELECTION & SOVEREIGN EXPORT */}
      <div className="rounded-2xl bg-card border border-line p-6 sm:p-8 space-y-6 shadow-xs transition-colors">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-hl/10 border border-hl/20 text-hl flex items-center justify-center font-bold">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-foreground font-heading">{t('projects.export.template_section_title')}</h2>
              <p className="text-xs text-muted-foreground">
                {t('projects.export.template_section_subtitle')}
              </p>
            </div>
          </div>
          <span className="text-[11px] font-mono text-muted-foreground px-3 py-1 rounded-full bg-sunken border border-line">
            python-docx &amp; LibreOffice (PDF)
          </span>
        </div>

        {/* Suggested Template Box */}
        {loadingTemplate ? (
          <div className="p-4 rounded-xl bg-sunken border border-line text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-hl" />
            <span>{t('projects.export.template_loading')}</span>
          </div>
        ) : suggestedTemplate?.has_template ? (
          <div className="p-4 rounded-xl bg-hl/8 border border-hl/20 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-hl animate-pulse" />
                <span className="text-xs font-bold text-foreground">{t('projects.export.template_suggested_label')}</span>
                <span className="badge-pill font-mono">
                  {suggestedTemplate.name}
                </span>
              </div>
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                {suggestedTemplate.source_type === 'export_template' ? t('projects.export.template_source_official') : t('projects.export.template_source_history')}
              </span>
            </div>
            <p className="text-xs text-foreground">{suggestedTemplate.description}</p>
          </div>
        ) : null}

        {/* La "grille de styles" précédemment ici (Standard/HQE/Synthèse) a été retirée le
            02/09 (tâche #66) : le backend (compile_technical_memo) ne lisait jamais le champ
            `template` envoyé -- il n'a jamais existé côté schéma (ExportDocumentRequest), donc
            Pydantic le supprimait silencieusement. Le document utilise toujours l'unique
            template Word actif du client (ExportTemplate.is_default, affiché ci-dessus quand
            il existe) : il n'y a jamais eu de choix réel à faire ici. */}
        {!suggestedTemplate?.has_template && !loadingTemplate && (
          <p className="text-xs text-muted-foreground">
            {t('projects.export.template_none_note')}
          </p>
        )}

        {/* Options Toggles */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex items-center justify-between p-4 rounded-xl bg-sunken border border-line">
            <div>
              <p className="text-xs font-bold text-slate-900 dark:text-zinc-200">{t('projects.export.toggle_visuals_label')}</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">{t('projects.export.toggle_visuals_desc')}</p>
            </div>
            <button
              type="button"
              onClick={() => setIncludeVisuals(!includeVisuals)}
              className={`w-11 h-6 rounded-full relative transition-colors cursor-pointer ${includeVisuals ? 'bg-hl' : 'bg-slate-300 dark:bg-slate-700'}`}
            >
              <span className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${includeVisuals ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>

          <div className="flex items-center justify-between p-4 rounded-xl bg-sunken border border-line">
            <div>
              <p className="text-xs font-bold text-slate-900 dark:text-zinc-200">{t('projects.export.toggle_cover_label')}</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">{t('projects.export.toggle_cover_desc')}</p>
            </div>
            <button
              type="button"
              onClick={() => setIncludeCoverPage(!includeCoverPage)}
              className={`w-11 h-6 rounded-full relative transition-colors cursor-pointer ${includeCoverPage ? 'bg-hl' : 'bg-slate-300 dark:bg-slate-700'}`}
            >
              <span className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${includeCoverPage ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>
        </div>

        {/* Export Buttons */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
          {/* Word Export Button */}
          <button
            type="button"
            onClick={() => handleExport('docx')}
            disabled={!!exporting}
            className="group relative overflow-hidden flex flex-col items-center gap-3 p-6 rounded-2xl bg-hl hover:bg-hl-strong text-hl-contrast transition-all disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer shadow-xs"
          >
            <div className="w-12 h-12 rounded-xl bg-white/15 border border-white/25 flex items-center justify-center group-hover:scale-105 transition-transform">
              {exporting === 'docx' ? (
                <Loader2 className="w-6 h-6 text-white animate-spin" />
              ) : (
                <FileText className="w-6 h-6 text-white" />
              )}
            </div>
            <div className="text-center">
              <p className="text-sm font-bold text-white">{t('projects.export.docx_title')}</p>
              <p className="text-xs text-white/80 mt-0.5">{t('projects.export.docx_desc')}</p>
            </div>
            {exporting === 'docx' && (
              <p className="text-xs text-white flex items-center gap-1.5 font-bold">
                <Clock className="w-3.5 h-3.5 animate-spin" /> {t('projects.export.docx_loading')}
              </p>
            )}
          </button>

          {/* PDF Export Button */}
          <button
            type="button"
            onClick={() => handleExport('pdf')}
            disabled={!!exporting}
            className="group relative overflow-hidden flex flex-col items-center gap-3 p-6 rounded-2xl bg-card hover:bg-sunken text-foreground border border-line transition-all disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer shadow-xs"
          >
            <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-card border border-line flex items-center justify-center group-hover:scale-105 transition-transform">
              {exporting === 'pdf' ? (
                <Loader2 className="w-6 h-6 text-hl animate-spin" />
              ) : (
                <FileDown className="w-6 h-6 text-hl" />
              )}
            </div>
            <div className="text-center">
              <p className="text-sm font-bold text-foreground">{t('projects.export.pdf_title')}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{t('projects.export.pdf_desc')}</p>
            </div>
            {exporting === 'pdf' && (
              <p className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
                <Clock className="w-3.5 h-3.5 animate-spin" /> {t('projects.export.pdf_loading')}
              </p>
            )}
          </button>
        </div>

        <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
          <Globe className="w-3.5 h-3.5 shrink-0" />
          {t('projects.export.pointer_to_mea')}
        </p>
      </div>

      {/* Error Notification */}
      {error && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-danger/10 border border-danger/30 text-danger text-xs">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-danger" />
          <div>
            <p className="font-bold">{t('projects.export.error_title')}</p>
            <p className="text-[11px] text-danger mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Success / Progress / Failure Result Card (correctif tâche #66, 02/09 : les champs
          lus ici ne correspondaient auparavant à rien de ce que le backend renvoie réellement,
          voir api.ts::exportProject) */}
      {result && (
        <div className={`p-6 rounded-2xl border space-y-4 animate-in fade-in ${
          result.status === 'failed'
            ? 'bg-danger/10 border-danger/30'
            : 'bg-positive/10 border-positive/30'
        }`}>
          {result.status === 'completed' ? (
            <div className="flex items-center gap-2 text-positive font-heading">
              <CheckCircle2 className="w-5 h-5 text-positive" />
              <p className="text-sm font-bold">{t('projects.export.result_success')}</p>
            </div>
          ) : result.status === 'failed' ? (
            <div className="flex items-center gap-2 text-danger font-heading">
              <AlertTriangle className="w-5 h-5 text-danger" />
              <p className="text-sm font-bold">{t('projects.export.result_failed')}</p>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-positive font-heading">
              <Loader2 className="w-5 h-5 text-positive animate-spin" />
              <p className="text-sm font-bold">{t('projects.export.result_generating')}</p>
            </div>
          )}

          {result.status === 'completed' && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-card border border-line">
                <p className="text-muted-foreground">{t('projects.export.result_format')}</p>
                <p className="text-slate-900 dark:text-zinc-200 font-semibold mt-0.5 font-mono text-[11px] uppercase">
                  {result.format === 'pdf' && result.s3_pdf_url ? 'PDF' : 'DOCX'}
                </p>
              </div>
              {result.file_size_bytes > 0 && (
                <div className="p-3 rounded-xl bg-card border border-line">
                  <p className="text-muted-foreground">{t('projects.export.result_size')}</p>
                  <p className="text-slate-900 dark:text-zinc-200 font-semibold font-mono mt-0.5">{Math.round(result.file_size_bytes / 1024)} {t('projects.export.result_size_unit')}</p>
                </div>
              )}
            </div>
          )}

          {result.status === 'completed' && result.format === 'pdf' && !result.s3_pdf_url && (
            <p className="text-[11px] text-corten">{result.error_message || t('projects.export.pdf_fallback_note')}</p>
          )}
          {result.status === 'failed' && result.error_message && (
            <p className="text-[11px] text-danger">{result.error_message}</p>
          )}

          {result.status === 'completed' && (
            <div className="flex flex-wrap gap-3 pt-1">
              <button
                type="button"
                onClick={handleDownloadResult}
                disabled={downloadingResult}
                className="btn-primary cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {downloadingResult ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                <span>{result.format === 'pdf' && result.s3_pdf_url ? t('projects.export.download_pdf') : t('projects.export.download_docx')}</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* SECTION: MEA & INTERNATIONAL REGIONAL EXPORT */}
      <div className="card-modern p-6 sm:p-8 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/60 dark:border-zinc-800/40 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-hl/10 border border-hl/20 text-hl flex items-center justify-center font-bold">
              <Globe className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-[15px] font-bold text-foreground font-heading">{t('projects.export.mea_title')}</h2>
              <p className="text-[12px] text-muted-foreground">
                {t('projects.export.mea_subtitle')}
              </p>
            </div>
          </div>
          <span className="badge-pill text-[10px] bg-hl/10 text-hl border border-hl/20">
            {t('projects.export.mea_rtl_badge')}
          </span>
        </div>

        <p className="text-[12px] text-muted-foreground">
          {t('projects.export.mea_replaces_note')}
        </p>

        <form onSubmit={handleMeaExport} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-[12px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">{t('projects.export.mea_country_label')}</label>
              <select
                value={meaCountry}
                onChange={(e: any) => setMeaCountry(e.target.value)}
                className="input-field cursor-pointer"
              >
                <option value="SA">{t('projects.export.mea_country_sa')}</option>
                <option value="QA">{t('projects.export.mea_country_qa')}</option>
                <option value="AE">{t('projects.export.mea_country_ae')}</option>
                <option value="LB">{t('projects.export.mea_country_lb')}</option>
              </select>
            </div>

            <div>
              <label className="block text-[12px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">{t('projects.export.mea_lang_label')}</label>
              <select
                value={meaLanguage}
                onChange={(e: any) => setMeaLanguage(e.target.value)}
                className="input-field cursor-pointer"
              >
                <option value="fr">{t('projects.export.mea_lang_fr')}</option>
                <option value="en">{t('projects.export.mea_lang_en')}</option>
                <option value="ar">{t('projects.export.mea_lang_ar')}</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={exportingMea}
              className="btn-primary"
            >
              {exportingMea ? <Loader2 className="w-4 h-4 animate-spin" /> : <Globe className="w-4 h-4" />}
              <span>{t('projects.export.mea_submit')}</span>
            </button>
          </div>
        </form>

        {meaError && (
          <div className="p-3.5 rounded-lg bg-danger/8 border border-danger/20 text-danger text-[12px]">
            {meaError}
          </div>
        )}

        {meaResult && (
          <div className="p-4 rounded-xl bg-positive/10 border border-positive/30 text-positive text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-positive shrink-0" />
            <span>{t('projects.export.mea_result_success', { filename: meaResult.filename })}</span>
          </div>
        )}
      </div>
    </div>
  );
}
