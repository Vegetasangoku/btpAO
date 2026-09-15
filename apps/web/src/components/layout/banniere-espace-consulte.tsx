'use client';

import React, { useEffect, useState } from 'react';
import { Building2, X } from 'lucide-react';
import { supabase } from '@/lib/supabase/client';
import { api } from '@/lib/api';
import { lireEspaceConsulte, ecrireEspaceConsulte, type EspaceConsulte } from '@/lib/espace-actif';
import { useTranslation } from '@/components/i18n-provider';

/**
 * Rappel permanent : « vous n'êtes pas chez vous ».
 *
 * Quand un administrateur inspecte l'espace d'un client, il doit le savoir à
 * chaque écran — pas seulement au moment où il a cliqué. Sans ce rappel, le
 * 10/09, l'administrateur a travaillé dans les données d'un client en croyant
 * être dans les siennes, et rien à l'écran ne le contredisait.
 *
 * Correctif du 14/09, trouvé en testant un tout nouveau compte client dans
 * Chrome : `btp_espace_consulte` vit dans localStorage, donc à l'échelle du
 * NAVIGATEUR, pas du compte connecté. Un navigateur où un administrateur a
 * déjà consulté un client garde cette valeur après déconnexion — et elle
 * s'affichait, sans aucune vérification de rôle, au premier client venu qui
 * se connectait ensuite dans ce même navigateur : bandeau « vous consultez
 * l'espace de… » sur le tout premier tableau de bord d'une entreprise qui
 * vient de s'inscrire, sans aucun lien avec l'administration. L'API refuse
 * déjà cet en-tête pour un compte non-admin (voir app/core/security.py),
 * donc aucune donnée n'a fui — mais l'AFFICHAGE mentait, et chaque appel API
 * d'un compte non-admin déclenchait en plus une alerte « tentative de
 * franchissement » côté serveur pour rien.
 *
 * Le rôle vient désormais de `/auth/me`, comme dans user-sidebar.tsx — jamais
 * de la simple présence d'une clé dans localStorage — et un compte non-admin
 * qui porte une valeur héritée d'une autre session la voit effacée
 * automatiquement.
 */
export function BanniereEspaceConsulte() {
  const { t } = useTranslation();
  const [espace, setEspace] = useState<EspaceConsulte>(null);
  const [estAdminPlateforme, setEstAdminPlateforme] = useState<boolean | null>(null);

  useEffect(() => {
    let annule = false;

    async function resynchroniser() {
      let admin = false;
      try {
        const profile = await api.getProfile();
        admin = profile.role === 'platform_admin' || profile.role === 'super_admin';
      } catch {
        admin = false;
      }
      if (annule) return;
      setEstAdminPlateforme(admin);

      const valeurStockee = lireEspaceConsulte();
      if (!admin) {
        // Compte non-admin : cette valeur ne peut venir que d'une session
        // précédente dans ce navigateur. On l'efface pour de bon — sinon elle
        // survit à la déconnexion et retombe sur le prochain compte connecté.
        if (valeurStockee) ecrireEspaceConsulte(null);
        setEspace(null);
      } else {
        setEspace(valeurStockee);
      }
    }

    resynchroniser();
    const { data: ecoute } = supabase.auth.onAuthStateChange(() => {
      resynchroniser();
    });
    // Un autre onglet peut changer l'espace consulté : rester synchronisé.
    const surStockage = () => resynchroniser();
    window.addEventListener('storage', surStockage);
    return () => {
      annule = true;
      ecoute.subscription.unsubscribe();
      window.removeEventListener('storage', surStockage);
    };
  }, []);

  if (!estAdminPlateforme || !espace) return null;

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
