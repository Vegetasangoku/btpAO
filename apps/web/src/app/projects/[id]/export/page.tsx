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
import { api } from '@/lib/api';
import { Project, SuggestedTemplate, GoNoGoAnalysis, GeneratedSection } from '@/lib/types';

interface ExportResult {
  docx_url?: string;
  pdf_url?: string;
  filename?: string;
  file_size_kb?: number;
  sections_count?: number;
}

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

  // Project & Context Data
  const [project, setProject] = useState<Project | null>(null);
  const [gonogo, setGonogo] = useState<GoNoGoAnalysis | null>(null);
  const [sections, setSections] = useState<GeneratedSection[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [calculatingGoNoGo, setCalculatingGoNoGo] = useState(false);

  // Standard Export States
  const [exporting, setExporting] = useState<'docx' | 'pdf' | null>(null);
  const [result, setResult] = useState<ExportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [includeVisuals, setIncludeVisuals] = useState(true);
  const [includeCoverPage, setIncludeCoverPage] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState('suggested_history');

  // Suggested Template State
  const [suggestedTemplate, setSuggestedTemplate] = useState<SuggestedTemplate | null>(null);
  const [loadingTemplate, setLoadingTemplate] = useState(true);

  // MEA / International Regional Export State
  const [meaCountry, setMeaCountry] = useState<'SA' | 'QA' | 'AE' | 'LB' | 'FR'>('SA');
  const [meaLanguage, setMeaLanguage] = useState<'fr' | 'en' | 'ar'>('fr');
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
          if (tmplRes.value.has_template) {
            setSelectedTemplate('suggested_history');
          } else {
            setSelectedTemplate('standard_btp');
          }
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
      setError(err?.message || "Erreur lors du calcul de la matrice Go/No-Go.");
    } finally {
      setCalculatingGoNoGo(false);
    }
  }

  async function handleExport(format: 'docx' | 'pdf') {
    setExporting(format);
    setError(null);
    setResult(null);
    try {
      const data = await api.exportProject(projectId, {
        format,
        include_visuals: includeVisuals,
        template: selectedTemplate === 'suggested_history' ? 'standard_btp' : selectedTemplate,
      });
      setResult(data);
    } catch (err: any) {
      setError(err?.message || "Erreur lors de l'export. Vérifiez que les sections nécessaires ont été rédigées.");
    } finally {
      setExporting(null);
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
      setMeaError(err?.message || "Erreur lors de l'export du dossier MEA.");
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
    <div className="space-y-8 pb-20 max-w-5xl mx-auto">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        <Link href="/projects" className="hover:text-amber-600 dark:hover:text-amber-400 transition-colors flex items-center gap-1">
          <ArrowLeft className="w-3.5 h-3.5" /> Projets
        </Link>
        <ChevronRight className="w-3 h-3 text-slate-400 dark:text-slate-600" />
        <Link href={`/projects/${projectId}`} className="hover:text-amber-600 dark:hover:text-amber-400 transition-colors truncate max-w-[200px]">
          {project?.title || 'Dossier Projet'}
        </Link>
        <ChevronRight className="w-3 h-3 text-slate-400 dark:text-slate-600" />
        <span className="text-amber-600 dark:text-amber-400 font-semibold">Export & Livrables</span>
      </div>

      {/* Hero Header Card */}
      <div className="relative rounded-3xl p-6 sm:p-8 overflow-hidden bg-white dark:bg-gradient-to-br dark:from-[#0F1422] dark:via-[#131B2E] dark:to-amber-950/30 border border-slate-200 dark:border-amber-500/20 shadow-md dark:shadow-2xl transition-colors">
        <div className="absolute -right-16 -bottom-16 w-72 h-72 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-extrabold uppercase tracking-widest px-2.5 py-0.5 rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                Phase Finale • Livrables Prêts à Déposer
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                {project?.reference_code || 'REF-AO'}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-white tracking-tight">
              Centre de Compilation & Export Officiel
            </h1>

            <div className="flex flex-wrap gap-4 sm:gap-6 text-xs text-slate-600 dark:text-slate-400 pt-1">
              <div className="flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-amber-500" />
                <span>Client : <strong className="text-slate-900 dark:text-slate-200">{project?.client_name || 'Maître d’Ouvrage'}</strong></span>
              </div>
              {project?.budget_estimate && (
                <div className="flex items-center gap-1.5">
                  <Banknote className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Budget : <strong className="text-slate-900 dark:text-slate-200 font-mono">{project.budget_estimate.toLocaleString('fr-FR')} € HT</strong></span>
                </div>
              )}
              {project?.submission_deadline && (
                <div className="flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-sky-500" />
                  <span>Date limite : <strong className="text-slate-900 dark:text-slate-200">{new Date(project.submission_deadline).toLocaleDateString('fr-FR')}</strong></span>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href={`/projects/${projectId}/editor`}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-bold border border-slate-200 dark:border-slate-700 transition-colors shadow-sm"
            >
              <span>Ouvrir l’Éditeur IA</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </div>

      {/* Grid: Go/No-Go Decision + Sections Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Card 1 & 2: Go/No-Go Decision Matrix (2 Cols) */}
        <div className="lg:col-span-2 rounded-3xl bg-white dark:bg-[#0F1422] border border-slate-200 dark:border-[#1E293F] p-6 space-y-5 shadow-sm dark:shadow-xl transition-colors">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 flex items-center justify-center">
                <TrendingUp className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">Matrice Décisionnelle Go / No-Go</h2>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">Évaluation stratégique de faisabilité et d'adéquation au DCE</p>
              </div>
            </div>

            <button
              type="button"
              onClick={handleRunGoNoGo}
              disabled={calculatingGoNoGo}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-[11px] font-bold border border-slate-200 dark:border-slate-700 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 ${calculatingGoNoGo ? 'animate-spin text-amber-500' : ''}`} />
              <span>{gonogo ? 'Recalculer' : 'Calculer le score'}</span>
            </button>
          </div>

          {gonogo ? (
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-black uppercase tracking-wider px-3 py-1 rounded-full border ${
                        isGo
                          ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/40'
                          : isReserves
                          ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/40'
                          : 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/40'
                      }`}
                    >
                      {gonogo.recommendation === 'GO'
                        ? '✅ DÉCISION : GO CONFIRMÉ'
                        : isReserves
                        ? '⚠️ DÉCISION : GO SOUS RÉSERVES'
                        : '🛑 DÉCISION : NO-GO RECOMMANDÉ'}
                    </span>
                    <span className="text-xs font-mono font-bold text-slate-800 dark:text-white">
                      Score global : {score}/100
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-300 pt-1 leading-relaxed">{gonogo.summary}</p>
                </div>

                {/* Score Circular / Progress Badge */}
                <div className="shrink-0 flex flex-col items-center justify-center p-3 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-center min-w-[90px] shadow-sm">
                  <span className={`text-2xl font-black font-mono ${
                    (score || 0) >= 70 ? 'text-emerald-500' : (score || 0) >= 50 ? 'text-amber-500' : 'text-rose-500'
                  }`}>
                    {score}%
                  </span>
                  <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Indice IA</span>
                </div>
              </div>

              {/* Factors Highlights */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="p-3.5 rounded-xl bg-slate-50/80 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 flex items-start gap-2.5">
                  {gonogo.mandatory_criteria_met ? (
                    <Check className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                  )}
                  <div>
                    <p className="font-bold text-slate-900 dark:text-white">Critères éliminatoires</p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      {gonogo.mandatory_criteria_met ? '100% des critères minimaux DCE validés' : 'Des critères obligatoires non satisfaits'}
                    </p>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-50/80 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 flex items-start gap-2.5">
                  <ShieldCheck className="w-4 h-4 text-sky-500 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold text-slate-900 dark:text-white">Conformité Entreprise</p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      {gonogo.blocking_issues && gonogo.blocking_issues.length > 0
                        ? `${gonogo.blocking_issues.length} points de vigilance détectés`
                        : 'Aucun point de blocage réglementaire'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-6 rounded-2xl bg-slate-50 dark:bg-slate-950/50 border border-dashed border-slate-200 dark:border-slate-800 text-center space-y-3">
              <Sparkles className="w-8 h-8 text-amber-500/60 mx-auto animate-pulse" />
              <div>
                <p className="text-xs font-bold text-slate-900 dark:text-white">Analyse Go/No-Go non encore calculée</p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                  Évaluez l'opportunité de répondre à ce marché en croisant les exigences du DCE avec vos moyens disponibles.
                </p>
              </div>
              <button
                type="button"
                onClick={handleRunGoNoGo}
                disabled={calculatingGoNoGo}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-extrabold shadow-lg shadow-amber-500/20 transition-all disabled:opacity-50 cursor-pointer"
              >
                {calculatingGoNoGo ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                <span>Calculer l'analyse Go / No-Go</span>
              </button>
            </div>
          )}
        </div>

        {/* Card 3: Sections & Readiness Summary (1 Col) */}
        <div className="rounded-3xl bg-white dark:bg-[#0F1422] border border-slate-200 dark:border-[#1E293F] p-6 space-y-4 shadow-sm dark:shadow-xl flex flex-col justify-between transition-colors">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <FileCheck className="w-4 h-4 text-emerald-500" />
                <span>État des Sections</span>
              </h2>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                {validatedSectionsCount} / 5 Prêtes
              </span>
            </div>

            <div className="space-y-2 pt-1">
              {MANDATORY_SECTIONS.map((sec) => {
                const found = sections.find((s) => s.section_key === sec.key);
                const isReady = found && (found.status === 'validated' || (found.content_html && found.content_html.length > 50));
                return (
                  <div
                    key={sec.key}
                    className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 text-xs"
                  >
                    <span className="text-slate-700 dark:text-slate-300 font-medium truncate text-[11px] max-w-[190px]">
                      {sec.title}
                    </span>
                    {isReady ? (
                      <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-600 dark:text-emerald-400 shrink-0">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Prêt
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[10px] font-bold text-slate-400 shrink-0">
                        <Clock className="w-3 h-3" /> À valider
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <Link
            href={`/projects/${projectId}/editor`}
            className="w-full text-center py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-amber-600 dark:text-amber-400 text-xs font-bold border border-slate-200 dark:border-slate-700 transition-colors block"
          >
            Compléter les chapitres dans l'Éditeur →
          </Link>
        </div>
      </div>

      {/* SECTION: TEMPLATE SELECTION & SOVEREIGN EXPORT */}
      <div className="rounded-3xl bg-white dark:bg-[#0F1422] border border-slate-200 dark:border-[#1E293F] p-6 sm:p-8 space-y-6 shadow-sm dark:shadow-2xl transition-colors">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 flex items-center justify-center font-bold">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white">Génération Word (.docx) & PDF Haute Définition</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Sélectionnez le gabarit de charte graphique et compilez l'ensemble du mémoire technique.
              </p>
            </div>
          </div>
          <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 px-3 py-1 rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            Jinja2 / docxtpl & LibreOffice 7.x
          </span>
        </div>

        {/* Suggested Template Box */}
        {loadingTemplate ? (
          <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
            <span>Analyse de l'historique de votre entreprise...</span>
          </div>
        ) : suggestedTemplate?.has_template ? (
          <div className="p-4 rounded-2xl bg-amber-50/60 dark:bg-gradient-to-r dark:from-amber-950/40 dark:via-slate-900/90 dark:to-slate-950 border border-amber-200 dark:border-amber-500/30 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-600 dark:text-amber-400 animate-pulse" />
                <span className="text-xs font-bold text-slate-900 dark:text-white">Modèle Graphique Déduit :</span>
                <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-800 dark:text-amber-300 border border-amber-500/40 font-mono">
                  {suggestedTemplate.name}
                </span>
              </div>
              <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                {suggestedTemplate.source_type === 'export_template' ? 'Gabarit Officiel Entreprise' : 'Historique des mémoires'}
              </span>
            </div>
            <p className="text-xs text-slate-700 dark:text-slate-300">{suggestedTemplate.description}</p>
          </div>
        ) : null}

        {/* Template Choice Grid */}
        <div className="space-y-3">
          <label className="block text-xs font-bold text-slate-800 dark:text-slate-200">Choisir le gabarit de mise en page :</label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {suggestedTemplate?.has_template && (
              <button
                type="button"
                onClick={() => setSelectedTemplate('suggested_history')}
                className={`p-4 rounded-2xl text-left border transition-all cursor-pointer ${
                  selectedTemplate === 'suggested_history'
                    ? 'border-amber-500 bg-amber-500/10 text-amber-800 dark:text-amber-300 shadow-md ring-1 ring-amber-500/50'
                    : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 text-slate-600 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-700'
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                  <p className="text-xs font-bold text-slate-900 dark:text-white">Modèle Déduit Entreprise</p>
                </div>
                <p className="text-[11px] mt-1 text-slate-500 dark:text-slate-400 line-clamp-2">{suggestedTemplate.name}</p>
              </button>
            )}

            {[
              { id: 'standard_btp', label: 'Standard BTP Gros Œuvre', desc: 'Charte neutre professionnelle pour marchés publics & privés' },
              { id: 'hqe_certified', label: 'HQE / Bâtiment Durable', desc: 'Mise en avant prioritaire des critères RSE, carbone & SOGED' },
              { id: 'compact_summary', label: 'Synthèse Exécutive Compacte', desc: 'Format allégé 15-25 pages avec fiches résumées par lot' },
            ].map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setSelectedTemplate(t.id)}
                className={`p-4 rounded-2xl text-left border transition-all cursor-pointer ${
                  selectedTemplate === t.id
                    ? 'border-amber-500 bg-amber-500/10 text-amber-800 dark:text-amber-300 shadow-md ring-1 ring-amber-500/50'
                    : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 text-slate-600 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-700'
                }`}
              >
                <p className="text-xs font-bold text-slate-900 dark:text-white">{t.label}</p>
                <p className="text-[11px] mt-1 text-slate-500 dark:text-slate-400">{t.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Options Toggles */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex items-center justify-between p-4 rounded-2xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
            <div>
              <p className="text-xs font-bold text-slate-900 dark:text-slate-200">Injecter les graphiques HD (Gantt & Organigramme)</p>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">Rendu vectoriel 300 DPI dans le corps du document</p>
            </div>
            <button
              type="button"
              onClick={() => setIncludeVisuals(!includeVisuals)}
              className={`w-11 h-6 rounded-full relative transition-colors cursor-pointer ${includeVisuals ? 'bg-amber-500' : 'bg-slate-300 dark:bg-slate-700'}`}
            >
              <span className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${includeVisuals ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>

          <div className="flex items-center justify-between p-4 rounded-2xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
            <div>
              <p className="text-xs font-bold text-slate-900 dark:text-slate-200">Page de garde & Sommaire automatique</p>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">En-tête réglementaire, logo entreprise et pagination</p>
            </div>
            <button
              type="button"
              onClick={() => setIncludeCoverPage(!includeCoverPage)}
              className={`w-11 h-6 rounded-full relative transition-colors cursor-pointer ${includeCoverPage ? 'bg-amber-500' : 'bg-slate-300 dark:bg-slate-700'}`}
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
            className="group relative overflow-hidden flex flex-col items-center gap-3 p-6 rounded-2xl bg-amber-500 hover:bg-amber-400 dark:bg-gradient-to-br dark:from-amber-500/20 dark:via-slate-900 dark:to-slate-950 border border-amber-600 dark:border-amber-500/40 hover:dark:border-amber-400 transition-all disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer shadow-lg shadow-amber-500/20"
          >
            <div className="w-12 h-12 rounded-2xl bg-white/20 dark:bg-amber-500/20 border border-white/30 dark:border-amber-500/30 flex items-center justify-center group-hover:scale-110 transition-transform">
              {exporting === 'docx' ? (
                <Loader2 className="w-6 h-6 text-slate-950 dark:text-amber-400 animate-spin" />
              ) : (
                <FileText className="w-6 h-6 text-slate-950 dark:text-amber-400" />
              )}
            </div>
            <div className="text-center">
              <p className="text-sm font-black text-slate-950 dark:text-white">Générer le Mémoire Word (.docx)</p>
              <p className="text-xs text-slate-800 dark:text-slate-400 mt-0.5">Document entièrement éditable avec styles officiels</p>
            </div>
            {exporting === 'docx' && (
              <p className="text-xs text-slate-950 dark:text-amber-400 flex items-center gap-1.5 font-bold">
                <Clock className="w-3.5 h-3.5 animate-spin" /> Compilation docxtpl en cours (≈5-12 sec)…
              </p>
            )}
          </button>

          {/* PDF Export Button */}
          <button
            type="button"
            onClick={() => handleExport('pdf')}
            disabled={!!exporting}
            className="group relative overflow-hidden flex flex-col items-center gap-3 p-6 rounded-2xl bg-slate-900 hover:bg-slate-800 dark:bg-gradient-to-br dark:from-slate-800/60 dark:via-slate-900 dark:to-slate-950 border border-slate-700 hover:border-slate-500 transition-all disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer shadow-lg"
          >
            <div className="w-12 h-12 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center group-hover:scale-110 transition-transform">
              {exporting === 'pdf' ? (
                <Loader2 className="w-6 h-6 text-slate-300 animate-spin" />
              ) : (
                <FileDown className="w-6 h-6 text-slate-300" />
              )}
            </div>
            <div className="text-center">
              <p className="text-sm font-bold text-white">Générer le Mémoire PDF Officiel</p>
              <p className="text-xs text-slate-400 mt-0.5">Rendu vectoriel LibreOffice — Prêt pour dépôt</p>
            </div>
            {exporting === 'pdf' && (
              <p className="text-xs text-slate-300 flex items-center gap-1.5 font-medium">
                <Clock className="w-3.5 h-3.5 animate-spin" /> Rendu headless PDF en cours (≈15-25 sec)…
              </p>
            )}
          </button>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="flex items-start gap-3 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-700 dark:text-rose-300 text-xs">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-rose-500" />
            <div>
              <p className="font-bold">Erreur de compilation</p>
              <p className="text-[11px] text-rose-600 dark:text-rose-200 mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {/* Success Result Download Card */}
        {result && (
          <div className="p-6 rounded-2xl bg-emerald-50 dark:bg-gradient-to-r dark:from-emerald-950/40 dark:via-slate-900 dark:to-slate-950 border border-emerald-300 dark:border-emerald-500/40 space-y-4 animate-in fade-in">
            <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              <p className="text-sm font-bold">Votre livrable a été compilé avec succès !</p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
              {result.filename && (
                <div className="p-3 rounded-xl bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800">
                  <p className="text-slate-500 dark:text-slate-400">Nom du fichier</p>
                  <p className="text-slate-900 dark:text-slate-200 font-semibold mt-0.5 truncate font-mono text-[11px]">{result.filename}</p>
                </div>
              )}
              {result.file_size_kb && (
                <div className="p-3 rounded-xl bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800">
                  <p className="text-slate-500 dark:text-slate-400">Taille du livrable</p>
                  <p className="text-slate-900 dark:text-slate-200 font-semibold font-mono mt-0.5">{result.file_size_kb} Ko</p>
                </div>
              )}
              {result.sections_count && (
                <div className="p-3 rounded-xl bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800">
                  <p className="text-slate-500 dark:text-slate-400">Sections intégrées</p>
                  <p className="text-slate-900 dark:text-slate-200 font-semibold font-mono mt-0.5">{result.sections_count} / 5</p>
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-3 pt-1">
              {result.docx_url && (
                <a
                  href={result.docx_url}
                  download
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black transition-all shadow-lg shadow-amber-500/20"
                >
                  <Download className="w-4 h-4" />
                  <span>Télécharger le Word (.docx)</span>
                </a>
              )}
              {result.pdf_url && (
                <a
                  href={result.pdf_url}
                  download
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-all border border-slate-700"
                >
                  <Download className="w-4 h-4" />
                  <span>Télécharger le PDF</span>
                </a>
              )}
            </div>
          </div>
        )}
      </div>

      {/* SECTION: MEA & INTERNATIONAL REGIONAL EXPORT */}
      <div className="rounded-3xl bg-white dark:bg-[#0F1422] border border-slate-200 dark:border-[#1E293F] p-6 sm:p-8 space-y-6 shadow-sm dark:shadow-2xl transition-colors">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-sky-500/10 border border-sky-500/30 text-sky-600 dark:text-sky-400 flex items-center justify-center font-bold">
              <Globe className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white">Export Régional International (Moyen-Orient & Golfe)</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Générez des mémoires adaptés aux juridictions et normes du CCG (Arabie Saoudite, Qatar, EAU, Liban) avec support natif de l'arabe RTL.
              </p>
            </div>
          </div>
          <span className="text-[11px] font-mono text-sky-600 dark:text-sky-400 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/20">
            OpenXML w:bidi & w:rtl
          </span>
        </div>

        <form onSubmit={handleMeaExport} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">Juridiction & Normes Régionales</label>
              <select
                value={meaCountry}
                onChange={(e: any) => setMeaCountry(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white text-xs focus:border-amber-500 focus:outline-none"
              >
                <option value="SA">🇸🇦 Arabie Saoudite (SBC / SASO / Vision 2030)</option>
                <option value="QA">🇶🇦 Qatar (QCS 2018 / Ashghal)</option>
                <option value="AE">🇦🇪 Émirats Arabes Unis (Abu Dhabi / Dubai Code)</option>
                <option value="LB">🇱🇧 Liban (CDR / Libnor)</option>
                <option value="FR">🇫🇷 France (CCAG Travaux / DTU / Eurocodes)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">Langue du Mémoire Technique</label>
              <select
                value={meaLanguage}
                onChange={(e: any) => setMeaLanguage(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white text-xs focus:border-amber-500 focus:outline-none"
              >
                <option value="fr">🇫🇷 Français (Format standard européen)</option>
                <option value="en">🇬🇧 Anglais (FIDIC International standard)</option>
                <option value="ar">🇸🇦 Arabe (العربية — Format bidi RTL natif)</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={exportingMea}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold transition-all shadow-lg shadow-sky-900/30 disabled:opacity-50 cursor-pointer"
            >
              {exportingMea ? <Loader2 className="w-4 h-4 animate-spin" /> : <Globe className="w-4 h-4" />}
              <span>Générer le Dossier International</span>
            </button>
          </div>
        </form>

        {meaError && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-300 text-xs">
            {meaError}
          </div>
        )}

        {meaResult && (
          <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-300 dark:border-emerald-500/30 text-emerald-800 dark:text-emerald-300 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              <span>Dossier {meaResult.filename} généré avec succès.</span>
            </div>
            {meaResult.docx_url && (
              <a
                href={meaResult.docx_url}
                download
                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold"
              >
                Télécharger
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
