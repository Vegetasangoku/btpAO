'use client';

import React from 'react';
import Link from 'next/link';
import { AlertTriangle, ChevronRight } from 'lucide-react';
import { GoNoGoAnalysis } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

/**
 * 11/09 : une conclusion « suspendue » ne disait ni pourquoi ni quoi faire.
 * Ce bloc affiche les raisons (rédigées par le serveur dans la langue de
 * l'interface) et les actions à mener, chacune avec un lien.
 */
export type EtatGoNoGo = 'go' | 'no_go' | 'suspendue' | 'reserves';

export function etatGoNoGo(a?: Partial<GoNoGoAnalysis> | null): EtatGoNoGo | null {
  if (!a) return null;
  if (a.etat) return a.etat;
  const r = String(a.recommendation || '').toUpperCase().replace('-', '_');
  return r === 'GO' ? 'go' : r === 'NO_GO' ? 'no_go' : 'reserves';
}

export function useLibelleEtat() {
  const { t } = useTranslation();
  return (e: EtatGoNoGo | null) =>
    e === 'go'
      ? t('projects.export.gonogo_go')
      : e === 'no_go'
      ? t('projects.export.gonogo_nogo')
      : e === 'suspendue'
      ? t('projects.export.gonogo_suspendue')
      : t('projects.export.gonogo_reserves');
}

export function couleurEtat(e: EtatGoNoGo | null): string {
  return e === 'go' ? 'text-positive' : e === 'no_go' ? 'text-danger' : e === 'suspendue' ? 'text-muted-foreground' : 'text-hl';
}

export function GoNoGoExplication({ analysis }: { analysis: GoNoGoAnalysis }) {
  const { t } = useTranslation();
  const etat = etatGoNoGo(analysis);
  return (
    <div className="space-y-3">
      {analysis.raisons && analysis.raisons.length > 0 && (
        <div className="p-4 rounded-xl border border-line space-y-2">
          <p className="text-xs font-bold text-foreground">
            {etat === 'suspendue' ? t('projects.export.gonogo_pourquoi_suspendue') : t('projects.export.gonogo_pourquoi')}
          </p>
          <ul className="space-y-1.5">
            {analysis.raisons.map((r, i) => (
              <li key={i} className="text-[11px] text-muted-foreground flex gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px text-warning" /> <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {analysis.actions && analysis.actions.length > 0 && (
        <div className="p-4 rounded-xl border border-hl/30 bg-hl/5 space-y-2">
          <p className="text-xs font-bold text-foreground">{t('projects.export.gonogo_que_faire')}</p>
          <ol className="space-y-2">
            {analysis.actions.map((a, i) => (
              <li key={i} className="text-[11px] flex flex-wrap items-start justify-between gap-2">
                <span className="text-foreground">
                  <strong>{i + 1}. {a.texte}</strong>
                  {a.detail ? <span className="text-muted-foreground"> — {a.detail}</span> : null}
                </span>
                {a.lien && (
                  <Link href={a.lien} className="btn-secondary !py-1 !px-2.5 !text-[11px] shrink-0">
                    {t('projects.export.gonogo_y_aller')} <ChevronRight className="w-3 h-3" />
                  </Link>
                )}
              </li>
            ))}
          </ol>
          <p className="text-[10px] text-muted-foreground">{t('projects.export.gonogo_apres')}</p>
        </div>
      )}
    </div>
  );
}
