'use client';

/**
 * Détecteur de spécificité avant export (14/09, demande Charbel : « je veux une
 * qualité incroyable peu importe la langue basé sur les meilleurs dossiers »).
 *
 * Repère les paragraphes qui pourraient être copiés-collés dans n'importe quel
 * dossier BTP, faute de reprendre un fait réel de ce marché (site, délai,
 * référence, chiffre) ou de l'entreprise. Voir
 * apps/api/app/services/specificite_service.py pour la méthode : un vocabulaire
 * de faits réels de CE projet, vérifié mécaniquement dans chaque paragraphe —
 * pas une note auto-déclarée par le LLM, et indépendant de la langue de
 * rédaction (FR / EN / AR).
 */
import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Target, ChevronRight, RefreshCw, CheckCircle2, AlertTriangle, XCircle, Info } from 'lucide-react';
import { api } from '@/lib/api';
import { SpecificiteRapport } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

const STYLE: Record<string, { cls: string; badge: string; Icone: any }> = {
  excellent: { cls: 'border-positive/30 bg-positive/5', badge: 'bg-positive/15 text-positive', Icone: CheckCircle2 },
  correct: { cls: 'border-warning/30 bg-warning/5', badge: 'bg-warning/15 text-warning', Icone: AlertTriangle },
  insuffisant: { cls: 'border-danger/30 bg-danger/5', badge: 'bg-danger/15 text-danger', Icone: XCircle },
};

export function SpecificiteCard({ projectId, compact = false }: { projectId: string; compact?: boolean }) {
  const { t, language } = useTranslation();
  const [rapport, setRapport] = useState<SpecificiteRapport | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [ouvert, setOuvert] = useState(!compact);

  const charger = () => {
    setErreur(null);
    api.getSpecificite(projectId).then(setRapport).catch((e) => setErreur(e?.message || String(e)));
  };
  // La langue fait partie de la cle : les libelles sont rediges par l'API dans la langue de l'interface.
  useEffect(charger, [projectId, language]);

  if (erreur) {
    return <div className="card-modern p-4 text-xs text-danger">{t('specificite.erreur')} {erreur}</div>;
  }
  if (!rapport) return null;

  const { resume, score_global, sections, nb_faits_disponibles } = rapport;
  const donneesInsuffisantes = nb_faits_disponibles < 3;
  const sectionsAAmeliorer = sections.filter((s) => s.verdict !== 'excellent');
  const globalStyle = score_global !== null ? STYLE[rapport.verdict_global || 'insuffisant'] : STYLE.correct;

  return (
    <div className="card-modern p-5 sm:p-6 space-y-3">
      <button onClick={() => setOuvert((v) => !v)} className="w-full flex flex-wrap items-center justify-between gap-3 cursor-pointer text-left">
        <div className="flex items-start gap-3">
          <Target className="w-5 h-5 text-hl mt-0.5" />
          <div>
            <h2 className="text-base font-bold text-foreground font-heading">{t('specificite.titre')}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">{t('specificite.aide')}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold">
          {score_global !== null && (
            <span className={`px-2.5 py-1 rounded-lg font-bold ${globalStyle.badge}`}>
              {t('specificite.score_global')} : {score_global}/100
            </span>
          )}
          {resume.correct > 0 && <span className="px-2 py-1 rounded-lg bg-warning/15 text-warning">{t('specificite.nb_correct', { n: String(resume.correct) })}</span>}
          {resume.insuffisant > 0 && <span className="px-2 py-1 rounded-lg bg-danger/15 text-danger">{t('specificite.nb_insuffisant', { n: String(resume.insuffisant) })}</span>}
          <ChevronRight className={`w-4 h-4 text-muted-foreground transition-transform ${ouvert ? 'rotate-90' : ''}`} />
        </div>
      </button>

      {ouvert && (
        <div className="space-y-2">
          {donneesInsuffisantes ? (
            <div className="rounded-xl border border-line bg-sunken p-3 flex gap-3">
              <Info className="w-4 h-4 shrink-0 mt-0.5 text-muted-foreground" />
              <p className="text-xs text-muted-foreground">{t('specificite.pas_assez_de_donnees')}</p>
            </div>
          ) : sectionsAAmeliorer.length === 0 ? (
            <p className="text-xs text-positive flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              {t('specificite.tout_excellent')}
            </p>
          ) : (
            sectionsAAmeliorer.map((s) => {
              const { cls, badge, Icone } = STYLE[s.verdict];
              return (
                <div key={s.section_key} className={`rounded-xl border p-3 space-y-2 ${cls}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2.5 min-w-0">
                      <Icone className={`w-4 h-4 shrink-0 mt-0.5 ${s.verdict === 'insuffisant' ? 'text-danger' : 'text-warning'}`} />
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-foreground truncate">{s.title}</p>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          {t('specificite.marqueurs', { n: String(s.marqueurs_distincts), total: String(s.total_paragraphes) })}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${badge}`}>{s.score}/100</span>
                      <Link
                        href={`/projects/${projectId}/editor`}
                        className="text-[11px] font-semibold text-hl hover:underline whitespace-nowrap"
                      >
                        {t('specificite.corriger')} →
                      </Link>
                    </div>
                  </div>
                  {s.paragraphes_generiques.length > 0 && (
                    <div className="space-y-1.5 pl-6">
                      {s.paragraphes_generiques.map((p, i) => (
                        <div key={i} className="text-[11px] leading-snug">
                          <p className="text-muted-foreground">
                            <span className="font-semibold">{t('specificite.extrait_label')}</span>{' '}
                            <span className="italic">« {p.extrait} »</span>
                          </p>
                          <p className="text-muted-foreground/80 mt-0.5">{p.raison}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })
          )}
          <button onClick={charger} className="text-[11px] text-muted-foreground hover:text-hl flex items-center gap-1 cursor-pointer">
            <RefreshCw className="w-3 h-3" /> {t('specificite.actualiser')}
          </button>
        </div>
      )}
    </div>
  );
}
