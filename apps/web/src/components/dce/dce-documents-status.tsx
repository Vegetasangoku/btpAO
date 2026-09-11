'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, FileText } from 'lucide-react';
import { api } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';

/**
 * État réel des pièces du marché déposées (10/09).
 *
 * Rien, dans l'interface, ne montrait si une pièce déposée avait été analysée.
 * Sur un vrai dossier, un CCTP déposé le 3 septembre est resté bloqué en cours
 * d'analyse pendant une semaine : zéro fragment indexé, toutes les sections
 * rédigées sans une seule ligne du marché, et aucun signal. L'utilisateur a fini
 * par redéposer le même fichier sur d'autres dossiers sans comprendre pourquoi.
 *
 * Le nombre de fragments indexés est la seule preuve qu'une pièce sert vraiment :
 * c'est donc lui qu'on affiche, pas seulement un statut.
 */

type Doc = {
  id: string;
  filename: string;
  doc_type?: string;
  statut: 'completed' | 'failed' | 'processing' | string;
  fragments_indexes: number;
  message?: string;
};

type Etat = {
  documents: Doc[];
  total_fragments: number;
  exploitable: boolean;
  avertissement?: string | null;
};

export function DceDocumentsStatus({ projectId }: { projectId: string }) {
  const { t, language } = useTranslation();
  const [etat, setEtat] = useState<Etat | null>(null);
  const [chargement, setChargement] = useState(true);
  const [relance, setRelance] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(async () => {
    try {
      setEtat(await api.getDceDocuments(projectId));
      setErreur(null);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : t('dce.status.indisponible'));
    } finally {
      setChargement(false);
    }
  }, [projectId, language]);

  useEffect(() => {
    charger();
  }, [charger]);

  async function relancerAnalyse(documentId: string) {
    setRelance(documentId);
    try {
      // 11/09 : l'analyse se fait maintenant tout de suite dans l'API (le worker
      // pouvait etre arrete ou perime, et la piece restait « en cours » pour toujours).
      await api.analyserDceMaintenant(documentId);
      await charger();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : t('dce.status.relance_impossible'));
    } finally {
      setRelance(null);
    }
  }

  if (chargement) {
    return (
      <div className="card-modern p-4 flex items-center gap-2 text-[12px] text-muted-foreground">
        <Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('dce.status.lecture')}
      </div>
    );
  }
  if (erreur) {
    return <div className="card-modern p-4 text-[12px] text-danger">{erreur}</div>;
  }
  if (!etat || etat.documents.length === 0) return null;

  return (
    <div className="card-modern p-5 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[14px] font-bold text-foreground font-heading flex items-center gap-2">
          <FileText className="w-4 h-4 text-hl" />
          {t('dce.status.titre')}
        </h2>
        <button onClick={charger} className="btn-ghost !py-1 !px-2 !text-[11px]">
          <RefreshCw className="w-3 h-3" /> {t('dce.status.actualiser')}
        </button>
      </div>

      {etat.avertissement && (
        <div className="p-3 rounded-xl border border-danger/25 bg-danger/8 text-danger text-[12px] flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-px" />
          <span>{etat.avertissement}</span>
        </div>
      )}

      <ul className="space-y-2">
        {etat.documents.map((d) => {
          const ok = d.statut === 'completed';
          const enCours = d.statut === 'processing';
          return (
            <li
              key={d.id}
              className="flex flex-wrap items-start justify-between gap-2 p-3 rounded-xl card-inset"
            >
              <div className="min-w-0 flex-1">
                <p className="text-[12px] font-semibold text-foreground truncate">
                  {d.filename}
                  {d.doc_type && (
                    <span className="ml-2 text-[9px] uppercase font-mono text-muted-foreground">{d.doc_type}</span>
                  )}
                </p>
                <p
                  className={`text-[11px] mt-0.5 flex items-start gap-1.5 ${
                    ok ? 'text-positive' : enCours ? 'text-muted-foreground' : 'text-danger'
                  }`}
                >
                  {ok ? (
                    <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-px" />
                  ) : enCours ? (
                    <Loader2 className="w-3.5 h-3.5 shrink-0 mt-px animate-spin" />
                  ) : (
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" />
                  )}
                  <span>{d.message}</span>
                </p>
              </div>
              {!ok && !enCours && (
                <button
                  onClick={() => relancerAnalyse(d.id)}
                  disabled={relance === d.id}
                  className="btn-secondary !py-1 !px-2.5 !text-[11px] shrink-0"
                >
                  {relance === d.id ? (
                    <><Loader2 className="w-3 h-3 animate-spin" /> {t('dce.status.relance_en_cours')}</>
                  ) : (
                    <><RefreshCw className="w-3 h-3" /> {t('dce.status.relancer')}</>
                  )}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
