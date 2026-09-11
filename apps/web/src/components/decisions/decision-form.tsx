'use client';

import React, { useEffect, useState } from 'react';
import {
  Sliders,
  Calendar,
  Truck,
  Users,
  Leaf,
  ShieldCheck,
  CheckCircle2,
  Plus,
  Trash2,
  Save,
  ArrowRight,
} from 'lucide-react';
import { ProjectDecisionsForm, CadreEquipe, PhaseChantier } from '@/lib/types';
import { api } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';

interface DecisionFormProps {
  projectId: string;
  initialData?: ProjectDecisionsForm;
  onSaved?: (data: ProjectDecisionsForm) => void;
}

export function DecisionForm({ projectId, initialData, onSaved }: DecisionFormProps) {
  const { t } = useTranslation();
  // 11/09 : le formulaire s'ouvrait sur un chantier d'exemple complet (equipe
  // « Jean-Marc Alibert », grue Potain, 88 % de valorisation...) et n'affichait jamais
  // les donnees deja enregistrees. Un simple « Enregistrer » ecrasait donc les vraies
  // donnees par l'exemple, qui partait ensuite dans le memoire. On part desormais du
  // vide, on recharge ce qui est enregistre, et les exemples ne sont que des indications.
  const [formData, setFormData] = useState<ProjectDecisionsForm>(
    initialData || {
      delai_mois: undefined,
      date_demarrage: '',
      materiel_principal: '',
      travail_de_nuit: false,
      gestion_dechets: '',
      equipe_cadres: [],
      mesures_securite: '',
      demarche_rse_environnement: '',
      phasage_travaux: [],
    }
  );
  const [charge, setCharge] = useState<boolean>(!!initialData);

  useEffect(() => {
    if (initialData) return;
    let annule = false;
    api.getDecisions(projectId)
      .then((d) => {
        if (annule || !d) return;
        setFormData({
          ...d,
          date_demarrage: d.date_demarrage || '',
          materiel_principal: d.materiel_principal || '',
          gestion_dechets: d.gestion_dechets || '',
          mesures_securite: d.mesures_securite || '',
          demarche_rse_environnement: d.demarche_rse_environnement || '',
          equipe_cadres: d.equipe_cadres || [],
          phasage_travaux: d.phasage_travaux || [],
        });
      })
      .catch((e) => console.error('Failed to load decisions', e))
      .finally(() => { if (!annule) setCharge(true); });
    return () => { annule = true; };
  }, [projectId, initialData]);

  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState<'delais' | 'materiels' | 'cadres' | 'rse' | 'securite' | 'phasage'>('delais');

  // 11/09 : donnees d'exemple de l'ancien formulaire, enregistrees telles quelles.
  const EXEMPLES = ['Jean-Marc Alibert', 'Sébastien Vasseur', 'Chloé Fontaine', 'Potain MDT 219', 'Paprec / Veolia à 12 km'];
  const contientExemple = charge && EXEMPLES.some((x) => JSON.stringify(formData).includes(x));

  const handleSave = async () => {
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      const saved = await api.saveDecisions(projectId, formData);
      setSaveSuccess(true);
      if (onSaved) onSaved(saved);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e) {
      console.error('Failed to save decisions', e);
    } finally {
      setIsSaving(false);
    }
  };

  // Add cadre row
  const addCadre = () => {
    setFormData({
      ...formData,
      equipe_cadres: [
        ...formData.equipe_cadres,
        { nom: '', role: '', experience_ans: 0, presence_hebdo_pct: 100, qualif: '' },
      ],
    });
  };

  // Remove cadre row
  const removeCadre = (index: number) => {
    const updated = [...formData.equipe_cadres];
    updated.splice(index, 1);
    setFormData({ ...formData, equipe_cadres: updated });
  };

  // Add phase row
  const addPhase = () => {
    setFormData({
      ...formData,
      phasage_travaux: [
        ...formData.phasage_travaux,
        { phase: '', duree_semaines: 0, jalon: '' },
      ],
    });
  };

  // Remove phase row
  const removePhase = (index: number) => {
    const updated = [...formData.phasage_travaux];
    updated.splice(index, 1);
    setFormData({ ...formData, phasage_travaux: updated });
  };

  return (
    <div className="card-modern p-6 sm:p-7 space-y-6 rounded-2xl font-sans">
      {contientExemple && (
        <div className="p-3 rounded-xl border border-warning/30 bg-warning/10 text-[12px] text-foreground">
          {t('decisions.form.alerte_exemple')}
        </div>
      )}
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-line">
        <div>
          <h2 className="text-[15px] font-bold text-foreground flex items-center gap-2 font-heading">
            <Sliders className="w-4 h-4 text-hl" />
            {t('decisions.form.title')}
          </h2>
          <p className="text-[12px] text-muted-foreground mt-0.5">
            {t('decisions.form.subtitle')}
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={isSaving || !charge}
          className="btn-primary cursor-pointer"
        >
          <Save className="w-4 h-4" />
          <span>{isSaving ? t('decisions.form.saving') : t('decisions.form.save_btn')}</span>
        </button>
      </div>

      {saveSuccess && (
        <div className="p-3.5 rounded-xl bg-positive/8 border border-positive/20 text-positive text-[13px] font-semibold flex items-center gap-2 animate-fade-in-up">
          <CheckCircle2 className="w-4 h-4 text-positive shrink-0" />
          {t('decisions.form.save_success')}
        </div>
      )}

      {/* Tabs Navigation */}
      <div className="tab-group !p-1 flex-wrap">
        {[
          { id: 'delais', label: t('decisions.form.tab_delais'), icon: Calendar },
          { id: 'materiels', label: t('decisions.form.tab_materiels'), icon: Truck },
          { id: 'cadres', label: t('decisions.form.tab_cadres'), icon: Users },
          { id: 'rse', label: t('decisions.form.tab_rse'), icon: Leaf },
          { id: 'securite', label: t('decisions.form.tab_securite'), icon: ShieldCheck },
          { id: 'phasage', label: t('decisions.form.tab_phasage'), icon: ArrowRight },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={isActive ? 'tab-item-active !bg-hl !text-hl-contrast' : 'tab-item'}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab 1: Délais */}
      {activeTab === 'delais' && (
        <div className="space-y-4 animate-fade-in-up">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-[13px] font-medium text-foreground">{t('decisions.form.delai_label')}</label>
              <input
                type="number"
                min="1"
                max="48"
                value={formData.delai_mois ?? ''}
                placeholder={t('decisions.form.exemple_delai')}
                onChange={(e) => setFormData({ ...formData, delai_mois: e.target.value === '' ? undefined : (parseInt(e.target.value) || undefined) })}
                className="input-field font-mono"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[13px] font-medium text-foreground">{t('decisions.form.date_demarrage_label')}</label>
              <input
                type="date"
                value={formData.date_demarrage || ''}
                onChange={(e) => setFormData({ ...formData, date_demarrage: e.target.value })}
                className="input-field"
              />
            </div>
          </div>

          <div className="flex items-center gap-3 p-3.5 rounded-xl card-inset">
            <input
              type="checkbox"
              id="travail_nuit"
              checked={formData.travail_de_nuit}
              onChange={(e) => setFormData({ ...formData, travail_de_nuit: e.target.checked })}
              className="rounded text-hl focus:ring-hl w-4 h-4 cursor-pointer"
            />
            <label htmlFor="travail_nuit" className="text-[13px] text-foreground cursor-pointer font-medium">
              {t('decisions.form.travail_nuit_label')}
            </label>
          </div>
        </div>
      )}

      {/* Tab 2: Matériels */}
      {activeTab === 'materiels' && (
        <div className="space-y-3">
          <label className="text-xs font-semibold text-foreground">
            {t('decisions.form.materiel_label')}
          </label>
          <textarea
            rows={4}
            value={formData.materiel_principal}
            onChange={(e) => setFormData({ ...formData, materiel_principal: e.target.value })}
            className="input-field leading-relaxed"
            placeholder={t('decisions.form.materiel_placeholder')}
          />
          <p className="text-[11px] text-muted-foreground">
            {t('decisions.form.materiel_helper')}
          </p>
        </div>
      )}

      {/* Tab 3: Encadrement & CVs */}
      {activeTab === 'cadres' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-foreground">{t('decisions.form.cadres_label')}</p>
            <button
              onClick={addCadre}
              className="flex items-center gap-1 text-xs text-hl hover:underline font-semibold cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" /> {t('decisions.form.add_cadre_btn')}
            </button>
          </div>

          <div className="space-y-3">
            {formData.equipe_cadres.map((cadre, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl bg-sunken border border-line grid grid-cols-1 md:grid-cols-4 gap-3 items-center"
              >
                <div>
                  <label className="text-[10px] text-muted-foreground uppercase font-semibold">{t('decisions.form.cadre_nom_label')}</label>
                  <input
                    type="text"
                    value={cadre.nom}
                    onChange={(e) => {
                      const updated = [...formData.equipe_cadres];
                      updated[idx].nom = e.target.value;
                      setFormData({ ...formData, equipe_cadres: updated });
                    }}
                    className="input-field !py-1.5 !text-xs"
                    placeholder={t('decisions.form.cadre_nom_placeholder')}
                  />
                </div>

                <div>
                  <label className="text-[10px] text-muted-foreground uppercase font-semibold">{t('decisions.form.cadre_role_label')}</label>
                  <input
                    type="text"
                    value={cadre.role}
                    onChange={(e) => {
                      const updated = [...formData.equipe_cadres];
                      updated[idx].role = e.target.value;
                      setFormData({ ...formData, equipe_cadres: updated });
                    }}
                    className="input-field !py-1.5 !text-xs"
                    placeholder={t('decisions.form.cadre_role_placeholder')}
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-muted-foreground uppercase font-semibold">{t('decisions.form.cadre_exp_label')}</label>
                    <input
                      type="number"
                      value={cadre.experience_ans}
                      onChange={(e) => {
                        const updated = [...formData.equipe_cadres];
                        updated[idx].experience_ans = parseInt(e.target.value) || 0;
                        setFormData({ ...formData, equipe_cadres: updated });
                      }}
                      className="input-field !py-1.5 !text-xs font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted-foreground uppercase font-semibold">{t('decisions.form.cadre_presence_label')}</label>
                    <input
                      type="number"
                      value={cadre.presence_hebdo_pct}
                      onChange={(e) => {
                        const updated = [...formData.equipe_cadres];
                        updated[idx].presence_hebdo_pct = parseInt(e.target.value) || 100;
                        setFormData({ ...formData, equipe_cadres: updated });
                      }}
                      className="input-field !py-1.5 !text-xs font-mono"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between gap-2 pt-3 md:pt-0">
                  <div className="flex-1">
                    <label className="text-[10px] text-muted-foreground uppercase font-semibold">{t('decisions.form.cadre_qualif_label')}</label>
                    <input
                      type="text"
                      value={cadre.qualif || ''}
                      onChange={(e) => {
                        const updated = [...formData.equipe_cadres];
                        updated[idx].qualif = e.target.value;
                        setFormData({ ...formData, equipe_cadres: updated });
                      }}
                      className="input-field !py-1.5 !text-xs"
                      placeholder={t('decisions.form.cadre_qualif_placeholder')}
                    />
                  </div>
                  <button
                    onClick={() => removeCadre(idx)}
                    className="text-slate-400 hover:text-danger p-1.5 rounded self-end mb-0.5 cursor-pointer"
                    title={t('decisions.form.remove_cadre_title')}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: RSE & Déchets */}
      {activeTab === 'rse' && (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-foreground">
              {t('decisions.form.rse_beton_label')}
            </label>
            <textarea
              rows={3}
              value={formData.demarche_rse_environnement}
              placeholder={t('decisions.form.exemple_rse')}
              onChange={(e) => setFormData({ ...formData, demarche_rse_environnement: e.target.value })}
              className="input-field"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-foreground">
              {t('decisions.form.rse_dechets_label')}
            </label>
            <textarea
              rows={3}
              value={formData.gestion_dechets}
              placeholder={t('decisions.form.exemple_dechets')}
              onChange={(e) => setFormData({ ...formData, gestion_dechets: e.target.value })}
              className="input-field"
            />
          </div>
        </div>
      )}

      {/* Tab 5: Sécurité */}
      {activeTab === 'securite' && (
        <div className="space-y-3">
          <label className="text-xs font-semibold text-foreground">
            {t('decisions.form.securite_label')}
          </label>
          <textarea
            rows={4}
            value={formData.mesures_securite}
            placeholder={t('decisions.form.exemple_securite')}
            onChange={(e) => setFormData({ ...formData, mesures_securite: e.target.value })}
            className="input-field"
          />
        </div>
      )}

      {/* Tab 6: Phasage */}
      {activeTab === 'phasage' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-foreground">{t('decisions.form.phasage_label')}</p>
            <button
              onClick={addPhase}
              className="flex items-center gap-1 text-xs text-hl hover:underline font-semibold cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" /> {t('decisions.form.add_phase_btn')}
            </button>
          </div>

          <div className="space-y-2">
            {formData.phasage_travaux.map((phase, idx) => (
              <div
                key={idx}
                className="p-3 rounded-xl bg-sunken border border-line grid grid-cols-1 md:grid-cols-12 gap-3 items-center"
              >
                <div className="md:col-span-6">
                  <input
                    type="text"
                    value={phase.phase}
                    onChange={(e) => {
                      const updated = [...formData.phasage_travaux];
                      updated[idx].phase = e.target.value;
                      setFormData({ ...formData, phasage_travaux: updated });
                    }}
                    className="input-field !py-1.5 !text-xs"
                    placeholder={t('decisions.form.phase_placeholder')}
                  />
                </div>

                <div className="md:col-span-2">
                  <input
                    type="number"
                    value={phase.duree_semaines}
                    onChange={(e) => {
                      const updated = [...formData.phasage_travaux];
                      updated[idx].duree_semaines = parseInt(e.target.value) || 1;
                      setFormData({ ...formData, phasage_travaux: updated });
                    }}
                    className="input-field !py-1.5 !text-xs font-mono"
                    placeholder={t('decisions.form.duree_placeholder')}
                  />
                </div>

                <div className="md:col-span-3">
                  <input
                    type="text"
                    value={phase.jalon}
                    onChange={(e) => {
                      const updated = [...formData.phasage_travaux];
                      updated[idx].jalon = e.target.value;
                      setFormData({ ...formData, phasage_travaux: updated });
                    }}
                    className="input-field !py-1.5 !text-xs"
                    placeholder={t('decisions.form.jalon_placeholder')}
                  />
                </div>

                <div className="md:col-span-1 flex justify-end">
                  <button
                    onClick={() => removePhase(idx)}
                    className="text-slate-400 hover:text-danger p-1 cursor-pointer"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
