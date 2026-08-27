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

interface DecisionFormProps {
  projectId: string;
  initialData?: ProjectDecisionsForm;
  onSaved?: (data: ProjectDecisionsForm) => void;
}

export function DecisionForm({ projectId, initialData, onSaved }: DecisionFormProps) {
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
    <div className="bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-lg dark:shadow-2xl space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Sliders className="w-5 h-5 text-amber-500 dark:text-amber-400" />
            Formulaire de Décisions & Choix Métiers (Conducteur de Travaux)
          </h2>
          <p className="text-xs text-slate-400">
            Ces choix techniques alimentent directement la rédaction précise et personnalisée de chaque section.
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={isSaving}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold shadow-glow disabled:opacity-50 transition-all"
        >
          <Save className="w-4 h-4" />
          <span>{isSaving ? 'Enregistrement...' : 'Enregistrer les choix'}</span>
        </button>
      </div>

      {saveSuccess && (
        <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          Choix métiers enregistrés avec succès. Le moteur de rédaction et le Gantt sont synchronisés.
        </div>
      )}

      {/* Tabs Navigation */}
      <div className="flex flex-wrap gap-2 border-b border-slate-200 dark:border-slate-800 pb-3">
        {[
          { id: 'delais', label: '1. Délais & Planning', icon: Calendar },
          { id: 'materiels', label: '2. Matériels & Grues', icon: Truck },
          { id: 'cadres', label: '3. Encadrement & CVs', icon: Users },
          { id: 'rse', label: '4. RSE & Déchets', icon: Leaf },
          { id: 'securite', label: '5. Sécurité & PPSPS', icon: ShieldCheck },
          { id: 'phasage', label: '6. Phasage BTP', icon: ArrowRight },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/40'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab 1: Délais */}
      {activeTab === 'delais' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Délai global d’exécution garanti (mois)</label>
              <input
                type="number"
                min="1"
                max="48"
                value={formData.delai_mois}
                onChange={(e) => setFormData({ ...formData, delai_mois: parseInt(e.target.value) || 6 })}
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-200 focus:outline-none focus:border-amber-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Date prévisionnelle de démarrage</label>
              <input
                type="date"
                value={formData.date_demarrage || ''}
                onChange={(e) => setFormData({ ...formData, date_demarrage: e.target.value })}
                className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-200 focus:outline-none focus:border-amber-500"
              />
            </div>
          </div>

          <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
            <input
              type="checkbox"
              id="travail_nuit"
              checked={formData.travail_de_nuit}
              onChange={(e) => setFormData({ ...formData, travail_de_nuit: e.target.checked })}
              className="rounded bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-amber-500 focus:ring-0 w-4 h-4"
            />
            <label htmlFor="travail_nuit" className="text-xs text-slate-700 dark:text-slate-300 cursor-pointer">
              Travail de nuit ou horaires décalés prévus (soumis à autorisation municipale et acoustique)
            </label>
          </div>
        </div>
      )}

      {/* Tab 2: Matériels */}
      {activeTab === 'materiels' && (
        <div className="space-y-3">
          <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
            Parc matériel lourd affecté (Grues à tour, pelles, banches de coffrage)
          </label>
          <textarea
            rows={4}
            value={formData.materiel_principal}
            onChange={(e) => setFormData({ ...formData, materiel_principal: e.target.value })}
            className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 rounded-lg p-3 text-xs text-slate-900 dark:text-slate-200 focus:outline-none focus:border-amber-500 leading-relaxed"
            placeholder="Ex : Grue à tour Potain MDT 219 (flèche 50m), 2 pelles Liebherr 22t..."
          />
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            Ces spécifications matérielles seront automatiquement injectées dans la section 2 et la notice de levage.
          </p>
        </div>
      )}

      {/* Tab 3: Encadrement & CVs */}
      {activeTab === 'cadres' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">Équipe d’encadrement dédiée au chantier</p>
            <button
              onClick={addCadre}
              className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-300 font-semibold"
            >
              <Plus className="w-3.5 h-3.5" /> Ajouter un cadre
            </button>
          </div>

          <div className="space-y-3">
            {formData.equipe_cadres.map((cadre, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800/80 grid grid-cols-1 md:grid-cols-4 gap-3 items-center"
              >
                <div>
                  <label className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold">Nom & Prénom</label>
                  <input
                    type="text"
                    value={cadre.nom}
                    onChange={(e) => {
                      const updated = [...formData.equipe_cadres];
                      updated[idx].nom = e.target.value;
                      setFormData({ ...formData, equipe_cadres: updated });
                    }}
                    className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded p-1.5 text-xs text-slate-900 dark:text-slate-200"
                    placeholder="Jean Dupont"
                  />
                </div>

                <div>
                  <label className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold">Rôle sur chantier</label>
                  <input
                    type="text"
                    value={cadre.role}
                    onChange={(e) => {
                      const updated = [...formData.equipe_cadres];
                      updated[idx].role = e.target.value;
                      setFormData({ ...formData, equipe_cadres: updated });
                    }}
                    className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded p-1.5 text-xs text-slate-900 dark:text-slate-200"
                    placeholder="Conducteur de Travaux"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold">Exp. (ans)</label>
                    <input
                      type="number"
                      value={cadre.experience_ans}
                      onChange={(e) => {
                        const updated = [...formData.equipe_cadres];
                        updated[idx].experience_ans = parseInt(e.target.value) || 0;
                        setFormData({ ...formData, equipe_cadres: updated });
                      }}
                      className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded p-1.5 text-xs text-slate-900 dark:text-slate-200"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold">% Présence</label>
                    <input
                      type="number"
                      value={cadre.presence_hebdo_pct}
                      onChange={(e) => {
                        const updated = [...formData.equipe_cadres];
                        updated[idx].presence_hebdo_pct = parseInt(e.target.value) || 100;
                        setFormData({ ...formData, equipe_cadres: updated });
                      }}
                      className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded p-1.5 text-xs text-slate-900 dark:text-slate-200"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between gap-2 pt-3 md:pt-0">
                  <div className="flex-1">
                    <label className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold">Diplôme / Qualif</label>
                    <input
                      type="text"
                      value={cadre.qualif || ''}
                      onChange={(e) => {
                        const updated = [...formData.equipe_cadres];
                        updated[idx].qualif = e.target.value;
                        setFormData({ ...formData, equipe_cadres: updated });
                      }}
                      className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded p-1.5 text-xs text-slate-900 dark:text-slate-200"
                      placeholder="ESTP, Master..."
                    />
                  </div>
                  <button
                    onClick={() => removeCadre(idx)}
                    className="text-slate-400 dark:text-slate-500 hover:text-red-500 dark:hover:text-red-400 p-1.5 rounded self-end mb-0.5"
                    title="Supprimer ce cadre"
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
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Démarche RSE & Bétons bas carbone
            </label>
            <textarea
              rows={3}
              value={formData.demarche_rse_environnement}
              onChange={(e) => setFormData({ ...formData, demarche_rse_environnement: e.target.value })}
              className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 rounded-lg p-3 text-xs text-slate-900 dark:text-slate-200 focus:outline-none focus:border-amber-500"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Tri des déchets in situ & Filières de revalorisation locales
            </label>
            <textarea
              rows={3}
              value={formData.gestion_dechets}
              onChange={(e) => setFormData({ ...formData, gestion_dechets: e.target.value })}
              className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 rounded-lg p-3 text-xs text-slate-900 dark:text-slate-200 focus:outline-none focus:border-amber-500"
            />
          </div>
        </div>
      )}

      {/* Tab 5: Sécurité */}
      {activeTab === 'securite' && (
        <div className="space-y-3">
          <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
            Mesures de Sécurité, PPSPS & Plan d’Assurance Qualité (PAQ)
          </label>
          <textarea
            rows={4}
            value={formData.mesures_securite}
            onChange={(e) => setFormData({ ...formData, mesures_securite: e.target.value })}
            className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 rounded-lg p-3 text-xs text-slate-900 dark:text-slate-200 focus:outline-none focus:border-amber-500"
          />
        </div>
      )}

      {/* Tab 6: Phasage */}
      {activeTab === 'phasage' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">Phasage chronologique pour le Gantt</p>
            <button
              onClick={addPhase}
              className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-300 font-semibold"
            >
              <Plus className="w-3.5 h-3.5" /> Ajouter une phase
            </button>
          </div>

          <div className="space-y-2">
            {formData.phasage_travaux.map((phase, idx) => (
              <div
                key={idx}
                className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 grid grid-cols-1 md:grid-cols-12 gap-3 items-center"
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
                    className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded p-1.5 text-xs text-slate-900 dark:text-slate-200"
                    placeholder="Intitulé de la phase"
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
                    className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded p-1.5 text-xs text-slate-900 dark:text-slate-200"
                    placeholder="Semaines"
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
                    className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-800 rounded p-1.5 text-xs text-slate-900 dark:text-slate-200"
                    placeholder="Jalon clé"
                  />
                </div>

                <div className="md:col-span-1 flex justify-end">
                  <button
                    onClick={() => removePhase(idx)}
                    className="text-slate-400 dark:text-slate-500 hover:text-red-500 dark:hover:text-red-400 p-1"
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
