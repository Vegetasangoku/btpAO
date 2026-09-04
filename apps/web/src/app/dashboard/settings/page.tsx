'use client';

import React, { useState, useEffect } from 'react';
import {
  Settings,
  Sun,
  Moon,
  Laptop,
  Clock,
  CreditCard,
  SlidersHorizontal,
  Globe,
  ShieldCheck,
  CheckCircle2,
  Loader2,
  Trash2,
  AlertTriangle,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useTheme } from '@/components/theme-provider';
import { useTranslation, Language } from '@/components/i18n-provider';

export default function EnterpriseSettingsPage() {
  const { theme, setTheme } = useTheme();
  const { language, setLanguage, t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'theme' | 'economic' | 'billing' | 'regional' | 'rgpd'>('theme');

  // Economic Rates State (persiste reellement via /company/economic-settings -- TenantSettings)
  const DEFAULT_HOURLY_RATES = {
    directeurTravaux: 95,
    conducteurTravaux: 75,
    chefChantier: 58,
    compagnonQualifie: 46,
    manoeuvre: 34,
    bureauEtudes: 82,
  };
  const [economicSettings, setEconomicSettings] = useState({
    hourlyRates: DEFAULT_HOURLY_RATES,
    inflationRate: 2.8,
    defaultMarginPercent: 12.0,
    riskContingencyPercent: 4.5,
  });
  const [savingEconomic, setSavingEconomic] = useState(false);
  const [economicSavedMsg, setEconomicSavedMsg] = useState(false);
  const [economicError, setEconomicError] = useState<string | null>(null);

  // Subscription / Quotas
  const [subscription, setSubscription] = useState<{
    has_subscription: boolean;
    plan_name: string;
    status: string;
    quota_dossiers: number;
    dossiers_used: number;
    exports_used: number;
  } | null>(null);

  // Regional Preferences
  const [defaultCountry, setDefaultCountry] = useState('FR');
  const [regionalSavedMsg, setRegionalSavedMsg] = useState(false);

  // RGPD
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);
  const [deletionStatus, setDeletionStatus] = useState<string | null>(null);

  useEffect(() => {
    api.getSubscription().then(setSubscription).catch(console.warn);
    api
      .getEconomicSettings()
      .then((data: any) => {
        setEconomicSettings((prev) => ({
          hourlyRates: { ...prev.hourlyRates, ...(data.taux_horaires || {}) },
          inflationRate: data.taux_inflation_pct ?? prev.inflationRate,
          defaultMarginPercent: data.marge_cible_pct ?? prev.defaultMarginPercent,
          riskContingencyPercent: data.risk_contingency_pct ?? prev.riskContingencyPercent,
        }));
      })
      .catch(console.warn);
  }, []);

  async function handleSaveEconomic(e: React.FormEvent) {
    e.preventDefault();
    setSavingEconomic(true);
    setEconomicError(null);
    try {
      await api.updateEconomicSettings({
        taux_inflation_pct: economicSettings.inflationRate,
        marge_cible_pct: economicSettings.defaultMarginPercent,
        risk_contingency_pct: economicSettings.riskContingencyPercent,
        taux_horaires: economicSettings.hourlyRates,
      });
      setEconomicSavedMsg(true);
      setTimeout(() => setEconomicSavedMsg(false), 3000);
    } catch (err: any) {
      setEconomicError(err?.message || "Erreur lors de l'enregistrement des réglages économiques.");
    } finally {
      setSavingEconomic(false);
    }
  }

  function handleSaveRegional(e: React.FormEvent) {
    e.preventDefault();
    setRegionalSavedMsg(true);
    setTimeout(() => setRegionalSavedMsg(false), 3000);
  }

  async function handleRequestDeletion() {
    if (!confirm('Êtes-vous sûr de vouloir demander la suppression de votre compte et de vos données d\'entreprise (RGPD Art. 17) ?')) return;
    setIsDeletingAccount(true);
    try {
      const res = await api.requestAccountDeletion();
      setDeletionStatus(res.message);
    } catch (err: any) {
      alert('Erreur: ' + err.message);
    } finally {
      setIsDeletingAccount(false);
    }
  }

  const tabs = [
    { id: 'theme' as const, label: t('settings.tab_theme'), icon: Sun },
    { id: 'economic' as const, label: t('settings.tab_economic'), icon: SlidersHorizontal },
    { id: 'billing' as const, label: t('settings.tab_billing'), icon: CreditCard },
    { id: 'regional' as const, label: t('settings.tab_regional'), icon: Globe },
    { id: 'rgpd' as const, label: t('settings.tab_rgpd'), icon: ShieldCheck },
  ];

  return (
    <div className="page-container max-w-5xl mx-auto font-sans">
      {/* ─── Top Banner ─── */}
      <div className="card-elevated p-6 sm:p-7 space-y-5 rounded-2xl">
        <div className="section-header">
          <span className="badge-pill text-[10px]">Configuration Système</span>
          <h1 className="text-xl sm:text-2xl font-extrabold text-foreground font-heading tracking-tight mt-2">
            {t('settings.title')}
          </h1>
          <p className="section-desc">{t('settings.desc')}</p>
        </div>

        {/* Tab Navigation */}
        <div className="tab-group">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={isActive ? 'tab-item-active !bg-hl !text-hl-contrast' : 'tab-item'}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : ''}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ─── TAB 1: THEME & APPARENCE ─── */}
      {activeTab === 'theme' && (
        <div className="card-modern p-6 sm:p-8 space-y-6 rounded-2xl animate-fade-in-up">
          <div className="section-header">
            <h2 className="section-title">
              <Sun className="w-5 h-5 text-hl" />
              <span>Apparence de l'Interface (Thème)</span>
            </h2>
            <p className="section-desc">
              Choisissez le mode d'affichage de votre espace de travail.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { mode: 'schedule' as const, icon: Clock, title: 'Horaires Chantier', desc: 'Clair en journée (07h30 - 20h30), bascule automatique en sombre le soir.' },
              { mode: 'system' as const, icon: Laptop, title: 'Système (OS)', desc: "S'adapte directement aux réglages de votre système d'exploitation." },
              { mode: 'dark' as const, icon: Moon, title: 'Mode Sombre', desc: 'Fond sombre profond, reposant pour les yeux et les longues sessions.' },
              { mode: 'light' as const, icon: Sun, title: 'Mode Clair', desc: 'Fond clair et net, pour une lisibilité maximale en plein jour.' },
            ].map(({ mode, icon: ModeIcon, title, desc }) => (
              <button
                key={mode}
                type="button"
                onClick={() => setTheme(mode)}
                className={`p-5 rounded-2xl border-2 text-left transition-all duration-200 space-y-3 cursor-pointer ${
                  theme === mode
                    ? 'border-hl bg-hl/5 shadow-xs'
                    : 'border-line bg-white dark:bg-raised hover:border-hl/50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    theme === mode ? 'bg-hl/15 text-hl' : 'bg-slate-100 dark:bg-card text-muted-foreground'
                  }`}>
                    <ModeIcon className="w-5 h-5" />
                  </div>
                  {theme === mode && (
                    <span className="badge-pill text-[9px]">Actif</span>
                  )}
                </div>
                <div>
                  <p className="text-[13px] font-bold text-foreground font-heading">{title}</p>
                  <p className="text-[12px] text-muted-foreground mt-1 leading-relaxed">{desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ─── TAB 2: ECONOMIC SETTINGS ─── */}
      {activeTab === 'economic' && (
        <div className="card-modern p-6 sm:p-8 space-y-6 rounded-2xl animate-fade-in-up">
          <div className="section-header">
            <h2 className="section-title">
              <SlidersHorizontal className="w-5 h-5 text-hl" />
              <span>Règles Économiques & Taux Horaires</span>
            </h2>
            <p className="section-desc">
              Ces taux sont injectés dans l'analyse financière de vos offres et la décomposition de prix.
            </p>
          </div>

          <form onSubmit={handleSaveEconomic} className="space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {[
                { label: 'Conducteur de Travaux (€/h)', value: economicSettings.hourlyRates.conducteurTravaux, key: 'conducteurTravaux' },
                { label: 'Chef de Chantier (€/h)', value: economicSettings.hourlyRates.chefChantier, key: 'chefChantier' },
                { label: 'Compagnon Qualifié (€/h)', value: economicSettings.hourlyRates.compagnonQualifie, key: 'compagnonQualifie' },
                { label: "Taux d'Inflation Annuel (%)", value: economicSettings.inflationRate, key: 'inflationRate', isGlobal: true, step: '0.1' },
                { label: 'Marge Commerciale Cible (%)', value: economicSettings.defaultMarginPercent, key: 'defaultMarginPercent', isGlobal: true, step: '0.1' },
                { label: 'Aléas Chantier / Risques (%)', value: economicSettings.riskContingencyPercent, key: 'riskContingencyPercent', isGlobal: true, step: '0.1' },
              ].map(({ label, value, key, isGlobal, step }) => (
                <div key={key} className="space-y-1.5">
                  <label className="text-[13px] font-medium text-foreground">{label}</label>
                  <input
                    type="number"
                    step={step}
                    value={value}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value) || 0;
                      if (isGlobal) {
                        setEconomicSettings({ ...economicSettings, [key]: val });
                      } else {
                        setEconomicSettings({
                          ...economicSettings,
                          hourlyRates: { ...economicSettings.hourlyRates, [key]: val }
                        });
                      }
                    }}
                    className="input-field"
                  />
                </div>
              ))}
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="submit"
                disabled={savingEconomic}
                className="btn-primary cursor-pointer"
              >
                {savingEconomic ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                <span>Enregistrer les règles économiques</span>
              </button>
            </div>

            {economicSavedMsg && (
              <div className="p-3.5 rounded-xl bg-positive/8 border border-positive/20 text-positive text-[13px] font-medium flex items-center gap-2.5 animate-fade-in-up">
                <CheckCircle2 className="w-4 h-4 text-positive shrink-0" />
                <span>Règles de chiffrage enregistrées avec succès !</span>
              </div>
            )}
            {economicError && (
              <div className="p-3.5 rounded-xl bg-danger/8 border border-danger/20 text-danger text-[13px] font-medium flex items-center gap-2.5 animate-fade-in-up">
                <AlertTriangle className="w-4 h-4 text-danger shrink-0" />
                <span>{economicError}</span>
              </div>
            )}
          </form>
        </div>
      )}

      {/* ─── TAB 3: BILLING & QUOTAS ─── */}
      {activeTab === 'billing' && (
        <div className="card-modern p-6 sm:p-8 space-y-6 rounded-2xl animate-fade-in-up">
          <div className="section-header">
            <h2 className="section-title">
              <CreditCard className="w-5 h-5 text-hl" />
              <span>Abonnement & Consommation des Quotas</span>
            </h2>
            <p className="section-desc">
              Suivez l'utilisation de vos dossiers et exports de mémoires techniques.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="card-inset p-5 space-y-2 rounded-xl">
              <span className="text-[12px] text-muted-foreground">Plan d'Abonnement Actif</span>
              <p className="text-lg font-bold text-foreground font-heading">
                {subscription?.plan_name || 'BTP Entreprise Pro'}
              </p>
              <span className="badge-pill-emerald text-[10px]">Actif & Conforme</span>
            </div>

            <div className="card-inset p-5 space-y-2 rounded-xl">
              <span className="text-[12px] text-muted-foreground">Dossiers d'AO Utilisés</span>
              <p className="text-lg font-bold text-foreground font-heading">
                {subscription?.dossiers_used || 0} / {subscription?.quota_dossiers || 20}
              </p>
              <p className="text-[11px] text-muted-foreground">Réinitialisé chaque mois</p>
            </div>

            <div className="card-inset p-5 space-y-2 rounded-xl">
              <span className="text-[12px] text-muted-foreground">Exports Word & PDF Réalisés</span>
              <p className="text-lg font-bold text-foreground font-heading">
                {subscription?.exports_used || 0}
              </p>
              <p className="text-[11px] text-muted-foreground">Compilations certifiées</p>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 4: REGIONAL ─── */}
      {activeTab === 'regional' && (
        <div className="card-modern p-6 sm:p-8 space-y-6 rounded-2xl animate-fade-in-up">
          <div className="section-header">
            <h2 className="section-title">
              <Globe className="w-5 h-5 text-hl" />
              <span>{t('settings.tab_regional')}</span>
            </h2>
            <p className="section-desc">
              Définissez la réglementation pays et la langue active de la plateforme.
            </p>
          </div>

          <form onSubmit={handleSaveRegional} className="space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-[13px] font-medium text-foreground">Réglementation Pays par Défaut</label>
                <select
                  value={defaultCountry}
                  onChange={(e) => setDefaultCountry(e.target.value)}
                  className="input-field"
                >
                  <option value="FR">🇫🇷 France (Code de la Commande Publique)</option>
                  <option value="SA">🇸🇦 Arabie Saoudite (GTPL / Local Content Authority)</option>
                  <option value="QA">🇶🇦 Qatar (Ashghal QCS 2014)</option>
                  <option value="AE">🇦🇪 Émirats Arabes Unis (FIDIC)</option>
                  <option value="LB">🇱🇧 Liban (CDR)</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-[13px] font-medium text-foreground">Langue Globale de l'Interface & des Livrables</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value as Language)}
                  className="input-field"
                >
                  <option value="fr">🇫🇷 Français (French)</option>
                  <option value="en">🇬🇧 English (International / FIDIC)</option>
                  <option value="ar">🇸🇦 العربية (Arabic - RTL)</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button type="submit" className="btn-primary cursor-pointer">
                {t('common.save')}
              </button>
            </div>

            {regionalSavedMsg && (
              <div className="p-3.5 rounded-xl bg-positive/8 border border-positive/20 text-positive text-[13px] font-medium flex items-center gap-2.5 animate-fade-in-up">
                <CheckCircle2 className="w-4 h-4 text-positive shrink-0" />
                <span>Préférences régionales et langue sauvegardées avec succès !</span>
              </div>
            )}
          </form>
        </div>
      )}

      {/* ─── TAB 5: RGPD ─── */}
      {activeTab === 'rgpd' && (
        <div className="card-modern p-6 sm:p-8 space-y-6 rounded-2xl animate-fade-in-up">
          <div className="section-header">
            <h2 className="section-title">
              <ShieldCheck className="w-5 h-5 text-hl" />
              <span>Confidentialité & Droit à l'Effacement (RGPD Art. 17)</span>
            </h2>
            <p className="section-desc">
              Conformément à la réglementation européenne sur la protection des données.
            </p>
          </div>

          <div className="p-5 rounded-2xl bg-danger/5 border-2 border-dashed border-danger/50 dark:border-danger/20 space-y-4">
            <h3 className="text-[14px] font-bold text-danger font-heading">
              Suppression Définitive du Compte et des Données
            </h3>
            <p className="text-[13px] text-muted-foreground leading-relaxed">
              La demande d'effacement déclenche la purge certifiée de tous vos mémoires générés, pièces de consultation déposées, fiches savoir-faire et comptes collaborateurs sous 30 jours calendaires.
            </p>

            <button
              onClick={handleRequestDeletion}
              disabled={isDeletingAccount}
              className="btn-danger cursor-pointer"
            >
              {isDeletingAccount ? 'Traitement...' : 'Demander la suppression de mon compte'}
            </button>

            {deletionStatus && (
              <p className="text-[13px] font-medium text-positive pt-2">{deletionStatus}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
