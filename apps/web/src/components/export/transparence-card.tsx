'use client';

/**
 * « Ce que l'application a fait à votre place » (11/09).
 *
 * Chaque fois qu'une donnée manque, l'application prend une décision : valeur
 * laissée « [à compléter] », pièces standard du pays, planning détaillé par l'IA,
 * modèle Word choisi… Cette carte les liste en clair, avec la raison et le lien
 * pour corriger. Rien de ce qui a été décidé automatiquement ne doit être caché.
 */
import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Eye, AlertTriangle, Info, PenLine, ChevronRight, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import { TransparenceRapport } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

const STYLE: Record<string, { cls: string; Icone: any }> = {
  a_completer: { cls: 'border-danger/30 bg-danger/5', Icone: PenLine },
  a_verifier: { cls: 'border-warning/30 bg-warning/5', Icone: AlertTriangle },
  info: { cls: 'border-line bg-card', Icone: Info },
};

export function TransparenceCard({ projectId, compact = false }: { projectId: string; compact?: boolean }) {
  const { t, language } = useTranslation();
  const [rapport, setRapport] = useState<TransparenceRapport | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [ouvert, setOuvert] = useState(!compact);

  const charger = () => {
    setErreur(null);
    api.getTransparence(projectId).then(setRapport).catch((e) => setErreur(e?.message || String(e)));
  };
  // La langue fait partie de la cle : le texte est redige par l'API dans la langue de l'interface.
  useEffect(charger, [projectId, language]);

  if (erreur) {
    return <div className="card-modern p-4 text-xs text-danger">{t('transparence.erreur')} {erreur}</div>;
  }
  if (!rapport) return null;
  const { resume } = rapport;

  return (
    <div className="card-modern p-5 sm:p-6 space-y-3">
      <button onClick={() => setOuvert((v) => !v)} className="w-full flex flex-wrap items-center justify-between gap-3 cursor-pointer text-left">
        <div className="flex items-start gap-3">
          <Eye className="w-5 h-5 text-hl mt-0.5" />
          <div>
            <h2 className="text-base font-bold text-foreground font-heading">{t('transparence.titre')}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">{t('transparence.aide')}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold">
          {resume.a_completer > 0 && <span className="px-2 py-1 rounded-lg bg-danger/15 text-danger">{t('transparence.nb_a_completer', { n: String(resume.a_completer) })}</span>}
          {resume.a_verifier > 0 && <span className="px-2 py-1 rounded-lg bg-warning/15 text-warning">{t('transparence.nb_a_verifier', { n: String(resume.a_verifier) })}</span>}
          {resume.info > 0 && <span className="px-2 py-1 rounded-lg bg-sunken text-muted-foreground">{t('transparence.nb_info', { n: String(resume.info) })}</span>}
          <ChevronRight className={`w-4 h-4 text-muted-foreground transition-transform ${ouvert ? 'rotate-90' : ''}`} />
        </div>
      </button>

      {ouvert && (
        <div className="space-y-2">
          {rapport.items.length === 0 && <p className="text-xs text-positive">{t('transparence.rien')}</p>}
          {rapport.items.map((it, i) => {
            const { cls, Icone } = STYLE[it.gravite] || STYLE.info;
            return (
              <div key={i} className={`rounded-xl border p-3 flex gap-3 ${cls}`}>
                <Icone className={`w-4 h-4 shrink-0 mt-0.5 ${it.gravite === 'a_completer' ? 'text-danger' : it.gravite === 'a_verifier' ? 'text-warning' : 'text-muted-foreground'}`} />
                <div className="flex-1 min-w-0 space-y-0.5">
                  <p className="text-[10px] uppercase tracking-widest font-bold text-muted-foreground">{it.domaine}</p>
                  <p className="text-xs text-foreground font-medium">{it.fait}</p>
                  <p className="text-[11px] text-muted-foreground"><span className="font-semibold">{t('transparence.pourquoi')}</span> {it.parce_que}</p>
                </div>
                {it.lien && (
                  <Link href={it.lien} className="self-center shrink-0 text-[11px] font-semibold text-hl hover:underline whitespace-nowrap">
                    {it.lien_libelle || t('transparence.corriger')} →
                  </Link>
                )}
              </div>
            );
          })}
          <button onClick={charger} className="text-[11px] text-muted-foreground hover:text-hl flex items-center gap-1 cursor-pointer">
            <RefreshCw className="w-3 h-3" /> {t('transparence.actualiser')}
          </button>
        </div>
      )}
    </div>
  );
}
