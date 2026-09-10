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

  // ─── Charte graphique (10/09) ───────────────────────────────────────────
  // Avant : ce formulaire n'appelait aucune API. handleSaveBranding faisait un
  // setTimeout de 400 ms puis affichait « enregistré » — rien n'était écrit, et
  // la charte restait aux valeurs de démonstration en base. Il lit et écrit
  // désormais réellement, et peut se pré-remplir à partir des dossiers déjà
  // déposés par l'entreprise plutôt que d'exiger une saisie manuelle.
  type Charte = {
    company_name: string;
    primary_color: string;
    secondary_color: string;
    font_family: string;
    header_text: string;
    footer_text: string;
  };
  const CHARTE_VIDE: Charte = {
    company_name: '', primary_color: '#1C6091', secondary_color: '#0F172A',
    font_family: 'Inter', header_text: '', footer_text: '',
  };
  const [charte, setCharte] = useState<Charte>(CHARTE_VIDE);
  const [chargementCharte, setChargementCharte] = useState(true);
  const [isSavingBranding, setIsSavingBranding] = useState(false);
  const [brandingSaved, setBrandingSaved] = useState(false);
  const [erreurCharte, setErreurCharte] = useState<string | null>(null);
  const [deduction, setDeduction] = useState<Awaited<ReturnType<typeof api.proposerCharte>> | null>(null);
  const [deductionEnCours, setDeductionEnCours] = useState(false);

  function majCharte(champ: keyof Charte, valeur: string) {
    setCharte((c) => ({ ...c, [champ]: valeur }));
    setBrandingSaved(false);
  }

  useEffect(() => {
    loadSuggestedTemplate();
    api.getTenant()
      .then((t) => {
        const b = t.branding_config || {};
        setCharte({
          company_name: b.company_name || t.name || '',
          primary_color: b.primary_color || CHARTE_VIDE.primary_color,
          secondary_color: b.secondary_color || CHARTE_VIDE.secondary_color,
          font_family: b.font_family || CHARTE_VIDE.font_family,
          header_text: b.header_text || '',
          footer_text: b.footer_text || '',
        });
      })
      .catch(() => setErreurCharte(t('charte.erreur_lecture')))
      .finally(() => setChargementCharte(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function deduireDepuisDossiers() {
    setDeductionEnCours(true);
    setErreurCharte(null);
    try {
      setDeduction(await api.proposerCharte());
    } catch (err) {
      setErreurCharte(err instanceof Error ? err.message : t('charte.analyse_impossible'));
    } finally {
      setDeductionEnCours(false);
    }
  }

  function appliquerProposition() {
    const p = (deduction?.proposition || {}) as Record<string, string>;
    setCharte((c) => ({
      company_name: p.company_name || c.company_name,
      primary_color: p.primary_color || c.primary_color,
      secondary_color: p.secondary_color || c.secondary_color,
      font_family: p.font_family || c.font_family,
      header_text: p.header_text || c.header_text,
      footer_text: p.footer_text || c.footer_text,
    }));
    setBrandingSaved(false);
  }

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

  async function handleSaveBranding(e: React.FormEvent) {
    e.preventDefault();
    setIsSavingBranding(true);
    setErreurCharte(null);
    try {
      const aEnvoyer = Object.fromEntries(
        Object.entries(charte).filter(([, v]) => String(v || '').trim() !== ''),
      ) as Record<string, string>;
      await api.appliquerCharte(aEnvoyer);
      setBrandingSaved(true);
      setTimeout(() => setBrandingSaved(false), 4000);
    } catch (err) {
      setErreurCharte(err instanceof Error ? err.message : t('charte.erreur_enregistrement'));
    } finally {
      setIsSavingBranding(false);
    }
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

          {/* Déduction depuis les dossiers déjà déposés — évite la saisie manuelle
              et, surtout, évite qu'une charte de démonstration parte à l'export. */}
          <div className="card-inset p-4 rounded-xl space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-[13px] font-semibold text-foreground">{t('charte.deduire_title')}</p>
                <p className="text-[11px] text-muted-foreground">
                  {t('charte.deduire_desc')}
                </p>
              </div>
              <button
                type="button"
                onClick={deduireDepuisDossiers}
                disabled={deductionEnCours}
                className="btn-secondary !py-1.5 !px-3 !text-[12px] shrink-0"
              >
                {deductionEnCours
                  ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('charte.analyse_en_cours')}</>
                  : <><RefreshCw className="w-3.5 h-3.5" /> {t('charte.analyser')}</>}
              </button>
            </div>

            {deduction && (
              <div className="space-y-2.5 pt-1">
                {Object.keys(deduction.proposition || {}).length > 0 ? (
                  <>
                    <ul className="space-y-1.5">
                      {/* Les drapeaux internes (…_a_confirmer) ne sont pas des champs de
                          charte : leur avertissement est déjà porté par la provenance. */}
                      {Object.entries(deduction.proposition)
                        .filter(([champ]) => !champ.endsWith('_a_confirmer'))
                        .map(([champ, valeur]) => (
                        <li key={champ} className="text-[11px]">
                          <span className="font-mono text-foreground">{champ}</span>
                          <span className="text-muted-foreground"> = </span>
                          <span className="font-semibold text-foreground break-all">
                            {Array.isArray(valeur) ? valeur.join(', ') : String(valeur)}
                          </span>
                          {deduction.provenance?.[champ] && (
                            <span className="block text-muted-foreground">↳ {deduction.provenance[champ]}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                    <button type="button" onClick={appliquerProposition} className="btn-primary !py-1.5 !px-3 !text-[12px]">
                      <CheckCircle2 className="w-3.5 h-3.5" /> {t('charte.reprendre')}
                    </button>
                  </>
                ) : (
                  <p className="text-[11px] text-muted-foreground">{t('charte.rien_trouve')}</p>
                )}
                {Object.entries(deduction.champs_non_trouves || {}).map(([champ, motif]) => (
                  <p key={champ} className="text-[11px] text-hl">⚠ {motif}</p>
                ))}
                {deduction.documents_analyses?.length > 0 && (
                  <p className="text-[10px] text-muted-foreground">
                    {t('charte.analyse_de')} {deduction.documents_analyses.join(', ')}
                  </p>
                )}
              </div>
            )}
          </div>

          <form onSubmit={handleSaveBranding} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-[13px] font-medium text-foreground">{t('charte.raison_sociale')}</label>
              <input
                type="text"
                value={charte.company_name}
                onChange={(e) => majCharte('company_name', e.target.value)}
                placeholder="EiffaBTP Construction SAS"
                className="input-field"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              {([['primary_color', t('branding.accent_label')], ['secondary_color', t('charte.couleur_secondaire')]] as const).map(([champ, libelle]) => (
                <div className="space-y-1.5" key={champ}>
                  <label className="text-[13px] font-medium text-foreground">{libelle}</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      value={charte[champ]}
                      onChange={(e) => majCharte(champ, e.target.value.toUpperCase())}
                      className="w-10 h-10 rounded-lg border border-line bg-transparent cursor-pointer shrink-0"
                    />
                    <span className="font-mono text-[12px] text-muted-foreground uppercase bg-sunken px-2 py-1.5 rounded-lg border border-line truncate">
                      {charte[champ]}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div className="space-y-1.5">
              <label className="text-[13px] font-medium text-foreground">{t('charte.police')}</label>
              <input
                type="text"
                value={charte.font_family}
                onChange={(e) => majCharte('font_family', e.target.value)}
                placeholder="Inter, Calibri, Arial…"
                className="input-field"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[13px] font-medium text-foreground">{t('charte.entete')}</label>
              <input
                type="text"
                value={charte.header_text}
                onChange={(e) => majCharte('header_text', e.target.value)}
                placeholder="EiffaBTP Construction SAS — Mémoire technique"
                className="input-field"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[13px] font-medium text-foreground">{t('branding.footer_label')}</label>
              <textarea
                value={charte.footer_text}
                onChange={(e) => majCharte('footer_text', e.target.value)}
                rows={2}
                placeholder="Document confidentiel — Réponse à appel d'offres"
                className="input-field resize-none"
              />
            </div>

            <button
              type="submit"
              disabled={isSavingBranding || chargementCharte}
              className="btn-primary w-full cursor-pointer"
            >
              {isSavingBranding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              <span>{t('branding.btn_save_style')}</span>
            </button>
          </form>

          {erreurCharte && (
            <div className="p-3.5 rounded-xl bg-danger/8 border border-danger/20 text-danger text-[13px] font-medium">
              {erreurCharte}
            </div>
          )}

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
