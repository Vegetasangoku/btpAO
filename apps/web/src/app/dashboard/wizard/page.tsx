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
import { api } from '@/lib/api';
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
      const res = await api.exportProject(project.id, {
        format: 'docx',
        include_visuals: true,
        template: suggestedTemplate?.id,
      });

      if (res.docx_url) {
        window.open(res.docx_url, '_blank');
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
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      {/* Top Banner & Stepper Header */}
      <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] shadow-subtle space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
              {t('wizard.badge')}
            </span>
            <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white font-heading">
              {project ? project.title : t('wizard.title')}
            </h1>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              {t('wizard.desc')}
            </p>
          </div>

          {project && (
            <Link
              href={`/projects/${project.id}`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-[#1E2638] hover:bg-slate-200 dark:hover:bg-slate-700 text-xs text-slate-700 dark:text-slate-300 font-semibold border border-slate-300 dark:border-slate-700 transition-colors"
            >
              <Info className="w-3.5 h-3.5 text-amber-500" />
              <span>{t('wizard.open_full_file')}</span>
            </Link>
          )}
        </div>

        {/* Stepper Navigation Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-2 border-t border-slate-200 dark:border-[#1E2638]">
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
                className={`p-2.5 rounded-lg text-left border transition-all flex items-center gap-2 ${
                  isCurrent
                    ? 'bg-amber-500/15 border-amber-500 text-slate-900 dark:text-white font-bold'
                    : isCompleted
                    ? 'bg-slate-100 dark:bg-[#1E2638] border-emerald-500/40 text-emerald-600 dark:text-emerald-400 font-medium'
                    : 'bg-slate-50 dark:bg-[#0F131D] border-slate-200 dark:border-slate-800 text-slate-400'
                }`}
              >
                <div className={`w-5 h-5 rounded-md flex items-center justify-center text-xs shrink-0 ${
                  isCurrent ? 'bg-amber-500 text-white' : isCompleted ? 'bg-emerald-600 text-white' : 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                }`}>
                  {isCompleted ? <CheckCircle2 className="w-3 h-3" /> : step.num}
                </div>
                <span className="text-[11px] truncate font-heading">{step.name}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* --- STEP 1: IMPORT PIÈCES --- */}
      {currentStep === 1 && (
        <div className="p-6 sm:p-8 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-6 shadow-subtle">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <UploadCloud className="w-5 h-5 text-amber-500" />
              <span>{t('wizard.step1_title')}</span>
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              {t('wizard.step1_desc')}
            </p>
          </div>

          <form onSubmit={handleStep1Submit} className="space-y-4">
            {/* Drag & Drop Zone */}
            <div
              onClick={() => fileInputRef.current?.click()}
              className="p-8 border-2 border-dashed border-slate-300 dark:border-[#1E2638] hover:border-amber-500/50 rounded-xl bg-slate-50 dark:bg-[#0C0F17] text-center space-y-3 cursor-pointer transition-colors"
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
              <div className="w-12 h-12 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center mx-auto">
                <UploadCloud className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <p className="text-xs font-bold text-slate-800 dark:text-white">
                  {t('wizard.drop_title')}
                </p>
                <p className="text-[11px] text-slate-500">
                  {t('wizard.drop_formats')}
                </p>
              </div>
            </div>

            {/* Selected files list */}
            {files.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-bold text-slate-700 dark:text-slate-300 font-heading">
                  {t('wizard.selected_files')} ({files.length}) :
                </p>
                <div className="space-y-1.5">
                  {files.map((f, i) => (
                    <div
                      key={i}
                      className="p-2.5 rounded-lg bg-slate-100 dark:bg-[#1A2130] flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <FileText className="w-4 h-4 text-amber-500 shrink-0" />
                        <span className="truncate text-slate-800 dark:text-slate-200">{f.name}</span>
                        <span className="text-[10px] text-slate-500 font-mono">
                          ({(f.size / (1024 * 1024)).toFixed(2)} Mo)
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setFiles(files.filter((_, idx) => idx !== i))}
                        className="text-slate-400 hover:text-rose-500 p-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Optional Manual Title */}
            <div className="pt-2 border-t border-slate-200 dark:border-[#1E2638]">
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                {t('wizard.optional_title')}
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t('wizard.title_placeholder')}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
              />
            </div>

            {/* Consignes Stratégiques Générales — directive prioritaire sur le RAG pour toute génération IA de ce dossier */}
            <div className="pt-2 border-t border-slate-200 dark:border-[#1E2638]">
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                {t('wizard.label_strategic_directives')}
              </label>
              <textarea
                value={strategicDirectives}
                onChange={(e) => setStrategicDirectives(e.target.value)}
                placeholder={t('wizard.placeholder_strategic_directives')}
                rows={3}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
              />
              <p className="text-[10px] text-slate-500 dark:text-slate-500 mt-1">
                {t('wizard.help_strategic_directives')}
              </p>
            </div>

            {uploadError && (
              <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-500/40 text-xs text-rose-700 dark:text-rose-300 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button
                type="submit"
                disabled={isUploading}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading shadow-subtle transition-all disabled:opacity-50 cursor-pointer"
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

      {/* --- STEP 2: VERIFY EXTRACTED INFO --- */}
      {currentStep === 2 && (
        <div className="p-6 sm:p-8 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-6 shadow-subtle">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <FileCheck2 className="w-5 h-5 text-amber-500" />
              <span>{t('wizard.step2_title')}</span>
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              {t('wizard.step2_desc')}
            </p>
          </div>

          <form onSubmit={handleStep2Submit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {t('wizard.label_market_title')}
                </label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {t('wizard.label_buyer')}
                </label>
                <input
                  type="text"
                  required
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {t('wizard.label_ref_lot')}
                </label>
                <input
                  type="text"
                  value={referenceCode}
                  onChange={(e) => setReferenceCode(e.target.value)}
                  placeholder={t('wizard.placeholder_ref_lot')}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {t('wizard.label_location')}
                </label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder={t('wizard.placeholder_location')}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {t('wizard.label_deadline')}
                </label>
                <input
                  type="date"
                  value={submissionDeadline}
                  onChange={(e) => setSubmissionDeadline(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  {t('wizard.label_budget')}
                </label>
                <input
                  type="number"
                  value={estimatedBudget}
                  onChange={(e) => setEstimatedBudget(e.target.value)}
                  placeholder={t('wizard.placeholder_budget')}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-slate-200 dark:border-[#1E2638]">
              <button
                type="button"
                onClick={() => setCurrentStep(1)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-slate-100 dark:bg-[#1E2638] text-slate-700 dark:text-slate-300 text-xs font-semibold"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>{t('wizard.btn_back_docs')}</span>
              </button>

              <button
                type="submit"
                disabled={isSavingInfo}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading shadow-subtle transition-all cursor-pointer"
              >
                {isSavingInfo ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                <span>{t('wizard.btn_to_drafting')}</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* --- STEP 3: REDACT MEMOIRE --- */}
      {currentStep === 3 && (
        <div className="space-y-4">
          <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-2 shadow-subtle">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
                  <Edit3 className="w-5 h-5 text-amber-500" />
                  <span>{t('wizard.step3_title')}</span>
                </h2>
                <p className="text-xs text-slate-600 dark:text-slate-400">
                  {t('wizard.step3_desc')}
                </p>
              </div>

              <button
                onClick={handleGenerateMissingSections}
                disabled={isGeneratingSections}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading transition-all shadow-subtle"
              >
                {isGeneratingSections ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>{t('wizard.generating')}</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>{t('wizard.btn_generate_chapter')}</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Chapters Tabs if multiple */}
          {sections.length > 1 && (
            <div className="flex flex-wrap gap-2">
              {sections.map((sec, idx) => (
                <button
                  key={sec.id}
                  onClick={() => setActiveSectionIdx(idx)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    activeSectionIdx === idx
                      ? 'bg-amber-600 text-white shadow-subtle'
                      : 'bg-white dark:bg-[#131823] text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white border border-slate-200 dark:border-[#1E2638]'
                  }`}
                >
                  {sec.title || `Chapitre ${idx + 1}`}
                </button>
              ))}
            </div>
          )}

          {/* WYSIWYG Editor */}
          {sections.length > 0 && sections[activeSectionIdx] ? (
            <div className="rounded-xl overflow-hidden border border-slate-200 dark:border-[#1E2638] bg-white dark:bg-[#0C0F17] shadow-subtle">
              <TiptapEditor
                projectId={project!.id}
                section={sections[activeSectionIdx]}
                onSave={(updated) => {
                  setSections(prev => prev.map(s => s.id === updated.id ? updated : s));
                }}
              />
            </div>
          ) : (
            <div className="p-12 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] text-center space-y-3">
              <FileText className="w-8 h-8 text-slate-400 mx-auto" />
              <p className="text-xs font-bold text-slate-700 dark:text-slate-300">{t('wizard.empty_sections_title')}</p>
              <p className="text-[11px] text-slate-500">
                {t('wizard.empty_sections_desc')}
              </p>
            </div>
          )}

          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setCurrentStep(2)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-slate-100 dark:bg-[#1E2638] text-slate-700 dark:text-slate-300 text-xs font-semibold"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>{t('wizard.btn_back_info')}</span>
            </button>

            <button
              onClick={() => setCurrentStep(4)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading shadow-subtle transition-all cursor-pointer"
            >
              <span>{t('wizard.btn_to_admin')}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* --- STEP 4: ADMINISTRATIVE FORMS --- */}
      {currentStep === 4 && (
        <div className="p-6 sm:p-8 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-6 shadow-subtle">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-amber-500" />
              <span>{t('wizard.step4_title')}</span>
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              {t('wizard.step4_desc')}
            </p>
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Form 1: DC1 */}
              <div className="p-4 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                    {t('wizard.dc1_title')}
                  </span>
                  <input
                    type="checkbox"
                    checked={adminForms.dc1_required}
                    onChange={(e) => setAdminForms({ ...adminForms, dc1_required: e.target.checked })}
                    className="rounded text-amber-500"
                  />
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  {t('wizard.dc1_desc')}
                </p>
                <span className="inline-block text-[10px] font-mono font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  {t('wizard.dc1_badge')}
                </span>
              </div>

              {/* Form 2: DC2 */}
              <div className="p-4 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                    {t('wizard.dc2_title')}
                  </span>
                  <input
                    type="checkbox"
                    checked={adminForms.dc2_required}
                    onChange={(e) => setAdminForms({ ...adminForms, dc2_required: e.target.checked })}
                    className="rounded text-amber-500"
                  />
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  {t('wizard.dc2_desc')}
                </p>
                <span className="inline-block text-[10px] font-mono font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  {t('wizard.dc2_badge')}
                </span>
              </div>

              {/* Form 3: DUME */}
              <div className="p-4 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                    {t('wizard.dume_title')}
                  </span>
                  <input
                    type="checkbox"
                    checked={adminForms.dume_required}
                    onChange={(e) => setAdminForms({ ...adminForms, dume_required: e.target.checked })}
                    className="rounded text-amber-500"
                  />
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  {t('wizard.dume_desc')}
                </p>
                <span className="inline-block text-[10px] font-mono text-slate-500 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                  {t('wizard.dume_badge')}
                </span>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-300 dark:border-emerald-500/30 text-xs text-emerald-700 dark:text-emerald-300 flex items-center gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>
                {t('wizard.compliance_note')}
              </span>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-slate-200 dark:border-[#1E2638]">
              <button
                type="button"
                onClick={() => setCurrentStep(3)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-slate-100 dark:bg-[#1E2638] text-slate-700 dark:text-slate-300 text-xs font-semibold"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>{t('wizard.btn_back_drafting')}</span>
              </button>

              <button
                type="button"
                onClick={() => setCurrentStep(5)}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading shadow-subtle transition-all cursor-pointer"
              >
                <span>{t('wizard.btn_to_export')}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --- STEP 5: EXPORT & FINALIZE --- */}
      {currentStep === 5 && (
        <div className="p-6 sm:p-8 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-6 shadow-subtle">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <Download className="w-5 h-5 text-amber-500" />
              <span>{t('wizard.step5_title')}</span>
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              {t('wizard.step5_desc')}
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Suggested Template Box */}
            <div className="p-5 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                  {t('wizard.applied_template')}
                </span>
                <span className="text-[10px] font-mono font-bold text-amber-600 dark:text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                  {t('wizard.deduced_tag')}
                </span>
              </div>
              <p className="text-xs text-slate-800 dark:text-slate-300 font-semibold truncate">
                {suggestedTemplate?.title || t('wizard.default_template_name')}
              </p>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                {suggestedTemplate?.reason || t('wizard.template_reason')}
              </p>
              <Link
                href="/dashboard/branding"
                className="text-[11px] text-amber-600 dark:text-amber-400 hover:underline inline-block font-semibold"
              >
                {t('wizard.change_template_link')}
              </Link>
            </div>

            {/* Language Selector */}
            <div className="p-5 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] space-y-3">
              <span className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                {t('wizard.output_language')}
              </span>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'fr', label: '🇫🇷 Français' },
                  { id: 'en', label: '🇬🇧 English' },
                  { id: 'ar', label: '🇸🇦 العربية' },
                ].map((lang) => (
                  <button
                    key={lang.id}
                    type="button"
                    onClick={() => setSelectedLanguage(lang.id as any)}
                    className={`py-2 px-2 rounded-lg text-xs font-bold border transition-all cursor-pointer ${
                      selectedLanguage === lang.id
                        ? 'bg-amber-600 text-white border-amber-500'
                        : 'bg-slate-200 dark:bg-[#1E2638] text-slate-700 dark:text-slate-400 border-transparent hover:text-slate-900 dark:hover:text-white'
                    }`}
                  >
                    {lang.label}
                  </button>
                ))}
              </div>
              {selectedLanguage === 'ar' && (
                <p className="text-[10px] text-amber-600 dark:text-amber-300">
                  RTL activé automatiquement (OpenXML bidi)
                </p>
              )}
            </div>
          </div>

          {exportSuccessMsg && (
            <div className="p-3.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-300 dark:border-emerald-500/40 text-emerald-700 dark:text-emerald-300 text-xs font-semibold flex items-center gap-2 animate-in fade-in">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>{exportSuccessMsg}</span>
            </div>
          )}

          {/* Download Action Buttons */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-slate-200 dark:border-[#1E2638]">
            <button
              type="button"
              onClick={() => setCurrentStep(4)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-slate-100 dark:bg-[#1E2638] text-slate-700 dark:text-slate-300 text-xs font-semibold"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>{t('wizard.btn_back_admin')}</span>
            </button>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleDownloadWord}
                disabled={isExporting}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading shadow-subtle transition-all cursor-pointer disabled:opacity-50"
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
                className="px-4 py-2.5 rounded-lg bg-slate-100 dark:bg-[#1E2638] hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold transition-colors"
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
      <div className="flex items-center justify-center min-h-[40vh] text-xs text-slate-400 gap-2">
        <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
        <span>{t('dash.loading')}</span>
      </div>
    }>
      <ResponseWizardContent />
    </Suspense>
  );
}
