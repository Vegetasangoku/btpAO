'use client';

/**
 * Pièces administratives et formulaires officiels (11/09).
 *
 * Liste les pièces exigées (dossier de consultation + pays du marché), indique ce qui
 * est déjà disponible, et pour ce qui manque cherche le formulaire sur les portails
 * officiels du pays — liens vérifiés (page réellement ouverte) ou signalés comme tels.
 */
import React, { useState } from 'react';
import { ClipboardCheck, RefreshCw, CheckCircle2, AlertTriangle, FileDown, ExternalLink, Wand2, PenLine, Info, History, PlusCircle } from 'lucide-react';
import { api, buildApiUrl, fetchAuthenticatedBlobUrl } from '@/lib/api';
import { PiecesRapport } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

export function PiecesCard({ projectId }: { projectId: string }) {
  const { t, language } = useTranslation();
  const [rapport, setRapport] = useState<PiecesRapport | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  // 15/09 : recommandations que l'utilisateur a confirmees pour CE dossier (accumulees au fil
  // des clics) -- renvoyees a chaque appel pour qu'elles rejoignent les pieces et renforcent
  // l'historique cote serveur (« on fait les reco et on apprend »).
  const [confirmees, setConfirmees] = useState<string[]>([]);
  const [confirmationEnCours, setConfirmationEnCours] = useState<string | null>(null);

  // Changement de langue : le rapport (redige par l'API) doit etre refait.
  React.useEffect(() => { setRapport(null); setConfirmees([]); }, [language]);

  const lancer = async () => {
    setEnCours(true);
    setErreur(null);
    try {
      setRapport(await api.verifierPieces(projectId, confirmees));
    } catch (e: any) {
      setErreur(e?.message || String(e));
    } finally {
      setEnCours(false);
    }
  };

  const confirmer = async (piece: string) => {
    if (confirmationEnCours) return;
    const nouvelles = confirmees.includes(piece) ? confirmees : [...confirmees, piece];
    setConfirmees(nouvelles);
    setConfirmationEnCours(piece);
    setErreur(null);
    try {
      setRapport(await api.verifierPieces(projectId, nouvelles));
    } catch (e: any) {
      setErreur(e?.message || String(e));
    } finally {
      setConfirmationEnCours(null);
    }
  };

  const badge = (statut: string) =>
    statut === 'fourni'
      ? 'bg-positive/15 text-positive'
      : statut === 'generable'
      ? 'bg-hl/15 text-hl'
      : statut === 'redigeable'
      ? 'bg-warning/15 text-warning'
      : 'bg-danger/15 text-danger';

  return (
    <div className="card-modern p-6 sm:p-8 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
        <div className="flex items-start gap-3">
          <ClipboardCheck className="w-5 h-5 text-hl mt-0.5" />
          <div>
            <h2 className="text-base font-bold text-foreground font-heading">{t('pieces.titre')}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">{t('pieces.aide')}</p>
          </div>
        </div>
        <button onClick={lancer} disabled={enCours} className="btn-primary !text-xs cursor-pointer disabled:opacity-50">
          <RefreshCw className={`w-3.5 h-3.5 ${enCours ? 'animate-spin' : ''}`} />
          {enCours ? t('pieces.en_cours') : rapport ? t('pieces.relancer') : t('pieces.lancer')}
        </button>
      </div>

      {erreur && (
        <div className="p-3 rounded-xl border border-danger/30 bg-danger/10 text-danger text-xs flex gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" /> {erreur}
        </div>
      )}

      {rapport && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="px-2 py-1 rounded-lg bg-sunken">{t('pieces.pays', { pays: rapport.pays_nom, n: String(rapport.portails.length) })}</span>
            <span className="px-2 py-1 rounded-lg bg-positive/15 text-positive">{t('pieces.nb_fourni', { n: String(rapport.resume.fourni) })}</span>
            <span className="px-2 py-1 rounded-lg bg-hl/15 text-hl">{t('pieces.nb_generable', { n: String(rapport.resume.generable) })}</span>
            <span className="px-2 py-1 rounded-lg bg-warning/15 text-warning">{t('pieces.nb_redigeable', { n: String(rapport.resume.redigeable) })}</span>
            <span className="px-2 py-1 rounded-lg bg-danger/15 text-danger">{t('pieces.nb_manquant', { n: String(rapport.resume.manquant) })}</span>
          </div>
          {rapport.avertissement && (
            <div className="rounded-xl border border-warning/30 bg-warning/10 p-3 space-y-2">
              <p className="text-xs text-foreground flex gap-1.5"><Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-warning" />{rapport.avertissement}</p>
              {rapport.rc_absent && (
                <a href={`/projects/${projectId}/dce`} className="btn-secondary !py-1 !px-2.5 !text-[11px] inline-flex">
                  <FileDown className="w-3 h-3" /> {t('pieces.ajouter_rc')}
                </a>
              )}
            </div>
          )}
          {rapport.lecture_simple && (
            <p className="text-[11px] text-muted-foreground flex gap-1.5">
              <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />{t('pieces.lecture_simple')}
            </p>
          )}
          <div className="space-y-2">
            {rapport.pieces.map((p, i) => (
              <div key={i} className="rounded-xl border border-line p-3 space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  {p.statut === 'fourni' ? <CheckCircle2 className="w-4 h-4 text-positive" /> : p.statut === 'generable' ? <Wand2 className="w-4 h-4 text-hl" /> : p.statut === 'redigeable' ? <PenLine className="w-4 h-4 text-warning" /> : <AlertTriangle className="w-4 h-4 text-danger" />}
                  <span className="text-sm font-semibold text-foreground">{p.piece}</span>
                  <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${badge(p.statut)}`}>{t(`pieces.statut_${p.statut}`)}</span>
                  <span className="text-[10px] text-muted-foreground">{p.origine}</span>
                </div>
                {p.citation && (
                  <p className="text-[11px] italic text-muted-foreground">
                    {p.historique && <span className="not-italic font-semibold text-muted-foreground/80">{t('pieces.citation_historique')} </span>}
                    « {p.citation} »
                  </p>
                )}
                {p.fourni_par && <p className="text-[11px] text-positive">{p.fourni_par}</p>}
                {p.generable && <p className="text-[11px] text-hl">{p.generable}</p>}
                {p.redigeable && <p className="text-[11px] text-warning">{p.redigeable}</p>}
                {!!p.telechargements?.length && (
                  <div className="flex flex-wrap gap-2">
                    {p.telechargements.map((d) => (
                      <button
                        key={d.code}
                        onClick={async () => {
                          try {
                            const url = await fetchAuthenticatedBlobUrl(buildApiUrl(d.chemin));
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `${d.libelle}.docx`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            setTimeout(() => URL.revokeObjectURL(url), 60000);
                          } catch (e: any) {
                            setErreur(e?.message || String(e));
                          }
                        }}
                        className="btn-secondary !py-1 !px-2.5 !text-[11px] cursor-pointer"
                      >
                        {d.type === 'draft' ? <PenLine className="w-3 h-3" /> : <FileDown className="w-3 h-3" />}
                        {d.type === 'draft' ? t('pieces.rediger', { nom: d.libelle }) : t('pieces.telecharger', { nom: d.libelle })}
                      </button>
                    ))}
                  </div>
                )}
                {p.liens.length > 0 && (
                  <div className="space-y-1">
                    {p.liens.map((l, j) => (
                      <a key={j} href={l.url} target="_blank" rel="noopener noreferrer"
                         className="flex items-start gap-1.5 text-[11px] text-hl hover:underline">
                        {l.format === 'pdf' || l.format === 'docx' ? <FileDown className="w-3.5 h-3.5 shrink-0 mt-0.5" /> : <ExternalLink className="w-3.5 h-3.5 shrink-0 mt-0.5" />}
                        <span>
                          {l.titre} <span className="text-muted-foreground">— {new URL(l.url).hostname} · {l.format.toUpperCase()} · {l.verifie ? t('pieces.lien_verifie') : (l.erreur || t('pieces.lien_non_verifie'))}</span>
                        </span>
                      </a>
                    ))}
                  </div>
                )}
                {p.recherche && p.liens.length === 0 && p.statut !== 'fourni' && (
                  <p className="text-[11px] text-muted-foreground">{p.recherche}</p>
                )}
              </div>
            ))}
          </div>
          {!!rapport.recommandations?.length && (
            <div className="space-y-2 pt-3 border-t border-line">
              <div className="flex items-center gap-2">
                <History className="w-4 h-4 text-muted-foreground" />
                <h3 className="text-xs font-bold text-foreground uppercase tracking-wide">{t('pieces.recommandations_titre')}</h3>
              </div>
              <p className="text-[11px] text-muted-foreground">{t('pieces.recommandations_aide', { pays: rapport.pays_nom })}</p>
              {rapport.recommandations.map((r, i) => (
                <div key={i} className="rounded-xl border border-dashed border-line p-3 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">{r.piece}</span>
                    <span className="text-[10px] text-muted-foreground">{t('pieces.vu_fois', { n: String(r.vu_fois) })}</span>
                  </div>
                  <button
                    onClick={() => confirmer(r.piece)}
                    disabled={!!confirmationEnCours}
                    className="btn-secondary !py-1 !px-2.5 !text-[11px] cursor-pointer disabled:opacity-50"
                  >
                    {confirmationEnCours === r.piece ? <RefreshCw className="w-3 h-3 animate-spin" /> : <PlusCircle className="w-3 h-3" />}
                    {t('pieces.ajouter_dossier')}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
