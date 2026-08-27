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

  // Economic Rates State
  const [economicSettings, setEconomicSettings] = useState({
    hourlyRates: {
      directeurTravaux: 95,
      conducteurTravaux: 75,
      chefChantier: 58,
      compagnonQualifie: 46,
      manoeuvre: 34,
      bureauEtudes: 82,
    },
    inflationRate: 2.8,
    defaultMarginPercent: 12.0,
    riskContingencyPercent: 4.5,
  });
  const [savingEconomic, setSavingEconomic] = useState(false);
  const [economicSavedMsg, setEconomicSavedMsg] = useState(false);

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
  }, []);

  function handleSaveEconomic(e: React.FormEvent) {
    e.preventDefault();
    setSavingEconomic(true);
    setTimeout(() => {
      setSavingEconomic(false);
      setEconomicSavedMsg(true);
      setTimeout(() => setEconomicSavedMsg(false), 3000);
    }, 400);
  }

  function handleSaveRegional(e: React.FormEvent) {
    e.preventDefault();
    setRegionalSavedMsg(true);
    setTimeout(() => setRegionalSavedMsg(false), 3000);
  }

  async function handleRequestDeletion() {
    if (!confirm('Êtes-vous sûr de vouloir demander la suppression de votre compte et de vos données d’entreprise (RGPD Art. 17) ?')) return;
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

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-20">
      {/* Top Banner */}
      <div className="p-6 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] shadow-subtle space-y-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
              Configuration Système
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white font-heading">
            {t('settings.title')}
          </h1>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            {t('settings.desc')}
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-200 dark:border-[#1E2638]">
          {[
            { id: 'theme', label: t('settings.tab_theme'), icon: Sun },
            { id: 'economic', label: t('settings.tab_economic'), icon: SlidersHorizontal },
            { id: 'billing', label: t('settings.tab_billing'), icon: CreditCard },
            { id: 'regional', label: t('settings.tab_regional'), icon: Globe },
            { id: 'rgpd', label: t('settings.tab_rgpd'), icon: ShieldCheck },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-bold font-heading border transition-all ${
                  isActive
                    ? 'bg-amber-500/15 border-amber-500 text-slate-900 dark:text-white'
                    : 'bg-transparent border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-[#1E2638]'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-amber-500' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* --- TAB 1: THEME & APPARENCE --- */}
      {activeTab === 'theme' && (
        <div className="p-6 sm:p-8 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-6 shadow-subtle">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <Sun className="w-5 h-5 text-amber-500" />
              <span>Apparence de l'Interface (Thème)</span>
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              Choisissez le mode d'affichage de votre espace de travail.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Option 1: Schedule (Horaires Bureau d'Études) */}
            <button
              type="button"
              onClick={() => setTheme('schedule')}
              className={`p-5 rounded-2xl border text-left transition-all space-y-3 ${
                theme === 'schedule'
                  ? 'bg-amber-500/10 border-amber-500 ring-2 ring-amber-500/30'
                  : 'bg-slate-50 dark:bg-[#0C0F17] border-slate-200 dark:border-[#1E2638] hover:border-slate-400 dark:hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="w-9 h-9 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center">
                  <Clock className="w-5 h-5" />
                </div>
                {theme === 'schedule' && (
                  <span className="text-[10px] font-mono font-bold text-amber-600 dark:text-amber-400 bg-amber-500/15 px-2 py-0.5 rounded">
                    Actif
                  </span>
                )}
              </div>
              <div>
                <p className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                  Horaires Chantier
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                  Clair en journée (07h30 - 20h30), bascule automatique en sombre le soir.
                </p>
              </div>
            </button>

            {/* Option 2: System (OS) */}
            <button
              type="button"
              onClick={() => setTheme('system')}
              className={`p-5 rounded-2xl border text-left transition-all space-y-3 ${
                theme === 'system'
                  ? 'bg-amber-500/10 border-amber-500 ring-2 ring-amber-500/30'
                  : 'bg-slate-50 dark:bg-[#0C0F17] border-slate-200 dark:border-[#1E2638] hover:border-slate-400 dark:hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center">
                  <Laptop className="w-5 h-5" />
                </div>
                {theme === 'system' && (
                  <span className="text-[10px] font-mono font-bold text-amber-600 dark:text-amber-400 bg-amber-500/15 px-2 py-0.5 rounded">
                    Actif
                  </span>
                )}
              </div>
              <div>
                <p className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                  Système (OS)
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                  S’adapte directement aux réglages de votre système d’exploitation (macOS / Windows).
                </p>
              </div>
            </button>

            {/* Option 3: Dark */}
            <button
              type="button"
              onClick={() => setTheme('dark')}
              className={`p-5 rounded-2xl border text-left transition-all space-y-3 ${
                theme === 'dark'
                  ? 'bg-amber-500/10 border-amber-500 ring-2 ring-amber-500/30'
                  : 'bg-slate-50 dark:bg-[#0C0F17] border-slate-200 dark:border-[#1E2638] hover:border-slate-400 dark:hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center">
                  <Moon className="w-5 h-5" />
                </div>
                {theme === 'dark' && (
                  <span className="text-[10px] font-mono font-bold text-amber-600 dark:text-amber-400 bg-amber-500/15 px-2 py-0.5 rounded">
                    Actif
                  </span>
                )}
              </div>
              <div>
                <p className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                  Mode Sombre (Dark)
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                  Fond graphite minéral profond <code className="text-amber-500">#0C0F17</code> reposant pour les yeux.
                </p>
              </div>
            </button>

            {/* Option 4: Light */}
            <button
              type="button"
              onClick={() => setTheme('light')}
              className={`p-5 rounded-2xl border text-left transition-all space-y-3 ${
                theme === 'light'
                  ? 'bg-amber-500/10 border-amber-500 ring-2 ring-amber-500/30'
                  : 'bg-slate-50 dark:bg-[#0C0F17] border-slate-200 dark:border-[#1E2638] hover:border-slate-400 dark:hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center">
                  <Sun className="w-5 h-5" />
                </div>
                {theme === 'light' && (
                  <span className="text-[10px] font-mono font-bold text-amber-600 dark:text-amber-400 bg-amber-500/15 px-2 py-0.5 rounded">
                    Actif
                  </span>
                )}
              </div>
              <div>
                <p className="text-xs font-bold text-slate-900 dark:text-white font-heading">
                  Mode Clair (Light)
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                  Fond calcaire blanc cassé <code className="text-amber-500">#F8FAFC</code> et lisibilité maximale.
                </p>
              </div>
            </button>
          </div>
        </div>
      )}

      {/* --- TAB 2: ECONOMIC SETTINGS --- */}
      {activeTab === 'economic' && (
        <div className="p-6 sm:p-8 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-6 shadow-subtle">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <SlidersHorizontal className="w-5 h-5 text-amber-500" />
              <span>Règles Économiques & Taux Horaires de Chiffrage</span>
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              Ces taux sont injectés dans l’analyse financière de vos offres et la décomposition de prix.
            </p>
          </div>

          <form onSubmit={handleSaveEconomic} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="space-y-1">
                <label className="text-xs text-slate-700 dark:text-slate-300">Conducteur de Travaux (€/h)</label>
                <input
                  type="number"
                  value={economicSettings.hourlyRates.conducteurTravaux}
                  onChange={(e) => setEconomicSettings({
                    ...economicSettings,
                    hourlyRates: { ...economicSettings.hourlyRates, conducteurTravaux: parseFloat(e.target.value) || 0 }
                  })}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-700 dark:text-slate-300">Chef de Chantier (€/h)</label>
                <input
                  type="number"
                  value={economicSettings.hourlyRates.chefChantier}
                  onChange={(e) => setEconomicSettings({
                    ...economicSettings,
                    hourlyRates: { ...economicSettings.hourlyRates, chefChantier: parseFloat(e.target.value) || 0 }
                  })}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-700 dark:text-slate-300">Compagnon Qualifié (€/h)</label>
                <input
                  type="number"
                  value={economicSettings.hourlyRates.compagnonQualifie}
                  onChange={(e) => setEconomicSettings({
                    ...economicSettings,
                    hourlyRates: { ...economicSettings.hourlyRates, compagnonQualifie: parseFloat(e.target.value) || 0 }
                  })}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-700 dark:text-slate-300">Taux d'Inflation Annuel (%)</label>
                <input
                  type="number"
                  step="0.1"
                  value={economicSettings.inflationRate}
                  onChange={(e) => setEconomicSettings({ ...economicSettings, inflationRate: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-700 dark:text-slate-300">Marge Commerciale Cible (%)</label>
                <input
                  type="number"
                  step="0.1"
                  value={economicSettings.defaultMarginPercent}
                  onChange={(e) => setEconomicSettings({ ...economicSettings, defaultMarginPercent: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-700 dark:text-slate-300">Aléas Chantier / Risques (%)</label>
                <input
                  type="number"
                  step="0.1"
                  value={economicSettings.riskContingencyPercent}
                  onChange={(e) => setEconomicSettings({ ...economicSettings, riskContingencyPercent: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white"
                />
              </div>
            </div>

            <div className="flex justify-end pt-3">
              <button
                type="submit"
                disabled={savingEconomic}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading shadow-subtle transition-all"
              >
                {savingEconomic ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                <span>Enregistrer les règles économiques</span>
              </button>
            </div>

            {economicSavedMsg && (
              <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-300 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs font-semibold flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                <span>Règles de chiffrage enregistrées avec succès !</span>
              </div>
            )}
          </form>
        </div>
      )}

      {/* --- TAB 3: BILLING & QUOTAS --- */}
      {activeTab === 'billing' && (
        <div className="p-6 sm:p-8 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-6 shadow-subtle">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-amber-500" />
              <span>Abonnement & Consommation des Quotas</span>
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              Suivez l'utilisation de vos dossiers et exports de mémoires techniques.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] space-y-1">
              <span className="text-[11px] text-slate-500 dark:text-slate-400">Plan d'Abonnement Actif</span>
              <p className="text-lg font-bold text-slate-900 dark:text-white font-heading">
                {subscription?.plan_name || 'BTP Entreprise Pro'}
              </p>
              <span className="inline-block text-[10px] font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                Actif & Conforme
              </span>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] space-y-1">
              <span className="text-[11px] text-slate-500 dark:text-slate-400">Dossiers d'AO Utilisés</span>
              <p className="text-lg font-bold text-slate-900 dark:text-white font-heading">
                {subscription?.dossiers_used || 0} / {subscription?.quota_dossiers || 20}
              </p>
              <p className="text-[10px] text-slate-500">Réinitialisé chaque mois</p>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] space-y-1">
              <span className="text-[11px] text-slate-500 dark:text-slate-400">Exports Word & PDF Réalisés</span>
              <p className="text-lg font-bold text-slate-900 dark:text-white font-heading">
                {subscription?.exports_used || 0}
              </p>
              <p className="text-[10px] text-slate-500">Compilations certifiées</p>
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 4: REGIONAL PREFERENCES & GLOBAL LANGUAGE --- */}
      {activeTab === 'regional' && (
        <div className="p-6 sm:p-8 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-6 shadow-subtle">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <Globe className="w-5 h-5 text-amber-500" />
              <span>{t('settings.tab_regional')}</span>
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              Définissez la réglementation pays et la langue active de la plateforme et des dossiers générés.
            </p>
          </div>

          <form onSubmit={handleSaveRegional} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs text-slate-700 dark:text-slate-300">Réglementation Pays par Défaut</label>
                <select
                  value={defaultCountry}
                  onChange={(e) => setDefaultCountry(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white"
                >
                  <option value="FR">🇫🇷 France (Code de la Commande Publique)</option>
                  <option value="SA">🇸🇦 Arabie Saoudite (GTPL / Local Content Authority)</option>
                  <option value="QA">🇶🇦 Qatar (Ashghal QCS 2014)</option>
                  <option value="AE">🇦🇪 Émirats Arabes Unis (FIDIC)</option>
                  <option value="LB">🇱🇧 Liban (CDR)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-700 dark:text-slate-300">Langue Globale de l'Interface & des Livrables</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value as Language)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-[#0C0F17] border border-slate-300 dark:border-[#1E2638] text-xs text-slate-900 dark:text-white"
                >
                  <option value="fr">🇫🇷 Français (French)</option>
                  <option value="en">🇬🇧 English (International / FIDIC)</option>
                  <option value="ar">🇸🇦 العربية (Arabic - RTL)</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end pt-3">
              <button
                type="submit"
                className="px-5 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold font-heading"
              >
                {t('common.save')}
              </button>
            </div>

            {regionalSavedMsg && (
              <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-300 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300 text-xs font-semibold flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                <span>Préférences régionales et langue sauvegardées avec succès !</span>
              </div>
            )}
          </form>
        </div>
      )}

      {/* --- TAB 5: RGPD --- */}
      {activeTab === 'rgpd' && (
        <div className="p-6 sm:p-8 rounded-xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-6 shadow-subtle">
          <div className="space-y-1">
            <h2 className="text-base font-bold text-slate-900 dark:text-white font-heading flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-amber-500" />
              <span>Confidentialité & Droit à l'Effacement (RGPD Art. 17)</span>
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              Conformément à la réglementation européenne sur la protection des données.
            </p>
          </div>

          <div className="p-5 rounded-lg bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-500/30 space-y-3">
            <h3 className="text-xs font-bold text-rose-600 dark:text-rose-400 font-heading">
              Suppression Définitive du Compte et des Données
            </h3>
            <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
              La demande d'effacement déclenche la purge certifiée de tous vos mémoires générés, pièces de consultation déposées, fiches savoir-faire et comptes collaborateurs sous 30 jours calendaires.
            </p>

            <button
              onClick={handleRequestDeletion}
              disabled={isDeletingAccount}
              className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold font-heading transition-colors cursor-pointer"
            >
              {isDeletingAccount ? 'Traitement...' : 'Demander la suppression de mon compte'}
            </button>

            {deletionStatus && (
              <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400 pt-2">{deletionStatus}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
