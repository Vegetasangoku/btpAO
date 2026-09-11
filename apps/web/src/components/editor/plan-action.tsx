'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { ArrowRight, ChevronDown, ChevronRight, ListChecks, CheckCircle2 } from 'lucide-react';

import { construireRecommandations, type SectionAvecLacunes } from '@/lib/recommandations';
import { useTranslation } from '@/components/i18n-provider';
import { TexteAvecAcronymes } from '@/components/ui/acronyme';

/**
 * Plan d'action du dossier (10/09).
 *
 * Remplace la liste brute de recommandations que l'utilisateur jugeait
 * incompréhensible : « je ne comprends ni l'action attendue ni comment
 * l'application va concrètement m'aider à l'appliquer ».
 *
 * Trois réponses, dans cet ordre de lecture :
 *   — CE QU'IL FAUT FAIRE : un verbe à l'infinitif, une ligne, pas un sigle ;
 *   — POURQUOI ÇA COMPTE  : le nombre de sections que le point débloque ;
 *   — OÙ LE FAIRE         : un bouton qui ouvre l'écran concerné.
 * Le texte d'origine du moteur reste consultable en dépliant la ligne, pour
 * qui veut le détail — mais il ne s'impose plus à la lecture.
 */
export function PlanDAction({
  sections,
  projectId,
}: {
  sections: SectionAvecLacunes[];
  projectId: string;
}) {
  const { t } = useTranslation();
  const [deplie, setDeplie] = useState<string | null>(null);

  const recommandations = construireRecommandations(sections, projectId);
  if (recommandations.length === 0) {
    return (
      <div className="card-modern p-4 flex items-start gap-2.5">
        <CheckCircle2 className="w-4 h-4 text-positive shrink-0 mt-0.5" />
        <div>
          <h3 className="text-[13px] font-bold text-foreground font-heading">
            {t('plan.rien_titre')}
          </h3>
          <p className="text-[11px] text-muted-foreground mt-0.5">{t('plan.rien_desc')}</p>
        </div>
      </div>
    );
  }

  const total = sections.length || 1;

  return (
    <div className="card-modern p-4 space-y-3">
      <div className="flex items-center gap-2">
        <ListChecks className="w-4 h-4 text-hl shrink-0" />
        <h3 className="text-[13px] font-bold text-foreground font-heading">
          {t('plan.titre')}
        </h3>
        <span className="text-[10px] font-semibold text-muted-foreground bg-sunken px-1.5 py-0.5 rounded">
          {recommandations.length}
        </span>
      </div>
      <p className="text-[11px] text-muted-foreground leading-relaxed">{t('plan.desc')}</p>

      <ol className="space-y-2">
        {recommandations.map((reco, rang) => {
          const ouvert = deplie === reco.id;
          const portee = reco.sections.length;
          return (
            <li key={reco.id} className="rounded-lg border border-line bg-sunken/40 overflow-hidden">
              <div className="p-3 space-y-2">
                <div className="flex items-start gap-2.5">
                  <span className="mt-0.5 shrink-0 w-5 h-5 rounded-full bg-hl/15 text-hl text-[10px] font-bold flex items-center justify-center">
                    {rang + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-semibold text-foreground leading-snug">
                      <TexteAvecAcronymes texte={reco.action} />
                    </p>
                    <p className="text-[11px] mt-1">
                      <span className={portee > 1 ? 'text-hl font-semibold' : 'text-muted-foreground'}>
                        {portee === total
                          ? t('plan.portee_toutes')
                          : `${t('plan.portee_prefixe')} ${portee} ${portee > 1 ? t('plan.sections') : t('plan.section')}`}
                      </span>
                      {reco.pourquoi && (
                        <span className="text-muted-foreground"> — <TexteAvecAcronymes texte={reco.pourquoi} /></span>
                      )}
                    </p>
                    {reco.ceQueLAppFait && (
                      <p className="text-[11px] text-muted-foreground mt-1 leading-relaxed">
                        <span className="font-semibold text-foreground">{t('plan.ce_que_lapp_fait')}</span>{' '}
                        {reco.ceQueLAppFait}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3 pl-7">
                  {reco.lien ? (
                    <Link href={reco.lien} className="btn-primary !py-1 !px-2.5 !text-[11px]">
                      {reco.lienLibelle || t('plan.ouvrir')}
                      <ArrowRight className="w-3 h-3" />
                    </Link>
                  ) : (
                    <span className="text-[10px] text-muted-foreground italic">
                      {t('plan.pas_ecran')}
                    </span>
                  )}
                  {reco.details.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setDeplie(ouvert ? null : reco.id)}
                      aria-expanded={ouvert}
                      className="inline-flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
                    >
                      {ouvert ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                      {t('plan.detail')} ({reco.details.length})
                    </button>
                  )}
                </div>

                {ouvert && (
                  <ul className="pl-7 space-y-1 pt-1">
                    {reco.details.map((d, i) => (
                      <li key={i} className="text-[11px] text-muted-foreground leading-relaxed border-l-2 border-line pl-2">
                        <TexteAvecAcronymes texte={d} />
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
