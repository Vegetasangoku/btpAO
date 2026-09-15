import pathlib
p = pathlib.Path.home() / "mnt/reponse_au_ao/apps/web/src/lib/api.ts"
content = p.read_text()

def replace_once(content, old, new, label):
    n = content.count(old)
    assert n == 1, f"{label}: expected 1 match, got {n}"
    return content.replace(old, new, 1)

old = '''  verifierPieces: (projectId: string) =>
    fetcher<PiecesRapport>(`/dossiers/${projectId}/pieces`, { method: 'POST' }),'''
new = '''  // 15/09 : piecesConfirmees -- libelles de recommandations (historique tenant+pays,
  // cf. rapport.recommandations) que l'utilisateur vient d'accepter pour ce dossier ;
  // omis ou vide = comportement inchange (pas de corps envoye).
  verifierPieces: (projectId: string, piecesConfirmees?: string[]) =>
    fetcher<PiecesRapport>(`/dossiers/${projectId}/pieces`, {
      method: 'POST',
      ...(piecesConfirmees && piecesConfirmees.length
        ? { body: JSON.stringify({ pieces_confirmees: piecesConfirmees }) }
        : {}),
    }),'''
content = replace_once(content, old, new, "verifierPieces-piecesConfirmees")

p.write_text(content)
print("OK: api.ts edit applied")
