'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { Plus, Trash2, Loader2, Sparkles, AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import { api } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';

interface PricingLine {
  id: string;
  lot?: string | null;
  designation: string;
  unite: string;
  quantite: number;
  prix_unitaire_ht: number;
  total_ht: number;
}

interface PricingSummary {
  lines_count: number;
  total_ht_brut: number;
  taux_inflation_pct: number;
  risk_contingency_pct: number;
  marge_cible_pct: number;
  total_apres_inflation_ht: number;
  total_apres_alea_ht: number;
  total_avec_marge_ht: number;
  tva_pct: number;
  total_ttc: number;
  formule: string;
}

const fmt = (n: number) =>
  (n ?? 0).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function PricingChiffrage({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const [lines, setLines] = useState<PricingLine[]>([]);
  const [summary, setSummary] = useState<PricingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState({ lot: '', designation: '', unite: 'u', quantite: '', prix_unitaire_ht: '' });
  const [analysis, setAnalysis] = useState<any>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [linesData, summaryData] = await Promise.all([
        api.getPricingLines(projectId),
        api.getPricingSummary(projectId),
      ]);
      setLines(linesData || []);
      setSummary(summaryData || null);
    } catch (e) {
      console.warn('[PricingChiffrage] refresh failed', e);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleAddLine(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.designation.trim() || !draft.quantite || !draft.prix_unitaire_ht) return;
    setSaving(true);
    try {
      await api.createPricingLine(projectId, {
        lot: draft.lot || undefined,
        designation: draft.designation,
        unite: draft.unite || 'u',
        quantite: parseFloat(draft.quantite),
        prix_unitaire_ht: parseFloat(draft.prix_unitaire_ht),
      });
      setDraft({ lot: '', designation: '', unite: 'u', quantite: '', prix_unitaire_ht: '' });
      await refresh();
    } catch (e) {
      console.warn('[PricingChiffrage] add line failed', e);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteLine(id: string) {
    try {
      await api.deletePricingLine(id);
      await refresh();
    } catch (e) {
      console.warn('[PricingChiffrage] delete failed', e);
    }
  }

  async function handleAnalyze() {
    setAnalyzing(true);
    setAnalysis(null);
    try {
      const result = await api.analyzePricing(projectId);
      setAnalysis(result);
    } catch (e) {
      setAnalysis({ status: 'error', message: String(e) });
    } finally {
      setAnalyzing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-[13px] text-muted-foreground font-mono">
        <Loader2 className="w-6 h-6 animate-spin text-hl" />
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      <div>
        <h1 className="text-2xl font-extrabold text-foreground">{t('projects.pricing.heading')}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">{t('projects.pricing.subtitle')}</p>
        <p className="text-[11px] text-muted-foreground mt-1 flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5 shrink-0" />
          {t('projects.pricing.settings_link')}{' '}
          <Link href="/dashboard/settings" className="text-hl hover:underline">
            →
          </Link>
        </p>
      </div>

      {/* Lines table */}
      <div className="card-modern p-6 rounded-2xl space-y-4">
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-muted-foreground border-b border-line">
                <th className="py-2 pr-3 font-semibold">{t('projects.pricing.col_lot')}</th>
                <th className="py-2 pr-3 font-semibold">{t('projects.pricing.col_designation')}</th>
                <th className="py-2 pr-3 font-semibold">{t('projects.pricing.col_unite')}</th>
                <th className="py-2 pr-3 font-semibold text-right">{t('projects.pricing.col_quantite')}</th>
                <th className="py-2 pr-3 font-semibold text-right">{t('projects.pricing.col_pu')}</th>
                <th className="py-2 pr-3 font-semibold text-right">{t('projects.pricing.col_total')}</th>
                <th className="py-2 w-8" />
              </tr>
            </thead>
            <tbody>
              {lines.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-muted-foreground text-[12px]">
                    {t('projects.pricing.empty')}
                  </td>
                </tr>
              )}
              {lines.map((l) => (
                <tr key={l.id} className="border-b border-line last:border-0">
                  <td className="py-2 pr-3 text-muted-foreground">{l.lot || '—'}</td>
                  <td className="py-2 pr-3 font-medium text-foreground">{l.designation}</td>
                  <td className="py-2 pr-3 text-muted-foreground">{l.unite}</td>
                  <td className="py-2 pr-3 text-right font-mono tabular-nums">{fmt(l.quantite)}</td>
                  <td className="py-2 pr-3 text-right font-mono tabular-nums">{fmt(l.prix_unitaire_ht)} €</td>
                  <td className="py-2 pr-3 text-right font-mono tabular-nums font-semibold text-foreground">{fmt(l.total_ht)} €</td>
                  <td className="py-2">
                    <button
                      type="button"
                      onClick={() => handleDeleteLine(l.id)}
                      className="text-muted-foreground hover:text-danger transition-colors cursor-pointer"
                      aria-label="Supprimer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <form onSubmit={handleAddLine} className="grid grid-cols-2 sm:grid-cols-6 gap-2 pt-3 border-t border-line">
          <input
            className="input-field text-[12px] col-span-1"
            placeholder={t('projects.pricing.col_lot')}
            value={draft.lot}
            onChange={(e) => setDraft({ ...draft, lot: e.target.value })}
          />
          <input
            className="input-field text-[12px] col-span-2 sm:col-span-2"
            placeholder={t('projects.pricing.col_designation')}
            value={draft.designation}
            onChange={(e) => setDraft({ ...draft, designation: e.target.value })}
          />
          <input
            className="input-field text-[12px]"
            placeholder={t('projects.pricing.col_unite')}
            value={draft.unite}
            onChange={(e) => setDraft({ ...draft, unite: e.target.value })}
          />
          <input
            className="input-field text-[12px]"
            type="number"
            step="0.01"
            placeholder={t('projects.pricing.col_quantite')}
            value={draft.quantite}
            onChange={(e) => setDraft({ ...draft, quantite: e.target.value })}
          />
          <div className="flex gap-2">
            <input
              className="input-field text-[12px]"
              type="number"
              step="0.01"
              placeholder={t('projects.pricing.col_pu')}
              value={draft.prix_unitaire_ht}
              onChange={(e) => setDraft({ ...draft, prix_unitaire_ht: e.target.value })}
            />
            <button type="submit" disabled={saving} className="btn-primary !px-3 shrink-0 cursor-pointer">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            </button>
          </div>
        </form>
      </div>

      {/* Summary */}
      {summary && summary.lines_count > 0 && (
        <div className="card-modern p-6 rounded-2xl space-y-3">
          <h2 className="section-title text-[14px]">{t('projects.pricing.summary_title')}</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[12px]">
            <div className="p-3 rounded-xl bg-sunken">
              <p className="text-muted-foreground">{t('projects.pricing.total_brut')}</p>
              <p className="font-mono font-bold text-foreground text-[14px]">{fmt(summary.total_ht_brut)} €</p>
            </div>
            <div className="p-3 rounded-xl bg-sunken">
              <p className="text-muted-foreground">Inflation ({summary.taux_inflation_pct}%)</p>
              <p className="font-mono tabular-nums">{fmt(summary.total_apres_inflation_ht)} €</p>
            </div>
            <div className="p-3 rounded-xl bg-sunken">
              <p className="text-muted-foreground">Aléas ({summary.risk_contingency_pct}%) + Marge ({summary.marge_cible_pct}%)</p>
              <p className="font-mono tabular-nums">{fmt(summary.total_avec_marge_ht)} €</p>
            </div>
            <div className="p-3 rounded-xl bg-hl/10">
              <p className="text-hl font-medium">{t('projects.pricing.total_ttc')} (TVA {summary.tva_pct}%)</p>
              <p className="font-mono font-bold text-hl text-[15px]">{fmt(summary.total_ttc)} €</p>
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground font-mono">{summary.formule}</p>
        </div>
      )}

      {/* LLM analysis */}
      <div className="card-modern p-6 rounded-2xl space-y-3">
        <button
          type="button"
          onClick={handleAnalyze}
          disabled={analyzing || lines.length === 0}
          className="btn-secondary text-[12px] inline-flex items-center gap-2 cursor-pointer disabled:opacity-50"
        >
          {analyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {analyzing ? t('projects.pricing.analyzing') : t('projects.pricing.analyze_btn')}
        </button>

        {analysis && analysis.status === 'ok' && (
          <div className="p-4 rounded-xl bg-sunken space-y-2 text-[12px]">
            <div className="flex items-center gap-2">
              <span
                className={`badge-pill text-[9px] ${
                  analysis.risk_level === 'high' ? 'bg-danger/10 text-danger' : analysis.risk_level === 'medium' ? 'bg-corten/10 text-corten' : 'bg-positive/10 text-positive'
                }`}
              >
                {analysis.risk_level}
              </span>
              <span className="text-muted-foreground text-[10px] font-mono">{analysis.model_used}</span>
            </div>
            <p className="text-foreground">{analysis.summary}</p>
            {analysis.flagged_lines?.length > 0 && (
              <p className="text-corten">⚠ {analysis.flagged_lines.join(', ')}</p>
            )}
            {analysis.missing_items_suggestions?.length > 0 && (
              <p className="text-muted-foreground">Suggestions : {analysis.missing_items_suggestions.join(', ')}</p>
            )}
          </div>
        )}
        {analysis && analysis.status !== 'ok' && (
          <div className="p-3 rounded-xl bg-corten/8 border border-corten/20 text-corten text-[12px] flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{analysis.message}</span>
          </div>
        )}
      </div>
    </div>
  );
}
