import pathlib
p = pathlib.Path.home() / "mnt/reponse_au_ao/apps/web/src/components/export/pieces-card.tsx"
content = p.read_text()

def replace_once(content, old, new, label):
    n = content.count(old)
    assert n == 1, f"{label}: expected 1 match, got {n}"
    return content.replace(old, new, 1)

# 1. Import PlusCircle and History icons
old1 = "import { ClipboardCheck, RefreshCw, CheckCircle2, AlertTriangle, FileDown, ExternalLink, Wand2, PenLine, Info } from 'lucide-react';"
new1 = "import { ClipboardCheck, RefreshCw, CheckCircle2, AlertTriangle, FileDown, ExternalLink, Wand2, PenLine, Info, History, PlusCircle } from 'lucide-react';"
content = replace_once(content, old1, new1, "1-icon-imports")

# 2. State + effect: track confirmed recommendations across clicks, reset on language change
old2 = """  const [rapport, setRapport] = useState<PiecesRapport | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  // Changement de langue : le rapport (redige par l'API) doit etre refait.
  React.useEffect(() => { setRapport(null); }, [language]);

  const lancer = async () => {
    setEnCours(true);
    setErreur(null);
    try {
      setRapport(await api.verifierPieces(projectId));
    } catch (e: any) {
      setErreur(e?.message || String(e));
    } finally {
      setEnCours(false);
    }
  };"""
new2 = """  const [rapport, setRapport] = useState<PiecesRapport | null>(null);
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
  };"""
content = replace_once(content, old2, new2, "2-state-and-confirmer")

# 3. UI block: render recommandations after the main pieces list
old3 = """            ))}
          </div>
        </div>
      )}
    </div>
  );
}"""
new3 = """            ))}
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
}"""
content = replace_once(content, old3, new3, "3-recommandations-ui-block")

p.write_text(content)
print("OK: pieces-card.tsx edit applied")
