'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Globe,
  ArrowLeft,
  Plus,
  Trash2,
  RotateCcw,
  Pencil,
  Save,
  X,
  Loader2,
  ShieldCheck,
  ExternalLink,
  AlertTriangle,
} from 'lucide-react';
import { api } from '@/lib/api';

interface CountrySource {
  id: string;
  country_code: string;
  portal_name: string;
  portal_url: string;
  portal_type: string;
  reference_law: string | null;
  status: string;
  last_checked_at: string | null;
  created_at: string | null;
}

const COUNTRY_NAMES: Record<string, string> = {
  AE: 'Émirats Arabes Unis',
  DE: 'Allemagne',
  ES: 'Espagne',
  FR: 'France',
  IT: 'Italie',
  LB: 'Liban',
  LU: 'Luxembourg',
  QA: 'Qatar',
  SA: 'Arabie Saoudite',
};

const COUNTRY_CODES = Object.keys(COUNTRY_NAMES);

const EMPTY_FORM = {
  country_code: 'FR',
  portal_name: '',
  portal_url: '',
  portal_type: 'procurement_portal',
  reference_law: '',
};

export default function WhitelistAdminPage() {
  const [sources, setSources] = useState<CountrySource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addForm, setAddForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<CountrySource>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listCountrySourcesAdmin();
      setSources(data);
    } catch (e: any) {
      setError(e?.message || 'Impossible de charger la whitelist réglementaire.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleAdd() {
    if (!addForm.portal_name.trim() || !addForm.portal_url.trim() || !addForm.portal_type.trim()) return;
    setSaving(true);
    try {
      await api.createCountrySourceAdmin({
        ...addForm,
        reference_law: addForm.reference_law.trim() || undefined,
      });
      setAddForm(EMPTY_FORM);
      setShowAddForm(false);
      await load();
    } catch (e: any) {
      setError(e?.message || "Échec de l'ajout du site.");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleStatus(source: CountrySource) {
    setBusyId(source.id);
    try {
      if (source.status === 'active') {
        await api.deleteCountrySourceAdmin(source.id);
      } else {
        await api.updateCountrySourceAdmin(source.id, { status: 'active' });
      }
      await load();
    } catch (e: any) {
      setError(e?.message || 'Échec de la mise à jour du statut.');
    } finally {
      setBusyId(null);
    }
  }

  function startEdit(source: CountrySource) {
    setEditingId(source.id);
    setEditForm({
      portal_name: source.portal_name,
      portal_url: source.portal_url,
      portal_type: source.portal_type,
      reference_law: source.reference_law || '',
      country_code: source.country_code,
    });
  }

  async function saveEdit(id: string) {
    setSaving(true);
    try {
      await api.updateCountrySourceAdmin(id, editForm);
      setEditingId(null);
      await load();
    } catch (e: any) {
      setError(e?.message || "Échec de l'enregistrement.");
    } finally {
      setSaving(false);
    }
  }

  const grouped = sources.reduce<Record<string, CountrySource[]>>((acc, s) => {
    (acc[s.country_code] = acc[s.country_code] || []).push(s);
    return acc;
  }, {});
  const countryOrder = Object.keys(grouped).sort();

  return (
    <div className="space-y-6 pb-12">
      <div>
        <Link href="/admin" className="text-xs text-rose-400 hover:underline flex items-center gap-1 mb-3 w-fit">
          <ArrowLeft className="w-3.5 h-3.5" />
          Retour au dashboard
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-white flex items-center gap-2.5">
              <Globe className="w-6 h-6 text-rose-400" />
              Whitelist Réglementaire
            </h1>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl">
              Sites officiels autorisés, par pays. L'IA ne peut restreindre sa recherche web (génération de
              sections, chat DCE) qu'à ces domaines exacts — aucune source hors de cette liste ne peut jamais
              être citée, et un pays sans site actif ici obtient zéro résultat web plutôt qu'un repli non
              restreint vers l'internet ouvert.
            </p>
          </div>
          <button
            onClick={() => setShowAddForm((v) => !v)}
            className="shrink-0 flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-bold border bg-rose-500/15 border-rose-500/40 text-rose-300 hover:bg-rose-500/25 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Ajouter un site</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {showAddForm && (
        <div className="p-4 rounded-2xl bg-[#0D1220] border border-[#1E293F] space-y-3">
          <p className="text-xs font-bold text-white">Nouveau site officiel</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-[10px] text-slate-400 uppercase font-semibold">Pays</label>
              <select
                value={addForm.country_code}
                onChange={(e) => setAddForm({ ...addForm, country_code: e.target.value })}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
              >
                {COUNTRY_CODES.map((c) => (
                  <option key={c} value={c}>{COUNTRY_NAMES[c]} ({c})</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-slate-400 uppercase font-semibold">Type de portail</label>
              <input
                type="text"
                value={addForm.portal_type}
                onChange={(e) => setAddForm({ ...addForm, portal_type: e.target.value })}
                placeholder="procurement_portal, legal_gazette, building_code..."
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
              />
            </div>
            <div className="space-y-1 md:col-span-2">
              <label className="text-[10px] text-slate-400 uppercase font-semibold">Nom du portail</label>
              <input
                type="text"
                value={addForm.portal_name}
                onChange={(e) => setAddForm({ ...addForm, portal_name: e.target.value })}
                placeholder="Ex : BOAMP (Bulletin Officiel des Annonces des Marchés Publics)"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
              />
            </div>
            <div className="space-y-1 md:col-span-2">
              <label className="text-[10px] text-slate-400 uppercase font-semibold">URL officielle</label>
              <input
                type="text"
                value={addForm.portal_url}
                onChange={(e) => setAddForm({ ...addForm, portal_url: e.target.value })}
                placeholder="https://www.exemple-officiel.gouv"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
              />
            </div>
            <div className="space-y-1 md:col-span-2">
              <label className="text-[10px] text-slate-400 uppercase font-semibold">Référence légale (optionnel)</label>
              <input
                type="text"
                value={addForm.reference_law}
                onChange={(e) => setAddForm({ ...addForm, reference_law: e.target.value })}
                placeholder="Ex : Code de la commande publique"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={handleAdd}
              disabled={saving}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-50 transition-all"
            >
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              <span>Enregistrer</span>
            </button>
            <button
              onClick={() => { setShowAddForm(false); setAddForm(EMPTY_FORM); }}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-bold text-slate-400 hover:text-slate-200"
            >
              <X className="w-3.5 h-3.5" />
              <span>Annuler</span>
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16 text-slate-500 text-xs gap-2">
          <Loader2 className="w-4 h-4 animate-spin" />
          Chargement de la whitelist...
        </div>
      ) : countryOrder.length === 0 ? (
        <div className="p-8 text-center text-slate-500 text-xs rounded-2xl border border-dashed border-slate-800">
          Aucun site enregistré pour l'instant.
        </div>
      ) : (
        countryOrder.map((code) => (
          <div key={code} className="space-y-2">
            <p className="text-xs font-extrabold uppercase tracking-widest text-slate-500 px-1">
              {COUNTRY_NAMES[code] || code} <span className="text-slate-600">({code})</span>
            </p>
            <div className="rounded-2xl border border-[#1E293F] overflow-hidden divide-y divide-[#1E293F]">
              {grouped[code].map((s) => (
                <div key={s.id} className="p-3.5 bg-[#0D1220] flex flex-col gap-2">
                  {editingId === s.id ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      <input
                        value={editForm.portal_name || ''}
                        onChange={(e) => setEditForm({ ...editForm, portal_name: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded p-1.5 text-xs text-slate-200 md:col-span-2"
                        placeholder="Nom du portail"
                      />
                      <input
                        value={editForm.portal_url || ''}
                        onChange={(e) => setEditForm({ ...editForm, portal_url: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded p-1.5 text-xs text-slate-200 md:col-span-2"
                        placeholder="URL officielle"
                      />
                      <input
                        value={editForm.portal_type || ''}
                        onChange={(e) => setEditForm({ ...editForm, portal_type: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded p-1.5 text-xs text-slate-200"
                        placeholder="Type de portail"
                      />
                      <input
                        value={editForm.reference_law || ''}
                        onChange={(e) => setEditForm({ ...editForm, reference_law: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded p-1.5 text-xs text-slate-200"
                        placeholder="Référence légale"
                      />
                      <div className="flex items-center gap-2 md:col-span-2 pt-1">
                        <button
                          onClick={() => saveEdit(s.id)}
                          disabled={saving}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[11px] font-bold bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-50"
                        >
                          <Save className="w-3 h-3" /> Enregistrer
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[11px] font-bold text-slate-400 hover:text-slate-200"
                        >
                          <X className="w-3 h-3" /> Annuler
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-bold text-white">{s.portal_name}</span>
                          <span
                            className={`text-[9px] uppercase font-extrabold px-1.5 py-0.5 rounded ${
                              s.status === 'active'
                                ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                                : 'bg-slate-700/30 text-slate-400 border border-slate-700/50'
                            }`}
                          >
                            {s.status === 'active' ? 'Actif' : 'Inactif'}
                          </span>
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800/60 text-slate-400">
                            {s.portal_type}
                          </span>
                        </div>
                        <a
                          href={s.portal_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[11px] text-sky-400 hover:underline flex items-center gap-1 mt-0.5 truncate"
                        >
                          {s.portal_url}
                          <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                        </a>
                        {s.reference_law && (
                          <p className="text-[10px] text-slate-500 mt-0.5">{s.reference_law}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          onClick={() => startEdit(s)}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800/60"
                          title="Modifier"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleToggleStatus(s)}
                          disabled={busyId === s.id}
                          className={`p-1.5 rounded-lg disabled:opacity-50 ${
                            s.status === 'active'
                              ? 'text-slate-500 hover:text-red-400 hover:bg-red-500/10'
                              : 'text-slate-500 hover:text-emerald-400 hover:bg-emerald-500/10'
                          }`}
                          title={s.status === 'active' ? 'Désactiver' : 'Réactiver'}
                        >
                          {busyId === s.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : s.status === 'active' ? (
                            <Trash2 className="w-3.5 h-3.5" />
                          ) : (
                            <RotateCcw className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))
      )}

      <div className="flex items-start gap-2 p-3 rounded-lg bg-slate-800/30 border border-slate-800 text-[11px] text-slate-500">
        <ShieldCheck className="w-3.5 h-3.5 shrink-0 mt-0.5 text-slate-600" />
        <span>
          Un pays sans aucun site "Actif" ici fait obtenir zéro résultat de recherche web à l'IA pour ce pays
          (jamais un repli vers l'internet ouvert). Désactiver un site le retire immédiatement de la
          restriction utilisée par la génération de sections et le chat DCE.
        </span>
      </div>
    </div>
  );
}
