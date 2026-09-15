import pathlib
p = pathlib.Path.home() / "mnt/reponse_au_ao/apps/web/src/components/i18n-provider.tsx"
content = p.read_text()

def replace_once(content, old, new, label):
    n = content.count(old)
    assert n == 1, f"{label}: expected 1 match, got {n}"
    return content.replace(old, new, 1)

old = """  'pieces.lien_non_verifie': { fr: 'non vérifié', en: 'not verified', ar: 'غير متحقق منه' },"""
new = """  'pieces.lien_non_verifie': { fr: 'non vérifié', en: 'not verified', ar: 'غير متحقق منه' },
  // 15/09 : recommandations issues de l'historique tenant+pays -- pieces deja vues dans un
  // dossier precedent, proposees en option pour celui-ci (« on fait les reco et on apprend »).
  'pieces.recommandations_titre': { fr: 'Déjà vues dans un dossier précédent', en: 'Seen in a previous tender', ar: 'ظهرت في ملف سابق' },
  'pieces.recommandations_aide': { fr: "Ces pièces ont déjà été demandées dans un dossier {pays} précédent pour ce compte. Ajoutez celles qui s'appliquent à ce dossier-ci.", en: 'These documents were already required in a previous {pays} tender for this account. Add the ones that apply to this one.', ar: 'طُلبت هذه الوثائق سابقاً في ملف مناقصة سابق في {pays} لهذا الحساب. أضف ما ينطبق منها على هذا الملف.' },
  'pieces.vu_fois': { fr: 'Vu {n} fois', en: 'Seen {n} time(s)', ar: 'ظهرت {n} مرة' },
  'pieces.ajouter_dossier': { fr: 'Ajouter à ce dossier', en: 'Add to this tender', ar: 'إضافة إلى هذا الملف' },"""
content = replace_once(content, old, new, "pieces-recommandations-i18n-keys")

p.write_text(content)
print("OK: i18n-provider.tsx edit applied")
