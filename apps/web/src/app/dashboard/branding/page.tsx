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
  const [primaryColor, setPrimaryColor] = useState('#1C6091');
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
    <div className="page-container max-w-5xl mx-auto font-sans">
      {/* ─── Top Banner ─── */}
      <div className="card-elevated p-6 sm:p-7 space-y-2 rounded-2xl">
        <span className="badge-pill text-[10px]">
          <span className="w-1.5 h-1.5 rounded-full bg-hl"></span>
          {t('branding.badge')}
        </span>
        <h1 className="text-xl sm:text-2xl font-extrabold text-foreground font-heading tracking-tight">
          {t('branding.title')}
        </h1>
        <p className="section-desc">
          {t('branding.desc')}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* ─── Left: Word Template ─── */}
        <div className="card-modern p-6 space-y-5 rounded-2xl">
          <div className="section-header">
            <h2 className="section-title text-[15px]">
              <Award className="w-4 h-4 text-hl" />
              <span>{t('branding.word_title')}</span>
            </h2>
            <p className="section-desc text-[12px]">{t('branding.word_desc')}</p>
          </div>

          {/* Active Template Card */}
          <div className="card-inset p-4 space-y-1.5 rounded-xl">
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-semibold text-foreground">
                {suggestedTemplate?.name || suggestedTemplate?.title || t('branding.default_model')}
              </span>
              <span className="badge-pill-slate text-[9px]">
                {suggestedTemplate?.has_template ? t('branding.active_tag') : t('branding.default_tag')}
              </span>
            </div>
            <p className="text-[12px] text-muted-foreground">
              {suggestedTemplate?.description || suggestedTemplate?.reason || 'Structure standard intégrant styles de titres, table des matières et en-têtes.'}
            </p>
          </div>

          {/* Upload New Template */}
          <form onSubmit={handleUploadWordTemplate} className="space-y-3 pt-4 border-t border-line">
            <label className="text-[13px] font-medium text-foreground block">
              {t('branding.replace_label')}
            </label>
            <input
              type="file"
              required
              accept=".docx"
              onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              className="w-full text-[13px] text-muted-foreground file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:bg-hl file:text-hl-contrast file:text-[13px] file:font-semibold cursor-pointer file:cursor-pointer file:transition-colors file:hover:bg-hl-strong"
            />
            <p className="text-[11px] text-muted-foreground">
              {t('branding.word_hint')}
            </p>

            <button
              type="submit"
              disabled={isUploading || !uploadFile}
              className="btn-secondary w-full cursor-pointer"
            >
              {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4 text-hl" />}
              <span>{t('branding.btn_upload_word')}</span>
            </button>
          </form>

          {successMsg && (
            <div className="p-3.5 rounded-xl bg-positive/8 border border-positive/20 text-positive text-[13px] font-medium flex items-center gap-2.5 animate-fade-in-up">
              <CheckCircle2 className="w-4 h-4 text-positive shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}
        </div>

        {/* ─── Right: Graphic Branding ─── */}
        <div className="card-modern p-6 space-y-5 rounded-2xl">
          <div className="section-header">
            <h2 className="section-title text-[15px]">
              <Palette className="w-4 h-4 text-hl" />
              <span>{t('branding.palette_title')}</span>
            </h2>
            <p className="section-desc text-[12px]">{t('branding.palette_desc')}</p>
          </div>

          <form onSubmit={handleSaveBranding} className="space-y-5">
            <div className="space-y-2">
              <label className="text-[13px] font-medium text-foreground">
                {t('branding.accent_label')}
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-10 h-10 rounded-lg border border-line bg-transparent cursor-pointer"
                />
                <span className="font-mono text-[13px] text-muted-foreground uppercase bg-sunken px-3 py-1.5 rounded-lg border border-line">
                  {primaryColor}
                </span>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-[13px] font-medium text-foreground">
                {t('branding.logo_label')}
              </label>
              <input
                type="text"
                value={companyLogoUrl}
                onChange={(e) => setCompanyLogoUrl(e.target.value)}
                placeholder="https://mon-entreprise-btp.fr/logo.png"
                className="input-field"
              />
            </div>

            <div className="space-y-2">
              <label className="text-[13px] font-medium text-foreground">
                {t('branding.footer_label')}
              </label>
              <textarea
                value={footerMention}
                onChange={(e) => setFooterMention(e.target.value)}
                rows={2}
                className="input-field resize-none"
              />
            </div>

            <button
              type="submit"
              disabled={isSavingBranding}
              className="btn-primary w-full cursor-pointer"
            >
              {isSavingBranding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              <span>{t('branding.btn_save_style')}</span>
            </button>
          </form>

          {brandingSaved && (
            <div className="p-3.5 rounded-xl bg-positive/8 border border-positive/20 text-positive text-[13px] font-medium flex items-center gap-2.5 animate-fade-in-up">
              <CheckCircle2 className="w-4 h-4 text-positive shrink-0" />
              <span>{t('branding.saved_confirm')}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
