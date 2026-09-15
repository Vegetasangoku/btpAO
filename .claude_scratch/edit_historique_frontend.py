import pathlib

# 1. types.ts -- add historique flag to the piece item shape
p1 = pathlib.Path.home() / "mnt/reponse_au_ao/apps/web/src/lib/types.ts"
c1 = p1.read_text()
old1 = '''    // 15/09 : brouillon rédigé par l'IA (pays sans formulaire national fixe) — voir "redigeable".
    redigeable: string | null;
    telechargements?: { code: string; libelle: string; chemin: string; type?: 'template' | 'draft' }[];'''
new1 = '''    // 15/09 : brouillon rédigé par l'IA (pays sans formulaire national fixe) — voir "redigeable".
    redigeable: string | null;
    // 15/09 : true si "citation" vient d'un dossier précédent confirmé par l'utilisateur
    // (recommandation acceptée), pas du DCE de CE dossier -- distingue l'affichage des deux.
    historique?: boolean;
    telechargements?: { code: string; libelle: string; chemin: string; type?: 'template' | 'draft' }[];'''
assert c1.count(old1) == 1, f"types.ts: expected 1 match, got {c1.count(old1)}"
p1.write_text(c1.replace(old1, new1, 1))
print("types.ts OK")

# 2. i18n-provider.tsx -- prefix label for a historique-sourced citation
p2 = pathlib.Path.home() / "mnt/reponse_au_ao/apps/web/src/components/i18n-provider.tsx"
c2 = p2.read_text()
old2 = """  'pieces.ajouter_dossier': { fr: 'Ajouter à ce dossier', en: 'Add to this tender', ar: 'إضافة إلى هذا الملف' },"""
new2 = """  'pieces.ajouter_dossier': { fr: 'Ajouter à ce dossier', en: 'Add to this tender', ar: 'إضافة إلى هذا الملف' },
  // 15/09 : marque la citation d'une piece confirmee depuis l'historique -- pour ne jamais la
  // laisser ressembler a une citation trouvee dans le DCE de CE dossier (rien n'est invente).
  'pieces.citation_historique': { fr: 'Passage du dossier précédent :', en: 'Passage from the previous tender:', ar: 'مقطع من الملف السابق:' },"""
assert c2.count(old2) == 1, f"i18n: expected 1 match, got {c2.count(old2)}"
p2.write_text(c2.replace(old2, new2, 1))
print("i18n-provider.tsx OK")

# 3. pieces-card.tsx -- render the citation distinctly when p.historique is true
p3 = pathlib.Path.home() / "mnt/reponse_au_ao/apps/web/src/components/export/pieces-card.tsx"
c3 = p3.read_text()
old3 = '''                {p.citation && <p className="text-[11px] italic text-muted-foreground">« {p.citation} »</p>}'''
new3 = '''                {p.citation && (
                  <p className="text-[11px] italic text-muted-foreground">
                    {p.historique && <span className="not-italic font-semibold text-muted-foreground/80">{t('pieces.citation_historique')} </span>}
                    « {p.citation} »
                  </p>
                )}'''
assert c3.count(old3) == 1, f"pieces-card.tsx: expected 1 match, got {c3.count(old3)}"
p3.write_text(c3.replace(old3, new3, 1))
print("pieces-card.tsx OK")
