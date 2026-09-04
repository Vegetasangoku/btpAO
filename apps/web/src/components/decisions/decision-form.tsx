'use client';

import React, { useState } from 'react';
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
  const [formData, setFormData] = useState<ProjectDecisionsForm>(
    initialData || {
      delai_mois: 6,
      date_demarrage: '2026-10-01',
      materiel_principal:
        'Grue à tour Potain MDT 219 (flèche 50m), 2 pelles Liebherr 22t, 4 camions 8x4 avec bâchage automatique, banches manuportables Alphi',
      travail_de_nuit: false,
      gestion_dechets:
        'Tri sélectif 5 flux sur plateforme sécurisée avec compacteur in situ. Objectif 88% de valorisation matière via plateforme locale Paprec / Veolia à 12 km du site.',
      equipe_cadres: [
        { nom: 'Jean-Marc Alibert', role: 'Directeur de Projet & Conducteur Principal', experience_ans: 15, presence_hebdo_pct: 100, qualif: 'Ingénieur ESTP' },
        { nom: 'Sébastien Vasseur', role: 'Chef de Chantier Gros Œuvre', experience_ans: 12, presence_hebdo_pct: 100, qualif: 'Master Génie Civil' },
        { nom: 'Chloé Fontaine', role: 'Ingénieur QSE & Environnement', experience_ans: 7, presence_hebdo_pct: 50, qualif: 'Master QSE BTP' },
      ],
      mesures_securite:
        "PPSPS strict, accueil sécurité avec badge biométrique, protection collective intégrée sur banches (garde-corps verrouillés), défibrillateur et 4 SST sur site.",
      demarche_rse_environnement:
        'Béton bas carbone CEM III/A (-42% CO2), circuit fermé de recyclage des eaux de lavage toupies, charte chantier vert à faibles nuisances sonores.',
      phasage_travaux: [
        { phase: '1. Installation de chantier, PIC & Terrassements', duree_semaines: 4, jalon: 'Accès voirie & base-vie opérationnels' },
        { phase: '2. Fondations profondes et longrines', duree_semaines: 4, jalon: 'Réception plateforme géotechnique' },
        { phase: '3. Infrastructure & Superstructure R+2 Gros Œuvre', duree_semaines: 10, jalon: "Hors d'eau / Hors d'air structurel" },
        { phase: '4. Réseaux enterrés, VRD & Aménagements extérieurs', duree_semaines: 4, jalon: "Essais d'étanchéité & OPR" },
        { phase: '5. Repli de chantier, levée des réserves & Livraison', duree_semaines: 2, jalon: 'Parfait Achèvement & Remise des clés' },
      ],
    }
  );

  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState<'delais' | 'materiels' | 'cadres' | 'rse' | 'securite' | 'phasage'>('delais');

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
        { nom: '', role: 'Chef d’équipe', experience_ans: 5, presence_hebdo_pct: 100, qualif: '' },
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
        { phase: `Phase ${formData.phasage_travaux.length + 1}`, duree_semaines: 4, jalon: 'Jalon intermédiaire' },
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
          disabled={isSaving}
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
                value={formData.delai_mois}
                onChange={(e) => setFormData({ ...formData, delai_mois: parseInt(e.target.value) || 6 })}
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
