'use client';

import React, { useEffect, useState } from 'react';
import { Building2, X } from 'lucide-react';
import { lireEspaceConsulte, ecrireEspaceConsulte, type EspaceConsulte } from '@/lib/espace-actif';
import { useTranslation } from '@/components/i18n-provider';

/**
 * Rappel permanent : « vous n'êtes pas chez vous ».
 *
 * Quand un administrateur inspecte l'espace d'un client, il doit le savoir à
 * chaque écran — pas seulement au moment où il a cliqué. Sans ce rappel, le
 * 10/09, l'administrateur a travaillé dans les données d'un client en croyant
 * être dans les siennes, et rien à l'écran ne le contredisait.
 */
export function BanniereEspaceConsulte() {
  const { t } = useTranslation();
  const [espace, setEspace] = useState<EspaceConsulte>(null);

  useEffect(() => {
    setEspace(lireEspaceConsulte());
    // Un autre onglet peut changer l'espace consulté : rester synchronisé.
    const surStockage = () => setEspace(lireEspaceConsulte());
    window.addEventListener('storage', surStockage);
    return () => window.removeEventListener('storage', surStockage);
  }, []);

  if (!espace) return null;

  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 bg-hl/12 border-b border-hl/30"
    >
      <p className="flex items-center gap-2 text-[12px] text-foreground min-w-0">
        <Building2 className="w-4 h-4 text-hl shrink-0" />
        <span className="truncate">{t('espace.banniere_inspection', { nom: espace.nom })}</span>
      </p>
      <button
        type="button"
        onClick={() => {
          ecrireEspaceConsulte(null);
          window.location.href = '/admin';
        }}
        className="btn-secondary !py-1 !px-2.5 !text-[11px] shrink-0 cursor-pointer"
      >
        <X className="w-3 h-3" />
        <span>{t('espace.revenir_au_mien')}</span>
      </button>
    </div>
  );
}
