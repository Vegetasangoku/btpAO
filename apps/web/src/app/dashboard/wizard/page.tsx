'use client';

import React, { useState, useRef, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  UploadCloud,
  FileCheck2,
  Edit3,
  FileSpreadsheet,
  Download,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  Loader2,
  Sparkles,
  FileText,
  Trash2,
  Info,
} from 'lucide-react';
import { api, fetchAuthenticatedBlobUrl } from '@/lib/api';
import { Project, GeneratedSection, SuggestedTemplate } from '@/lib/types';
import { TiptapEditor } from '@/components/editor/tiptap-editor';
import { useTranslation } from '@/components/i18n-provider';

function ResponseWizardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const existingProjectId = searchParams.get('projectId');
  const { t, language } = useTranslation();

  const [currentStep, setCurrentStep] = useState<number>(1);
  const [project, setProject] = useState<Project | null>(null);

  // Step 1: Upload state
  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step 2: Extracted Information (Pre-filled by AI / OCR)
  const [title, setTitle] = useState('');
  const [clientName, setClientName] = useState('');
  const [referenceCode, setReferenceCode] = useState('');
  const [location, setLocation] = useState('');
  const [submissionDeadline, setSubmissionDeadline] = useState('');
  const [estimatedBudget, setEstimatedBudget] = useState('');
  const [strategicDirectives, setStrategicDirectives] = useState('');
  const [isSavingInfo, setIsSavingInfo] = useState(false);

  // Step 3: AI Sections
  const [sections, setSections] = useState<GeneratedSection[]>([]);
  const [activeSectionIdx, setActiveSectionIdx] = useState(0);
  const [isGeneratingSections, setIsGeneratingSections] = useState(false);

  // Step 4: Administrative Forms
  const [adminForms, setAdminForms] = useState({
    dc1_required: true,
    dc2_required: true,
    dume_required: false,
    mea_country: 'FR',
    notes_admin: 'Toutes les attestations fiscales et sociales à jour.',
  });

  // Step 5: Export & Finalize
  const [suggestedTemplate, setSuggestedTemplate] = useState<SuggestedTemplate | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<'fr' | 'en' | 'ar'>('fr');
  const [isExporting, setIsExporting] = useState(false);
  const [exportSuccessMsg, setExportSuccessMsg] = useState<string | null>(null);

  // Sync selectedLanguage with global language initially
  useEffect(() => {
    if (language) {
      setSelectedLanguage(language);
    }
  }, [language]);

  // Load existing project if provided
  useEffect(() => {
    if (existingProjectId) {
      api.getProject(existingProjectId).then((p) => {
        setProject(p);
        setTitle(p.title || '');
        setClientName(p.client_name || '');
        setReferenceCode(p.reference_code || '');
        setLocation(p.location || '');
        setStrategicDirectives(p.strategic_directives || '');
        if (p.output_language) {
          setSelectedLanguage(p.output_language as 'fr' | 'en' | 'ar');
        }
        if (p.submission_deadline) {
          setSubmissionDeadline(p.submission_deadline.substring(0, 10));
        }
        if (p.estimated_budget) {
          setEstimatedBudget(p.estimated_budget.toString());
        }
      }).catch(console.warn);

      api.getSections(existingProjectId).then(setSections).catch(console.warn);
    }

    api.getSuggestedTemplate().then(setSuggestedTemplate).catch(console.warn);
  }, [existingProjectId]);

  // --- Step 1: Upload & Create Project ---
  async function handleStep1Submit(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0 && !title) {
      setUploadError('Veuillez déposer au moins un document ou saisir le titre du marché.');
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    try {
      let created = project;
      if (!created) {
        created = await api.createProject({
          title: title || files[0]?.name.replace(/\.[^/.]+$/, '') || "Nouvel Appel d'Offres",
          client_name: clientName || "Acheteur Public Détecté",
          reference_code: referenceCode || `AO-${new Date().getFullYear()}-${Math.floor(Math.random() * 1000)}`,
          status: 'in_progress',
          strategic_directives: strategicDirectives || undefined,
          output_language: selectedLanguage,
        });
        setProject(created);
      }

      // Upload all files
      for (const f of files) {
        await api.uploadDCE(created.id, 'cctp', f);
      }

      // Pre-fill Step 2
      setTitle(created.title);
      setClientName(created.client_name);
      setReferenceCode(created.reference_code || '');
      setLocation(created.location || 'France');

      setCurrentStep(2);
    } catch (err: any) {
      setUploadError(err.message || "Erreur lors de l'ingestion des pièces du marché.");
    } finally {
      setIsUploading(false);
    }
  }

  // --- Step 2: Validate Info ---
  async function handleStep2Submit(e: React.FormEvent) {
    e.preventDefault();
    if (!project) return;

    setIsSavingInfo(true);
    try {
      const updated = await api.updateProject(project.id, {
        title,
        client_name: clientName,
        reference_code: referenceCode,
        location,
        estimated_budget: estimatedBudget ? parseFloat(estimatedBudget) : undefined,
        submission_deadline: submissionDeadline ? new Date(submissionDeadline).toISOString() : undefined,
        strategic_directives: strategicDirectives || undefined,
        output_language: selectedLanguage,
      });
      setProject(updated);

      // Fetch or auto-generate sections for Step 3
      const existingSections = await api.getSections(project.id).catch(() => []);
      if (existingSections && existingSections.length > 0) {
        setSections(existingSections);
      } else {
        await handleGenerateMissingSections();
      }

      setCurrentStep(3);
    } catch (err: any) {
      alert("Erreur lors de l'enregistrement des informations: " + err.message);
    } finally {
      setIsSavingInfo(false);
    }
  }

  // --- Step 3: AI Generation ---
  async function handleGenerateMissingSections() {
    if (!project) return;
    setIsGeneratingSections(true);
    try {
      const standardKeys = [
        'presentation_entreprise',
        'references_similaires',
        'moyens_humains',
        'moyens_materiels',
        'methodologie_phasage',
        'qualite_controle',
        'securite_ppsps',
        'rse_environnement',
        'sous_traitance',
      ];

      for (const key of standardKeys) {
        await api.generateSection(project.id, key).catch(console.warn);
      }

      const generated = await api.getSections(project.id);
      setSections(generated || []);
    } catch (err: any) {
      console.warn('Erreur génération sections:', err);
    } finally {
      setIsGeneratingSections(false);
    }
  }

  // --- Step 5: Final Export ---
  async function handleDownloadWord() {
    if (!project) return;
    setIsExporting(true);
    setExportSuccessMsg(null);
    try {
      // Correctif (02/09, découvert en corrigeant la tâche #66) : ce bouton était
      // entièrement muet -- res.docx_url n'a jamais existé sur la vraie réponse backend
      // (ExportJobOut renvoie s3_docx_url, et de toute façon seulement une fois le job
      // Celery terminé), donc window.open() ne s'exécutait jamais, alors que le message
      // de succès s'affichait quand même, inconditionnellement. On interroge maintenant
      // le job jusqu'à complétion puis on télécharge via un blob authentifié (une simple
      // URL directe échouerait en 401, la route exige un Bearer token).
      const job = await api.exportProject(project.id, {
        format: 'docx',
        include_visuals: true,
      });
      let attempts = 0;
      let finalJob = job;
      while (finalJob.status !== 'completed' && finalJob.status !== 'failed' && attempts < 30) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        finalJob = await api.getExportJob(job.id);
        attempts += 1;
      }
      if (finalJob.status === 'failed') {
        throw new Error(finalJob.error_message || "Échec de la génération du document.");
      }
      if (finalJob.s3_docx_url) {
        const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
        const blobUrl = await fetchAuthenticatedBlobUrl(`${apiBase}${finalJob.s3_docx_url}`);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `Memoire_Technique_${project.id}.docx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
      }

      setExportSuccessMsg('Mémoire technique Word compilé et généré avec succès !');
    } catch (err: any) {
      alert("Erreur lors de l'export: " + err.message);
    } finally {
      setIsExporting(false);
    }
  }

  const stepsList = [
    { num: 1, name: t('wizard.step1'), icon: UploadCloud },
    { num: 2, name: t('wizard.step2'), icon: FileCheck2 },
    { num: 3, name: t('wizard.step3'), icon: Edit3 },
    { num: 4, name: t('wizard.step4'), icon: FileSpreadsheet },
    { num: 5, name: t('wizard.step5'), icon: Download },
  ];

  return (
    <div className="page-container max-w-5xl mx-auto font-sans">
      {/* ─── Top Banner & Stepper Header ─── */}
      <div className="card-elevated p-6 sm:p-7 space-y-6 rounded-2xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-2">
            <span className="badge-pill text-[10px]">
              <Sparkles className="w-3 h-3 text-hl" />
              <span>{t('wizard.badge')}</span>
            </span>
            <h1 className="text-xl sm:text-2xl font-extrabold text-foreground font-heading tracking-tight">
              {project ? project.title : t('wizard.title')}
            </h1>
            <p className="section-desc">
              {t('wizard.desc')}
            </p>
          </div>

          {project && (
            <Link
              href={`/projects/${project.id}`}
              className="btn-secondary !py-2 !px-3.5 !text-[12px] cursor-pointer"
            >
              <Info className="w-3.5 h-3.5 text-hl" />
              <span>{t('wizard.open_full_file')}</span>
            </Link>
          )}
        </div>

        {/* Stepper Navigation Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-3 border-t border-line">
          {stepsList.map((step) => {
            const Icon = step.icon;
            const isCurrent = currentStep === step.num;
            const isCompleted = currentStep > step.num;
            return (
              <button
                key={step.num}
                onClick={() => {
                  if (project || step.num === 1) setCurrentStep(step.num);
                }}
                disabled={!project && step.num > 1}
                className={`p-3 rounded-xl border text-left transition-all duration-200 flex items-center gap-2.5 cursor-pointer ${
                  isCurrent
                    ? 'bg-card border-hl text-foreground font-bold ring-1 ring-hl shadow-xs'
                    : isCompleted
                    ? 'card-inset border-positive/40 text-positive font-medium'
                    : 'card-inset opacity-60 text-muted-foreground cursor-not-allowed'
                }`}
              >
                <div className={`w-6 h-6 rounded-lg flex items-center justify-center text-[11px] font-bold shrink-0 ${
                  isCurrent ? 'bg-hl text-hl-contrast shadow-xs' : isCompleted ? 'bg-positive text-hl-contrast' : 'bg-slate-200 dark:bg-raised text-muted-foreground'
                }`}>
                  {isCompleted ? <CheckCircle2 className="w-3.5 h-3.5" /> : step.num}
                </div>
                <span className="text-[12px] truncate font-heading">{step.name}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ═══ STEP 1: IMPORT PIÈCES ═══ */}
      {currentStep === 1 && (
        <div className="card-modern p-6 sm:p-8 space-y-6 rounded-2xl animate-fade-in-up">
          <div className="section-header">
            <h2 className="section-title">
              <UploadCloud className="w-5 h-5 text-hl" />
              <span>{t('wizard.step1_title')}</span>
            </h2>
            <p className="section-desc">
              {t('wizard.step1_desc')}
            </p>
          </div>

          <form onSubmit={handleStep1Submit} className="space-y-5">
            {/* Drag & Drop Zone */}
            <div
              onClick={() => fileInputRef.current?.click()}
              className="p-10 border-2 border-dashed border-slate-300 dark:border-line hover:border-hl/60 rounded-2xl card-inset text-center space-y-3 cursor-pointer transition-all duration-200 group"
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.doc,.zip"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) {
                    setFiles(Array.from(e.target.files));
                  }
                }}
              />
              <div className="w-14 h-14 rounded-2xl bg-hl text-hl-contrast flex items-center justify-center mx-auto group-hover:scale-105 transition-transform duration-200 shadow-xs">
                <UploadCloud className="w-7 h-7" />
              </div>
              <div className="space-y-1">
                <p className="text-[14px] font-bold text-foreground font-heading">
                  {t('wizard.drop_title')}
                </p>
                <p className="text-[12px] text-muted-foreground">
                  {t('wizard.drop_formats')}
                </p>
              </div>
            </div>

            {/* Selected files list */}
            {files.length > 0 && (
              <div className="space-y-2.5">
                <p className="text-[13px] font-bold text-foreground font-heading">
                  {t('wizard.selected_files')} ({files.length}) :
                </p>
                <div className="space-y-2">
                  {files.map((f, i) => (
                    <div
                      key={i}
                      className="card-inset p-3 flex items-center justify-between text-[13px] rounded-xl"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <FileText className="w-4 h-4 text-hl shrink-0" />
                        <span className="truncate text-foreground font-medium">{f.name}</span>
                        <span className="text-[11px] text-muted-foreground font-mono shrink-0">
                          ({(f.size / (1024 * 1024)).toFixed(2)} Mo)
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setFiles(files.filter((_, idx) => idx !== i))}
                        className="text-slate-400 hover:text-danger p-1.5 rounded-md hover:bg-danger/8 transition-colors cursor-pointer"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Optional Manual Title */}
            <div className="space-y-1.5 pt-2">
              <label className="text-[13px] font-medium text-foreground">
                {t('wizard.optional_title')}
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t('wizard.title_placeholder')}
                className="input-field"
              />
            </div>

            {/* Consignes Stratégiques Générales */}
            <div className="space-y-1.5">
              <label className="text-[13px] font-medium text-foreground">
                {t('wizard.strategic_directives')}
              </label>
              <textarea
                value={strategicDirectives}
                onChange={(e) => setStrategicDirectives(e.target.value)}
                placeholder={t('wizard.placeholder_strategic_directives')}
                rows={3}
                className="input-field resize-none"
              />
              <p className="text-[11px] text-muted-foreground">
                {t('wizard.help_strategic_directives')}
              </p>
            </div>

            {/* Langue de rédaction du mémoire généré par IA */}
            <div className="space-y-2">
              <label className="text-[13px] font-medium text-foreground">
                {t('wizard.output_language')}
              </label>
              <div className="grid grid-cols-3 gap-2.5">
                {[
                  { id: 'fr', label: '🇫🇷 Français' },
                  { id: 'en', label: '🇬🇧 English' },
                  { id: 'ar', label: '🇸🇦 العربية' },
                ].map((lang) => (
                  <button
                    key={lang.id}
                    type="button"
                    onClick={() => setSelectedLanguage(lang.id as 'fr' | 'en' | 'ar')}
                    className={`py-2.5 px-3 rounded-xl text-[13px] font-semibold border transition-all duration-200 cursor-pointer ${
                      selectedLanguage === lang.id
                        ? 'bg-hl text-hl-contrast font-bold border-hl shadow-xs'
                        : 'card-inset text-foreground hover:border-slate-300 dark:hover:border-zinc-700'
                    }`}
                  >
                    {lang.label}
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-muted-foreground">
                {t('wizard.help_output_language')}
              </p>
            </div>

            {uploadError && (
              <div className="p-3.5 rounded-xl bg-danger/8 border border-danger/20 text-[13px] text-danger flex items-center gap-2.5">
                <AlertTriangle className="w-4 h-4 text-danger shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            <div className="flex justify-end pt-3 border-t border-line">
              <button
                type="submit"
                disabled={isUploading}
                className="btn-primary cursor-pointer"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{t('wizard.extracting')}</span>
                  </>
                ) : (
                  <>
                    <span>{t('wizard.btn_to_verification')}</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ═══ STEP 2: VERIFY EXTRACTED INFO ═══ */}
      {currentStep === 2 && (
        <div className="card-modern p-6 sm:p-8 space-y-6 rounded-2xl animate-fade-in-up">
          <div className="section-header">
            <h2 className="section-title">
              <FileCheck2 className="w-5 h-5 text-hl" />
              <span>{t('wizard.step2_title')}</span>
            </h2>
            <p className="section-desc">
              {t('wizard.step2_desc')}
            </p>
          </div>

          <form onSubmit={handleStep2Submit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-[13px] font-medium text-foreground">
                  {t('wizard.label_market_title')}
                </label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="input-field"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[13px] font-medium text-foreground">
                  {t('wizard.label_buyer')}
                </label>
                <input
                  type="text"
                  required
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  className="input-field"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[13px] font-medium text-foreground">
                  {t('wizard.label_ref_lot')}
                </label>
                <input
                  type="text"
                  value={referenceCode}
                  onChange={(e) => setReferenceCode(e.target.value)}
                  placeholder={t('wizard.placeholder_ref_lot')}
                  className="input-field"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[13px] font-medium text-foreground">
                  {t('wizard.label_location')}
                </label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder={t('wizard.placeholder_location')}
                  className="input-field"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[13px] font-medium text-foreground">
                  {t('wizard.label_deadline')}
                </label>
                <input
                  type="date"
                  value={submissionDeadline}
                  onChange={(e) => setSubmissionDeadline(e.target.value)}
                  className="input-field"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[13px] font-medium text-foreground">
                  {t('wizard.label_budget')}
                </label>
                <input
                  type="number"
                  value={estimatedBudget}
                  onChange={(e) => setEstimatedBudget(e.target.value)}
                  placeholder={t('wizard.placeholder_budget')}
                  className="input-field"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-line">
              <button
                type="button"
                onClick={() => setCurrentStep(1)}
                className="btn-secondary cursor-pointer"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>{t('wizard.btn_back_docs')}</span>
              </button>

              <button
                type="submit"
                disabled={isSavingInfo}
                className="btn-primary cursor-pointer"
              >
                {isSavingInfo ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                <span>{t('wizard.btn_to_drafting')}</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ═══ STEP 3: REDACT MEMOIRE ═══ */}
      {currentStep === 3 && (
        <div className="space-y-5 animate-fade-in-up">
          <div className="card-modern p-6 space-y-4 rounded-2xl">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="section-header">
                <h2 className="section-title">
                  <Edit3 className="w-5 h-5 text-hl" />
                  <span>{t('wizard.step3_title')}</span>
                </h2>
                <p className="section-desc">
                  {t('wizard.step3_desc')}
                </p>
              </div>

              <button
                onClick={handleGenerateMissingSections}
                disabled={isGeneratingSections}
                className="btn-primary cursor-pointer"
              >
                {isGeneratingSections ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{t('wizard.generating')}</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>{t('wizard.btn_generate_chapter')}</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Chapters Tabs if multiple */}
          {sections.length > 1 && (
            <div className="tab-group !p-1.5 flex-wrap">
              {sections.map((sec, idx) => (
                <button
                  key={sec.id}
                  onClick={() => setActiveSectionIdx(idx)}
                  className={activeSectionIdx === idx ? 'tab-item-active !bg-hl !text-hl-contrast' : 'tab-item'}
                >
                  {sec.title || `Chapitre ${idx + 1}`}
                </button>
              ))}
            </div>
          )}

          {/* WYSIWYG Editor */}
          {sections.length > 0 && sections[activeSectionIdx] ? (
            <div className="card-modern overflow-hidden rounded-2xl">
              <TiptapEditor
                projectId={project!.id}
                section={sections[activeSectionIdx]}
                onSave={(updated) => {
                  setSections(prev => prev.map(s => s.id === updated.id ? updated : s));
                }}
              />
            </div>
          ) : (
            <div className="card-modern p-12 text-center space-y-3 rounded-2xl">
              <FileText className="w-10 h-10 text-slate-300 dark:text-zinc-600 mx-auto" />
              <p className="text-[14px] font-semibold text-foreground font-heading">{t('wizard.empty_sections_title')}</p>
              <p className="text-[12px] text-muted-foreground max-w-sm mx-auto">
                {t('wizard.empty_sections_desc')}
              </p>
            </div>
          )}

          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setCurrentStep(2)}
              className="btn-secondary cursor-pointer"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>{t('wizard.btn_back_info')}</span>
            </button>

            <button
              onClick={() => setCurrentStep(4)}
              className="btn-primary cursor-pointer"
            >
              <span>{t('wizard.btn_to_admin')}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ═══ STEP 4: ADMINISTRATIVE FORMS ═══ */}
      {currentStep === 4 && (
        <div className="card-modern p-6 sm:p-8 space-y-6 rounded-2xl animate-fade-in-up">
          <div className="section-header">
            <h2 className="section-title">
              <FileSpreadsheet className="w-5 h-5 text-hl" />
              <span>{t('wizard.step4_title')}</span>
            </h2>
            <p className="section-desc">
              {t('wizard.step4_desc')}
            </p>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Form 1: DC1 */}
              <div className="card-inset p-4 space-y-2 rounded-xl">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-foreground font-heading">
                    {t('wizard.dc1_title')}
                  </span>
                  <input
                    type="checkbox"
                    checked={adminForms.dc1_required}
                    onChange={(e) => setAdminForms({ ...adminForms, dc1_required: e.target.checked })}
                    className="w-4 h-4 rounded text-hl cursor-pointer"
                  />
                </div>
                <p className="text-[11px] text-muted-foreground">
                  {t('wizard.dc1_desc')}
                </p>
                <span className="badge-pill-emerald text-[9px]">
                  {t('wizard.dc1_badge')}
                </span>
              </div>

              {/* Form 2: DC2 */}
              <div className="card-inset p-4 space-y-2 rounded-xl">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-foreground font-heading">
                    {t('wizard.dc2_title')}
                  </span>
                  <input
                    type="checkbox"
                    checked={adminForms.dc2_required}
                    onChange={(e) => setAdminForms({ ...adminForms, dc2_required: e.target.checked })}
                    className="w-4 h-4 rounded text-hl cursor-pointer"
                  />
                </div>
                <p className="text-[11px] text-muted-foreground">
                  {t('wizard.dc2_desc')}
                </p>
                <span className="badge-pill-emerald text-[9px]">
                  {t('wizard.dc2_badge')}
                </span>
              </div>

              {/* Form 3: DUME */}
              <div className="card-inset p-4 space-y-2 rounded-xl">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-foreground font-heading">
                    {t('wizard.dume_title')}
                  </span>
                  <input
                    type="checkbox"
                    checked={adminForms.dume_required}
                    onChange={(e) => setAdminForms({ ...adminForms, dume_required: e.target.checked })}
                    className="w-4 h-4 rounded text-hl cursor-pointer"
                  />
                </div>
                <p className="text-[11px] text-muted-foreground">
                  {t('wizard.dume_desc')}
                </p>
                <span className="badge-pill-slate text-[9px]">
                  {t('wizard.dume_badge')}
                </span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-positive/8 border border-positive/20 text-[13px] text-positive flex items-center gap-2.5 font-medium">
              <CheckCircle2 className="w-4 h-4 text-positive shrink-0" />
              <span>
                {t('wizard.compliance_note')}
              </span>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-line">
              <button
                type="button"
                onClick={() => setCurrentStep(3)}
                className="btn-secondary cursor-pointer"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>{t('wizard.btn_back_drafting')}</span>
              </button>

              <button
                type="button"
                onClick={() => setCurrentStep(5)}
                className="btn-primary cursor-pointer"
              >
                <span>{t('wizard.btn_to_export')}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ STEP 5: EXPORT & FINALIZE ═══ */}
      {currentStep === 5 && (
        <div className="card-modern p-6 sm:p-8 space-y-6 rounded-2xl animate-fade-in-up">
          <div className="section-header">
            <h2 className="section-title">
              <Download className="w-5 h-5 text-hl" />
              <span>{t('wizard.step5_title')}</span>
            </h2>
            <p className="section-desc">
              {t('wizard.step5_desc')}
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Suggested Template Box */}
            <div className="card-inset p-5 space-y-3 rounded-xl">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-bold text-foreground font-heading">
                  {t('wizard.applied_template')}
                </span>
                <span className="badge-pill text-[9px]">
                  {t('wizard.deduced_tag')}
                </span>
              </div>
              <p className="text-[13px] text-foreground font-semibold truncate">
                {suggestedTemplate?.title || t('wizard.default_template_name')}
              </p>
              <p className="text-[12px] text-muted-foreground">
                {suggestedTemplate?.reason || t('wizard.template_reason')}
              </p>
              <Link
                href="/dashboard/branding"
                className="text-[12px] text-hl hover:underline inline-block font-semibold"
              >
                {t('wizard.change_template_link')}
              </Link>
            </div>

            {/* Readonly output language */}
            <div className="card-inset p-5 space-y-3 rounded-xl">
              <span className="text-[13px] font-bold text-foreground font-heading">
                {t('wizard.output_language')}
              </span>
              <p className="text-sm text-foreground font-semibold">
                {{ fr: '🇫🇷 Français', en: '🇬🇧 English', ar: '🇸🇦 العربية' }[selectedLanguage]}
              </p>
              <p className="text-[11px] text-muted-foreground">
                {t('wizard.help_output_language_readonly')}
              </p>
            </div>
          </div>

          {exportSuccessMsg && (
            <div className="p-3.5 rounded-xl bg-positive/8 border border-positive/20 text-positive text-[13px] font-semibold flex items-center gap-2 animate-fade-in-up">
              <CheckCircle2 className="w-4 h-4 text-positive shrink-0" />
              <span>{exportSuccessMsg}</span>
            </div>
          )}

          {/* Download Action Buttons */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-line">
            <button
              type="button"
              onClick={() => setCurrentStep(4)}
              className="btn-secondary cursor-pointer"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>{t('wizard.btn_back_admin')}</span>
            </button>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleDownloadWord}
                disabled={isExporting}
                className="btn-primary cursor-pointer"
              >
                {isExporting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{t('wizard.compiling')}</span>
                  </>
                ) : (
                  <>
                    <FileText className="w-4 h-4" />
                    <span>{t('wizard.btn_download_word')}</span>
                  </>
                )}
              </button>

              <Link
                href={`/projects/${project?.id}/export`}
                className="btn-secondary cursor-pointer"
              >
                {t('wizard.advanced_export_link')}
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ResponseWizardPage() {
  const { t } = useTranslation();
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-[40vh] text-[13px] text-muted-foreground gap-2.5 font-mono">
        <Loader2 className="w-4 h-4 animate-spin text-hl" />
        <span>{t('dash.loading')}</span>
      </div>
    }>
      <ResponseWizardContent />
    </Suspense>
  );
}
