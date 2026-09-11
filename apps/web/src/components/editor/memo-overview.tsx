'use client';

import React, { useMemo } from 'react';
import { Loader2, Sparkles, AlertTriangle, CheckCircle2, Clock } from 'lucide-react';
import { TiptapEditor } from '@/components/editor/tiptap-editor';
import { SectionDiagnostics } from '@/components/editor/section-diagnostics';
import { InteractiveGanttChart } from '@/components/visuals/interactive-gantt-chart';
import { OrganigrammePreview } from '@/components/visuals/organigramme-preview';
import { MEMO_SECTIONS } from '@/lib/sections';
import { useTranslation } from '@/components/i18n-provider';
import { GeneratedSection } from '@/lib/types';
import { Acronyme, definitionAcronyme } from '@/components/ui/acronyme';
import { PlanDAction } from '@/components/editor/plan-action';
import { construireRecommandations } from '@/lib/recommandations';

/**
 * Aperçu global du mémoire (10/09).
 *
 * Demande explicite : « à la fin un aperçu global modifiable, chaque partie ».
 * L'éditeur n'offrait qu'une navigation section par section : impossible de lire
 * le dossier comme le lira le jury, ni de voir d'un coup d'œil ce qui manque.
 *
 * Ici tout est sur une seule page, dans l'ordre du mémoire, et tout reste
 * éditable en place : le même éditeur de texte que la vue détaillée (donc mêmes
 * sauvegardes, mêmes tableaux, mêmes couleurs), le planning interactif et
 * l'organigramme. Aucune vue « lecture seule » qui obligerait à repasser
 * ailleurs pour corriger une ligne.
 */

interface MemoOverviewProps {
  projectId: string;
  projectTitle: string;
  sections: GeneratedSection[];
  generating: Set<string>;
  failedKeys: Set<string>;
  onSectionSaved: (s: GeneratedSection) => void;
  onRegenerate: (key: string) => void;
}

const STATUTS_PRETS = ['generated', 'edited', 'validated', 'restored'];

