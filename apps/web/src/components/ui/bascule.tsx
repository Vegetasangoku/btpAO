'use client';

import React from 'react';

/**
 * Interrupteur à deux états, lisible sans deviner.
 *
 * Constat du 10/09 : les bascules de la page d'export étaient rendues avec un
 * `<span absolute>` sans `left`, donc positionné après le padding par défaut du
 * `<button>` — la pastille sortait de son rail. Elles se lisaient par ailleurs
 * comme des boutons radio alors que ce sont des interrupteurs indépendants, et
 * rien n'écrivait l'état : « inclus » ou « exclu » se devinait à la couleur.
 *
 * Ici : `role="switch"` (donc annoncé correctement par un lecteur d'écran),
 * pastille calée sur le rail, et l'état écrit en toutes lettres à côté.
 */
export function Bascule({
  actif,
  onChange,
  titre,
  description,
  libelleActif,
  libelleInactif,
  dense = false,
}: {
  actif: boolean;
  onChange: (valeur: boolean) => void;
  titre: string;
  description?: string;
  libelleActif: string;
  libelleInactif: string;
  /** Variante resserrée, pour un panneau étroit (colonne, encart latéral). */
  dense?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={actif}
      onClick={() => onChange(!actif)}
      className={`flex items-center justify-between w-full text-start rounded-xl bg-sunken border border-line hover:border-hl/40 transition-colors cursor-pointer ${
        dense ? 'gap-3 p-2.5' : 'gap-4 p-4'
      }`}
    >
      <span className="min-w-0">
        <span className="block text-xs font-bold text-slate-900 dark:text-zinc-200">{titre}</span>
        {description && !dense && (
          <span className="block text-[11px] text-muted-foreground mt-0.5">{description}</span>
        )}
      </span>
      <span className="flex items-center gap-2 shrink-0">
        <span className={`font-semibold whitespace-nowrap ${dense ? 'text-[10px]' : 'text-[11px]'} ${actif ? 'text-hl' : 'text-muted-foreground'}`}>
          {actif ? libelleActif : libelleInactif}
        </span>
        <span
          aria-hidden
          className={`relative block w-11 h-6 rounded-full transition-colors ${
            actif ? 'bg-hl' : 'bg-slate-300 dark:bg-slate-700'
          }`}
        >
          <span
            className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${
              actif ? 'translate-x-5' : 'translate-x-0'
            }`}
          />
        </span>
      </span>
    </button>
  );
}
