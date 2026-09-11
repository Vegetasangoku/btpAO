'use client';

import React, { useState } from 'react';
import { api } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';

/** 11/09 : indiquer l'issue d'un appel d'offres (l'historique du Go/No-Go en dépend). */
export function OutcomeSelect({
  projectId,
  value,
  onSaved,
}: {
  projectId: string;
  value?: string | null;
  onSaved?: (o: string) => void;
}) {
  const { t } = useTranslation();
  const [v, setV] = useState(value || 'pending');
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState(false);

  async function changer(o: string) {
    const avant = v;
    setV(o);
    setEnCours(true);
    setErreur(false);
    try {
      await api.recordOutcome(projectId, o);
      onSaved?.(o);
    } catch {
      setV(avant);
      setErreur(true);
    } finally {
      setEnCours(false);
    }
  }

  return (
    <label className="text-[11px] text-muted-foreground flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
      <span>{t('outcome.label')}</span>
      <select
        value={v}
        disabled={enCours}
        onChange={(e) => changer(e.target.value)}
        className={`input-field !py-0.5 !px-1.5 !text-[11px] !w-auto ${erreur ? '!border-danger' : ''}`}
      >
        <option value="pending">{t('outcome.pending')}</option>
        <option value="won">{t('outcome.won')}</option>
        <option value="lost">{t('outcome.lost')}</option>
        <option value="withdrawn">{t('outcome.withdrawn')}</option>
      </select>
    </label>
  );
}
