import pathlib
p = pathlib.Path.home() / "mnt/reponse_au_ao/apps/api/app/services/pieces_service.py"
content = p.read_text()

def replace_once(content, old, new, label):
    n = content.count(old)
    assert n == 1, f"{label}: expected 1 match, got {n}"
    return content.replace(old, new, 1)

# A: mark confirmed-from-history pieces explicitly, so the frontend can label their
# citation distinctly from a citation genuinely found in THIS project's own DCE.
oldA = '''        if _h:
            exigences.append({
                "piece": _h.piece_label, "citation": _h.piece_citation,
                "origine": _t("historique", L, pays=nom_pays(pays, L, profil.country_name if profil else pays)),
                "type": _h.piece_type,
            })'''
newA = '''        if _h:
            exigences.append({
                "piece": _h.piece_label, "citation": _h.piece_citation,
                "origine": _t("historique", L, pays=nom_pays(pays, L, profil.country_name if profil else pays)),
                "type": _h.piece_type, "historique": True,
            })'''
content = replace_once(content, oldA, newA, "A-mark-historique")

# B: dedup merge -- if a duplicate entry's citation comes FROM a confirmed historique
# piece, carry the marker over too, so the merged/kept line stays honestly labeled.
oldB = '''        if doublon:
            if e.get("citation") and not doublon.get("citation"):
                doublon.update(citation=e["citation"], origine=doublon["origine"] + " + " + e["origine"])
            continue'''
newB = '''        if doublon:
            if e.get("citation") and not doublon.get("citation"):
                doublon.update(citation=e["citation"], origine=doublon["origine"] + " + " + e["origine"])
                if e.get("historique"):
                    doublon["historique"] = True
            continue'''
content = replace_once(content, oldB, newB, "B-dedup-carries-historique")

p.write_text(content)
print("OK: historique marker edits applied")
