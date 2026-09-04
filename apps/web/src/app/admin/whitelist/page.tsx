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
import { useTranslation } from '@/components/i18n-provider';

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
  NL: 'Pays-Bas',
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
  const { t } = useTranslation();
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
      setError(t('admin.whitelist.error_load'));
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
      setError(t('admin.whitelist.error_add'));
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
      setError(t('admin.whitelist.error_toggle'));
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
      setError(t('admin.whitelist.error_save'));
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
    <div className="space-y-6 pb-12 max-w-5xl">
      <div>
        <Link href="/admin" className="text-xs text-hl hover:underline flex items-center gap-1 mb-3 w-fit">
          <ArrowLeft className="w-3.5 h-3.5" />
          {t('admin.whitelist.back_dashboard')}
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="badge-pill font-medium flex items-center gap-1.5">
                <Globe className="w-3.5 h-3.5 text-hl" />
                Whitelist Sources
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-foreground font-heading tracking-tight">
              {t('admin.whitelist.heading')}
            </h1>
            <p className="text-xs text-muted-foreground mt-1 max-w-2xl font-medium">
              {t('admin.whitelist.subtitle')}
            </p>
          </div>
          <button
            onClick={() => setShowAddForm((v) => !v)}
            className="btn-primary !py-2 !px-4 !text-xs shrink-0 cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>{t('admin.whitelist.btn_add_site')}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-danger/10 border border-danger/30 text-danger text-xs flex items-center gap-2 font-medium">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {showAddForm && (
        <div className="p-5 rounded-2xl bg-card border border-line space-y-3.5 shadow-xs">
          <p className="text-xs font-bold text-foreground font-heading">{t('admin.whitelist.new_site_title')}</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground uppercase font-mono font-bold">{t('admin.whitelist.label_country')}</label>
              <select
                value={addForm.country_code}
                onChange={(e) => setAddForm({ ...addForm, country_code: e.target.value })}
                className="w-full bg-sunken border border-line rounded-xl p-2.5 text-xs text-foreground focus:border-hl focus:outline-none font-medium cursor-pointer"
              >
                {COUNTRY_CODES.map((c) => (
                  <option key={c} value={c}>{COUNTRY_NAMES[c]} ({c})</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground uppercase font-mono font-bold">{t('admin.whitelist.label_portal_type')}</label>
              <input
                type="text"
                value={addForm.portal_type}
                onChange={(e) => setAddForm({ ...addForm, portal_type: e.target.value })}
                placeholder={t('admin.whitelist.placeholder_portal_type')}
                className="w-full bg-sunken border border-line rounded-xl p-2.5 text-xs text-foreground focus:border-hl focus:outline-none font-medium"
              />
            </div>
            <div className="space-y-1 md:col-span-2">
              <label className="text-[10px] text-muted-foreground uppercase font-mono font-bold">{t('admin.whitelist.label_portal_name')}</label>
              <input
                type="text"
                value={addForm.portal_name}
                onChange={(e) => setAddForm({ ...addForm, portal_name: e.target.value })}
                placeholder={t('admin.whitelist.placeholder_portal_name')}
                className="w-full bg-sunken border border-line rounded-xl p-2.5 text-xs text-foreground focus:border-hl focus:outline-none font-medium"
              />
            </div>
            <div className="space-y-1 md:col-span-2">
              <label className="text-[10px] text-muted-foreground uppercase font-mono font-bold">{t('admin.whitelist.label_url')}</label>
              <input
                type="text"
                value={addForm.portal_url}
                onChange={(e) => setAddForm({ ...addForm, portal_url: e.target.value })}
                placeholder="https://www.exemple-officiel.gouv"
                className="w-full bg-sunken border border-line rounded-xl p-2.5 text-xs text-foreground focus:border-hl focus:outline-none font-mono"
              />
            </div>
            <div className="space-y-1 md:col-span-2">
              <label className="text-[10px] text-muted-foreground uppercase font-mono font-bold">{t('admin.whitelist.label_reference_law')}</label>
              <input
                type="text"
                value={addForm.reference_law}
                onChange={(e) => setAddForm({ ...addForm, reference_law: e.target.value })}
                placeholder={t('admin.whitelist.placeholder_reference_law')}
                className="w-full bg-sunken border border-line rounded-xl p-2.5 text-xs text-foreground focus:border-hl focus:outline-none font-medium"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={handleAdd}
              disabled={saving}
              className="btn-primary !py-2 !px-4 !text-xs cursor-pointer"
            >
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              <span>{t('admin.whitelist.btn_save')}</span>
            </button>
            <button
              onClick={() => { setShowAddForm(false); setAddForm(EMPTY_FORM); }}
              className="btn-secondary !py-2 !px-4 !text-xs cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
              <span>{t('admin.whitelist.btn_cancel')}</span>
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16 text-muted-foreground text-xs gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-hl" />
          {t('admin.whitelist.loading')}
        </div>
      ) : countryOrder.length === 0 ? (
        <div className="p-8 text-center text-muted-foreground text-xs rounded-2xl border border-dashed border-line">
          {t('admin.whitelist.empty')}
        </div>
      ) : (
        countryOrder.map((code) => (
          <div key={code} className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground px-1 font-mono">
              {COUNTRY_NAMES[code] || code} <span className="text-muted-foreground font-normal">({code})</span>
            </p>
            <div className="rounded-2xl border border-line overflow-hidden divide-y divide-line bg-card shadow-xs">
              {grouped[code].map((s) => (
                <div key={s.id} className="p-4 flex flex-col gap-2">
                  {editingId === s.id ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                      <input
                        value={editForm.portal_name || ''}
                        onChange={(e) => setEditForm({ ...editForm, portal_name: e.target.value })}
                        className="w-full bg-sunken border border-line rounded-xl p-2 text-xs text-foreground md:col-span-2 focus:border-hl focus:outline-none"
                        placeholder="Nom du portail"
                      />
                      <input
                        value={editForm.portal_url || ''}
                        onChange={(e) => setEditForm({ ...editForm, portal_url: e.target.value })}
                        className="w-full bg-sunken border border-line rounded-xl p-2 text-xs text-foreground md:col-span-2 focus:border-hl focus:outline-none font-mono"
                        placeholder="URL officielle"
                      />
                      <input
                        value={editForm.portal_type || ''}
                        onChange={(e) => setEditForm({ ...editForm, portal_type: e.target.value })}
                        className="w-full bg-sunken border border-line rounded-xl p-2 text-xs text-foreground focus:border-hl focus:outline-none"
                        placeholder="Type de portail"
                      />
                      <input
                        value={editForm.reference_law || ''}
                        onChange={(e) => setEditForm({ ...editForm, reference_law: e.target.value })}
                        className="w-full bg-sunken border border-line rounded-xl p-2 text-xs text-foreground focus:border-hl focus:outline-none"
                        placeholder="Référence légale"
                      />
                      <div className="flex items-center gap-2 md:col-span-2 pt-1">
                        <button
                          onClick={() => saveEdit(s.id)}
                          disabled={saving}
                          className="btn-primary !py-1.5 !px-3 !text-xs cursor-pointer"
                        >
                          <Save className="w-3 h-3" /> {t('admin.whitelist.btn_save')}
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="btn-secondary !py-1.5 !px-3 !text-xs cursor-pointer"
                        >
                          <X className="w-3 h-3" /> {t('admin.whitelist.btn_cancel')}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-bold text-foreground font-heading">{s.portal_name}</span>
                          <span
                            className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded border ${
                              s.status === 'active'
                                ? 'bg-positive/10 text-positive border-positive/25'
                                : 'bg-sunken text-muted-foreground border-line'
                            }`}
                          >
                            {s.status === 'active' ? t('admin.whitelist.status_active') : t('admin.whitelist.status_inactive')}
                          </span>
                          <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-sunken text-muted-foreground border border-line">
                            {s.portal_type}
                          </span>
                        </div>
                        <a
                          href={s.portal_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[11px] text-hl hover:underline flex items-center gap-1 mt-0.5 truncate font-mono"
                        >
                          {s.portal_url}
                          <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                        </a>
                        {s.reference_law && (
                          <p className="text-[10px] text-muted-foreground mt-0.5">{s.reference_law}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          onClick={() => startEdit(s)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 hover:bg-slate-100 dark:hover:bg-raised cursor-pointer transition-colors"
                          title={t('admin.whitelist.title_edit')}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleToggleStatus(s)}
                          disabled={busyId === s.id}
                          className={`p-1.5 rounded-lg disabled:opacity-50 cursor-pointer transition-colors ${
                            s.status === 'active'
                              ? 'text-slate-400 hover:text-danger hover:bg-danger/10'
                              : 'text-slate-400 hover:text-positive hover:bg-positive/10'
                          }`}
                          title={s.status === 'active' ? t('admin.whitelist.title_deactivate') : t('admin.whitelist.title_reactivate')}
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

      <div className="flex items-start gap-2 p-3 rounded-2xl bg-card border border-line text-[11px] text-muted-foreground shadow-xs">
        <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5 text-hl" />
        <span>
          {t('admin.whitelist.footer_note')}
        </span>
      </div>
    </div>
  );
}
