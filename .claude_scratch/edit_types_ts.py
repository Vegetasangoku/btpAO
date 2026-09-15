import pathlib
p = pathlib.Path.home() / "mnt/reponse_au_ao/apps/web/src/lib/types.ts"
content = p.read_text()

def replace_once(content, old, new, label):
    n = content.count(old)
    assert n == 1, f"{label}: expected 1 match, got {n}"
    return content.replace(old, new, 1)

old = '''    recherche: string | null;
    liens: { titre: string; url: string; format: string; verifie: boolean; extrait: string; erreur: string | null }[];
  }[];
}

export interface CadreRapport {'''
new = '''    recherche: string | null;
    liens: { titre: string; url: string; format: string; verifie: boolean; extrait: string; erreur: string | null }[];
  }[];
  // 15/09 : pièces vues dans un dossier précédent (même tenant, même pays) mais absentes de
  // celui-ci -- proposées en option ; confirmer une recommandation la fait rejoindre "pieces".
  recommandations?: { piece: string; type: string | null; vu_fois: number; dernier_dossier_le: string | null }[];
}

export interface CadreRapport {'''
content = replace_once(content, old, new, "PiecesRapport-recommandations")

p.write_text(content)
print("OK: types.ts edit applied")
