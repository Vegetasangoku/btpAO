'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Languages, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';

/**
 * 11/09 : changer la langue du mémoire ne traduisait que la mise en page. Ici on
 * traduit le texte déjà rédigé, section par section, en gardant l'original dans
 * l'historique de version de chaque section.
 */
const NOMS: Record<string, Record<string, string>> = {
  fr: { fr: 'français', en: 'anglais', ar: 'arabe' },
  en: { fr: 'French', en: 'English', ar: 'Arabic' },
  ar: { fr: 'الفرنسية', en: 'الإنجليزية', ar: 'العربية' },
};

export function TraductionCard({ projectId }: { projectId: string }) {
  const { t, language } = useTranslation();
  const [etat, setEtat] = useState<{ langue_document: string; a_traduire: number; sections: { id: string; titre: string; langue: string | null; a_traduire: boolean }[] } | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [fait, setFait] = useState(0);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async () => {
    try {
      setEtat(await api.getLanguesSections(projectId));
    } catch {
      setEtat(null);
    }
  }, [projectId]);

  useEffect(() => { charger(); }, [charger]);

  async function traduire() {
    if (!etat) return;
    const cibles = etat.sections.filter((s) => s.a_traduire);
    setEnCours(true);
    setErreur(null);
    setFait(0);
    for (const s of cibles) {
      try {
        await api.traduireSection(s.id);
        setFait((n) => n + 1);
      } catch (e) {
        setErreur(e instanceof Error ? e.message : String(e));
        break;
      }
    }
    await charger();
    setEnCours(false);
  }

  if (!etat || etat.a_traduire === 0) return null;
  const noms = NOMS[language] || NOMS.fr;
  const ecrite = etat.sections.find((s) => s.a_traduire)?.langue || 'fr';

  return (
    <div id="traduction" className="card-modern p-5 space-y-3 rounded-2xl scroll-mt-20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex gap-2.5">
          <Languages className="w-4 h-4 text-hl mt-0.5" />
          <div>
            <h2 className="text-[14px] font-bold text-foreground font-heading">{t('traduction.titre')}</h2>
            <p className="text-[12px] text-muted-foreground">
              {t('traduction.constat', { n: String(etat.a_traduire), ecrite: noms[ecrite] || ecrite, voulue: noms[etat.langue_document] || etat.langue_document })}
            </p>
          </div>
        </div>
        <button onClick={traduire} disabled={enCours} className="btn-primary !py-1.5 !text-[12px]">
          {enCours ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Languages className="w-3.5 h-3.5" />}
          {enCours
            ? t('traduction.en_cours', { fait: String(fait), total: String(etat.a_traduire) })
            : t('traduction.bouton', { voulue: noms[etat.langue_document] || etat.langue_document })}
        </button>
      </div>
      <p className="text-[11px] text-muted-foreground">{t('traduction.note')}</p>
      {erreur && <p className="text-[12px] text-danger">{erreur}</p>}
    </div>
  );
}
