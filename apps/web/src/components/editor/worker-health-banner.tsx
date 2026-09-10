'use client';

import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';

/**
 * Avertissement quand le moteur de rédaction ne peut pas faire son travail (10/09).
 *
 * Deux situations réellement bloquantes, et jusqu'ici parfaitement silencieuses :
 *   - aucun worker ne répond : les demandes partent en file et n'en sortent jamais,
 *     l'utilisateur voit un sablier éternel sans la moindre explication ;
 *   - le worker tourne sur une version périmée du code : Celery ne recharge pas à
 *     chaud, donc un correctif posé sur le disque reste inactif tant que le
 *     conteneur n'a pas été recréé. Trois générations de test ont été relancées
 *     pour rien le 10/09 avant que la cause soit trouvée.
 *
 * On n'affiche rien quand tout va bien — pas de bandeau décoratif.
 */

type EtatCode = {
  statut?: 'a_jour' | 'perime' | 'aucun_worker' | 'indeterminable' | 'inconnu';
  message?: string | null;
};

/**
 * Hook partagé : l'éditeur s'en sert aussi pour NE PAS lancer la rédaction
 * automatique quand le moteur est hors service ou périmé. Dépenser les crédits du
 * client sur un moteur cassé est le pire des comportements possibles.
 */
export function useWorkerHealth(): { etat: EtatCode | null; bloquant: boolean; verifie: boolean } {
  const [etat, setEtat] = useState<EtatCode | null>(null);
  const [verifie, setVerifie] = useState(false);

  useEffect(() => {
    const base = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
    const url = base.endsWith('/api') ? `${base}/health` : `${base}/api/health`;
    let annule = false;
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((h) => {
        if (!annule) setEtat(h?.redis_celery?.code ?? null);
      })
      .catch(() => {
        /* Une sonde indisponible ne doit jamais bloquer l'éditeur. */
      })
      .finally(() => {
        if (!annule) setVerifie(true);
      });
    return () => {
      annule = true;
    };
  }, []);

  // « bloquant » désigne le worker de fond, pas la rédaction elle-même : le mode de
  // secours synchrone prend le relais (voir api.generateSectionSync).
  const bloquant = etat?.statut === 'perime' || etat?.statut === 'aucun_worker';
  return { etat, bloquant, verifie };
}

export function WorkerHealthBanner() {
  const { etat, bloquant } = useWorkerHealth();
  if (!etat || !bloquant) return null;

  const estArret = etat.statut === 'aucun_worker';
  return (
    <div className="p-3.5 rounded-xl border border-danger/25 bg-danger/8 text-danger text-[12px] flex items-start gap-2.5">
      <AlertTriangle className="w-4 h-4 shrink-0 mt-px" />
      <div className="space-y-1">
        <p className="font-semibold">
          {estArret
            ? "Aucun moteur de rédaction en tâche de fond ne répond."
            : "Le moteur de rédaction en tâche de fond exécute une version périmée du code."}
        </p>
        <p className="opacity-90">
          La rédaction bascule automatiquement en <strong>mode de secours</strong> : elle
          s&apos;exécute directement, avec le code à jour, mais chaque section prend deux à
          trois minutes et la page doit rester ouverte. Pour retrouver le fonctionnement
          normal :
        </p>
        <p className="font-mono opacity-75">docker compose up -d worker</p>
      </div>
    </div>
  );
}
