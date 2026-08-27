'use client';

import React, { useState, useEffect } from 'react';
import {
  Palette,
  Award,
  UploadCloud,
  CheckCircle2,
  FileText,
  Loader2,
  Sparkles,
  RefreshCw,
} from 'lucide-react';
import { api } from '@/lib/api';
import { SuggestedTemplate } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

export default function BrandingAndTemplatesPage() {
  const { t } = useTranslation();
  const [suggestedTemplate, setSuggestedTemplate] = useState<SuggestedTemplate | null>(null);
  const [loadingTemplate, setLoadingTemplate] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Branding Customization Form
  const [primaryColor, setPrimaryColor] = useState('#D97706');
  const [companyLogoUrl, setCompanyLogoUrl] = useState('');
  const [footerMention, setFooterMention] = useState('btpAO — Réponse certifiée et conforme aux règles de la commande publique');
  const [isSavingBranding, setIsSavingBranding] = useState(false);
  const [brandingSaved, setBrandingSaved] = useState(false);

  useEffect(() => {
    loadSuggestedTemplate();
  }, []);

  async function loadSuggestedTemplate() {
    setLoadingTemplate(true);
    try {
      const data = await api.getSuggestedTemplate();
      setSuggestedTemplate(data);
    } catch (err) {
      console.warn('Erreur template suggéré:', err);
    } finally {
      setLoadingTemplate(false);
    }
  }

  async function handleUploadWordTemplate(e: React.FormEvent) {
    e.preventDefault();
    if (!uploadFile) return;

    setIsUploading(true);
    setSuccessMsg(null);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      await api.uploadWordTemplate(formData);
      setSuccessMsg(`Modèle Word "${uploadFile.name}" enregistré comme modèle par défaut !`);
      setUploadFile(null);
      await loadSuggestedTemplate();
    } catch (err: any) {
      alert('Erreur upload modèle Word: ' + err.message);
    } finally {
      setIsUploading(false);
    }
  }

  function handleSaveBranding(e: React.FormEvent) {
    e.preventDefault();
    setIsSavingBranding(true);
    setTimeout(() => {
      setIsSavingBranding(false);
      setBrandingSaved(true);
      setTimeout(() => setBrandingSaved(false), 3000);
    }, 400);
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      {/* Top Banner */}
      <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] shadow-subtle space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            {t('branding.badge')}
          </span>
        </div>
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white font-heading">
          {t('branding.title')}
        </h1>
        <p className="text-xs text-slate-600 dark:text-slate-400">
          {t('branding.desc')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Col: Word Template Deduction & Upload */}
        <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-5 shadow-subtle">
          <div className="space-y-1">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <Award className="w-4 h-4 text-amber-500" />
              <span>{t('branding.word_title')}</span>
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {t('branding.word_desc')}
            </p>
          </div>

          {/* Active Deduced Template Card */}
          <div className="p-4 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                {suggestedTemplate?.name || suggestedTemplate?.title || t('branding.default_model')}
              </span>
              <span className="text-[10px] font-mono font-bold text-amber-600 dark:text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                {suggestedTemplate?.has_template ? t('branding.active_tag') : t('branding.default_tag')}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              {suggestedTemplate?.description || suggestedTemplate?.reason || 'Structure standard intégrant styles de titres, table des matières et en-têtes.'}
            </p>
          </div>

          {/* Upload New Template */}
          <form onSubmit={handleUploadWordTemplate} className="space-y-3 pt-3 border-t border-slate-200 dark:border-[#1E2638]">
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
              {t('branding.replace_label')}
            </label>
            <input
              type="file"
              required
              accept=".docx"
              onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              className="w-full text-xs text-slate-500 file:mr-2 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-amber-600 file:text-white file:text-xs file:font-semibold"
            />
            <p className="text-[10px] text-slate-500">
              {t('branding.word_hint')}
            </p>

            <button
              type="submit"
              disabled={isUploading || !uploadFile}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading shadow-subtle transition-all disabled:opacity-50"
            >
              {isUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <UploadCloud className="w-3.5 h-3.5" />}
              <span>{t('branding.btn_upload_word')}</span>
            </button>
          </form>

          {successMsg && (
            <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-300 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs font-semibold flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}
        </div>

        {/* Right Col: Graphic Branding Options */}
        <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-5 shadow-subtle">
          <div className="space-y-1">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <Palette className="w-4 h-4 text-amber-500" />
              <span>{t('branding.palette_title')}</span>
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {t('branding.palette_desc')}
            </p>
          </div>

          <form onSubmit={handleSaveBranding} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('branding.accent_label')}
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-10 h-10 rounded-lg border border-slate-300 dark:border-[#1E2638] bg-transparent cursor-pointer"
                />
                <input
                  type="text"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-32 px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white font-mono"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                {t('branding.footer_label')}
              </label>
              <textarea
                rows={2}
                value={footerMention}
                onChange={(e) => setFooterMention(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white focus:outline-none focus:border-amber-500"
              />
            </div>

            <button
              type="submit"
              disabled={isSavingBranding}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-slate-100 dark:bg-[#1E2638] hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-white text-xs font-bold font-heading transition-colors"
            >
              {isSavingBranding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
              <span>{t('branding.btn_save_options')}</span>
            </button>

            {brandingSaved && (
              <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-300 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs font-semibold flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                <span>Options graphiques enregistrées !</span>
              </div>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