export function MemoOverview({
  projectId,
  projectTitle,
  sections,
  generating,
  failedKeys,
  onSectionSaved,
  onRegenerate,
}: MemoOverviewProps) {
  const { t, language } = useTranslation();
  const trouver = (key: string) => sections.find((s) => s.section_key === key);

  const bilan = useMemo(() => {
    const redigees = MEMO_SECTIONS.filter((m) => !m.visual);
    const pretes = redigees.filter((m) => {
      const s = trouver(m.key);
      return s && STATUTS_PRETS.includes(s.status) && (s.content_html || '').trim().length > 50;
    });
    const scores = pretes
      .map((m) => trouver(m.key)?.compliance_score)
      .filter((v): v is number => typeof v === 'number');
    const moyenne = scores.length
      ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
      : null;
    // On compte les ACTIONS distinctes, pas les lacunes brutes : le moteur
    // répète la même demande section par section, et afficher « 74 points »
    // décourage sans informer. Après regroupement il en reste une dizaine.
    const lacunes = construireRecommandations(sections, projectId).length;
    return { total: redigees.length, pretes: pretes.length, moyenne, lacunes };
  }, [sections, projectId]);

  return (
    <div className="space-y-6">
      {/* Bandeau de synthèse : l'état réel du dossier, sans chiffre inventé. */}
      <div className="card-modern p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <div>
            <h2 className="text-[16px] font-bold text-foreground font-heading">{projectTitle}</h2>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {t('apercu.sous_titre')}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-5">
            <div>
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">{t('apercu.sections_redigees')}</p>
              <p className="text-[18px] font-mono font-bold text-foreground">
                {bilan.pretes}<span className="text-muted-foreground text-[13px]"> / {bilan.total}</span>
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">{t('apercu.conformite_moyenne')}</p>
              <p className={`text-[18px] font-mono font-bold ${
                bilan.moyenne === null ? 'text-muted-foreground'
                  : bilan.moyenne >= 90 ? 'text-positive'
                  : bilan.moyenne >= 70 ? 'text-hl' : 'text-danger'
              }`}>
                {bilan.moyenne === null ? '—' : `${bilan.moyenne}%`}
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">{t('apercu.points_a_fournir')}</p>
              <p className={`text-[18px] font-mono font-bold ${bilan.lacunes > 0 ? 'text-hl' : 'text-positive'}`}>
                {bilan.lacunes}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Le plan d'action passe AVANT les sections : c'est la première chose
          à lire quand on ouvre un dossier incomplet. */}
      <PlanDAction sections={sections} projectId={projectId} />

      {MEMO_SECTIONS.map((meta) => {
        const section = trouver(meta.key);
        const enCours = generating.has(meta.key) || section?.status === 'processing';
        const enEchec = failedKeys.has(meta.key) || section?.status === 'failed';
        const prete = Boolean(section && STATUTS_PRETS.includes(section.status) && section.content_html);
        const score = section?.compliance_score;

        return (
          <section key={meta.key} className="space-y-3 scroll-mt-4" id={`section-${meta.key}`}>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-2">
              <div className="flex items-center gap-2.5 min-w-0">
                {enCours ? <Loader2 className="w-4 h-4 text-hl animate-spin shrink-0" />
                  : enEchec ? <AlertTriangle className="w-4 h-4 text-danger shrink-0" />
                  : prete || meta.visual ? <CheckCircle2 className="w-4 h-4 text-positive shrink-0" />
                  : <Clock className="w-4 h-4 text-muted-foreground shrink-0" />}
                <h3 className="text-[14px] font-bold text-foreground font-heading truncate">{meta.title}</h3>
                {!meta.mandatory && (
                  <span className="text-[9px] font-semibold text-muted-foreground bg-sunken px-1.5 py-0.5 rounded shrink-0">
                    {t('apercu.facultative')}
                  </span>
                )}
                {typeof score === 'number' && prete && (
                  <span
                    title={`${score} % des critères de notation du règlement de consultation sont couverts par cette section. ${definitionAcronyme('RC', language)}`}
                    className={`text-[10px] font-semibold shrink-0 cursor-help whitespace-nowrap ${
                      score >= 90 ? 'text-positive' : score >= 70 ? 'text-hl' : 'text-danger'
                    }`}
                  >
                    <span className="font-mono font-bold">{score} %</span>{' '}
                    <span className="font-normal">{t('apercu.des_criteres_notation')}</span>
                  </span>
                )}
              </div>
              {!meta.visual && (
                <button
                  onClick={() => onRegenerate(meta.key)}
                  disabled={enCours}
                  className="btn-ghost !py-1 !px-2 !text-[11px]"
                >
                  {enCours
                    ? <><Loader2 className="w-3 h-3 animate-spin" /> {t('apercu.en_cours')}</>
                    : <><Sparkles className="w-3 h-3" /> {t('apercu.regenerer')}</>}
                </button>
              )}
            </div>

            {meta.visual === 'gantt' ? (
              <InteractiveGanttChart projectId={projectId} projectTitle={projectTitle} />
            ) : section ? (
              <>
                <div className="card-modern overflow-hidden">
                  <TiptapEditor
                    key={`ov-${meta.key}`}
                    projectId={projectId}
                    section={section}
                    onSave={onSectionSaved}
                    onRegenerate={() => onRegenerate(meta.key)}
                  />
                </div>
                <SectionDiagnostics placeholders={section.visual_placeholders} />
              </>
            ) : (
              <div className="p-5 rounded-xl card-inset text-[12px] text-muted-foreground">
                {t('apercu.pas_redigee')}
              </div>
            )}

            {/* L'organigramme d'encadrement se lit avec les moyens humains : c'est là
                qu'un jury le cherche, et il reste modifiable comme le reste. */}
            {meta.key === 'moyens_humains' && (
              <OrganigrammePreview projectId={projectId} projectTitle={projectTitle} />
            )}
          </section>
        );
      })}
    </div>
  );
}
