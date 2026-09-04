'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Globe2, Loader2, AlertTriangle, CheckCircle2, RefreshCw, Info } from 'lucide-react';
import { api } from '@/lib/api';
import { ProjectCountryState } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

/**
 * Pays du marche applique au dossier (04/09).
 *
 * Ce bandeau existe parce que le cadre reglementaire (normes, regime de commande publique,
 * qualifications reconnues, whitelist de sources officielles) change TOUT le contenu genere.
 * Jusqu'ici il etait pris sur le pays de l'ENTREPRISE, jamais sur celui du marche : une
 * entreprise francaise repondant au Qatar recevait des normes francaises, en silence.
 *
 * Regle de conception : on n'applique jamais un cadre reglementaire sans le dire. Le pays
 * retenu, son origine (detecte / corrige a la main / repli sur le pays de l'entreprise) et
 * les indices qui ont conduit a ce choix sont toujours affiches, et corrigeables en un clic.
 */
export function ProjectCountryBanner({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const [state, setState] = useState<ProjectCountryState | null>(null);
  const [busy, setBusy] = useState(false);
  const [showWhy, setShowWhy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setState(await api.getProjectCountry(projectId));
    } catch (err) {
      console.error('Failed to load project country', err);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  async function runDetection() {
    setBusy(true);
    setError(null);
    try {
      setState(await api.detectProjectCountry(projectId));
      setShowWhy(true);
    } catch (err: any) {
      console.error('Country detection failed', err);
      setError(err?.message || t('projects.country.action_failed'));
    } finally {
      setBusy(false);
    }
  }

  async function override(code: string) {
    setBusy(true);
    setError(null);
    try {
      setState(await api.setProjectCountry(projectId, code || null));
    } catch (err: any) {
      console.error('Country override failed', err);
      setError(err?.message || t('projects.country.action_failed'));
    } finally {
      setBusy(false);
    }
  }

  if (!state) return null;

  const detection = state.detection || {};
  const isFallback = state.is_tenant_fallback;
  const overridden = Boolean(detection.overridden_by_user);
  const current = state.available_countries.find((c) => c.country_code === state.effective_country_code);
  const label = current ? current.country_name : state.effective_country_code;

  // Le repli silencieux est le cas a signaler : le dossier est traite avec le cadre du pays
  // de l'entreprise faute de mieux, ce qui est un defaut, pas une decision.
  const tone = isFallback ? 'border-warn/40 bg-warn/8' : 'border-line bg-card';

  return (
    <div className={`rounded-xl border ${tone} p-3.5 space-y-2.5 text-xs`}>
      <div className="flex flex-wrap items-center gap-2">
        <Globe2 className="w-4 h-4 text-hl shrink-0" />
        <span className="font-semibold text-foreground">
          {t('projects.country.title')} <strong className="text-hl">{label}</strong>
        </span>

        {overridden ? (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-hl/15 text-hl">
            {t('projects.country.badge_manual')}
          </span>
        ) : isFallback ? (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-warn/20 text-warn inline-flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> {t('projects.country.badge_fallback')}
          </span>
        ) : (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-positive/15 text-positive inline-flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> {t('projects.country.badge_detected')}
          </span>
        )}

        <div className="ml-auto flex items-center gap-2">
          {detection.reason && (
            <button
              type="button"
              onClick={() => setShowWhy((v) => !v)}
              className="text-[11px] text-muted-foreground hover:text-hl inline-flex items-center gap-1 cursor-pointer"
            >
              <Info className="w-3 h-3" /> {t('projects.country.why')}
            </button>
          )}
          <button
            type="button"
            onClick={runDetection}
            disabled={busy}
            className="px-2.5 py-1 rounded-lg border border-line text-[11px] font-semibold hover:text-hl disabled:opacity-50 cursor-pointer inline-flex items-center gap-1"
          >
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            {t('projects.country.detect_btn')}
          </button>
        </div>
      </div>

      {isFallback && (
        <p className="text-[11px] text-muted-foreground">
          {t('projects.country.fallback_hint', { country: state.tenant_country_code })}
        </p>
      )}

      {showWhy && detection.reason && (
        <div className="rounded-lg bg-bg/60 border border-line p-2.5 space-y-1.5">
          <p className="text-[11px] text-foreground">{detection.reason}</p>
          {Array.isArray(detection.signals) && detection.signals.length > 0 && (
            <ul className="space-y-0.5">
              {detection.signals.map((s, i) => (
                <li key={i} className="text-[10px] text-muted-foreground font-mono">
                  · <strong className="text-foreground">{s.marker}</strong> — {s.kind}, {s.where}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground font-semibold">
          {t('projects.country.override_label')}
        </span>
        <select
          value={state.country_code || ''}
          onChange={(e) => override(e.target.value)}
          disabled={busy}
          className="bg-card border border-line rounded-lg px-2 py-1 text-[11px] text-foreground disabled:opacity-50 cursor-pointer"
        >
          <option value="">{t('projects.country.use_tenant_option', { country: state.tenant_country_code })}</option>
          {state.available_countries.map((c) => (
            <option key={c.country_code} value={c.country_code}>
              {c.country_name} ({c.country_code})
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p className="text-[11px] text-danger inline-flex items-center gap-1">
          <AlertTriangle className="w-3 h-3 shrink-0" /> {error}
        </p>
      )}
    </div>
  );
}
