import pathlib
p = pathlib.Path.home() / "mnt/reponse_au_ao/apps/api/app/api/admin_dossiers.py"
content = p.read_text()

def replace_once(content, old, new, label):
    n = content.count(old)
    assert n == 1, f"{label}: expected 1 match, got {n}"
    return content.replace(old, new, 1)

old = '''    """Pièces exigées (DCE + pays du marché), ce qui est déjà disponible, et pour ce qui
    manque, lien vers le formulaire sur les portails officiels du pays (11/09)."""
    from app.services.pieces_service import analyser_pieces
    tenant, project = await _get_project_and_tenant(project_id, current_user, db)
    return await analyser_pieces(db, tenant.id, project, chercher=chercher,
                                 langue=request.headers.get("x-ui-language") or "fr")'''
new = '''    """Pièces exigées (DCE + pays du marché), ce qui est déjà disponible, et pour ce qui
    manque, lien vers le formulaire sur les portails officiels du pays (11/09).
    15/09 : accepte en option un corps JSON {"pieces_confirmees": [...]} -- libellés de
    recommandations (historique tenant+pays) que l'utilisateur vient de confirmer pour ce
    dossier ; corps absent ou vide = comportement inchangé (rétrocompatible)."""
    from app.services.pieces_service import analyser_pieces
    tenant, project = await _get_project_and_tenant(project_id, current_user, db)
    pieces_confirmees = None
    try:
        corps = await request.json()
        if isinstance(corps, dict):
            brut = corps.get("pieces_confirmees")
            if isinstance(brut, list):
                pieces_confirmees = [str(x)[:250] for x in brut if str(x or "").strip()][:30] or None
    except Exception:
        pieces_confirmees = None
    return await analyser_pieces(db, tenant.id, project, chercher=chercher,
                                 langue=request.headers.get("x-ui-language") or "fr",
                                 pieces_confirmees=pieces_confirmees)'''
content = replace_once(content, old, new, "endpoint-pieces-confirmees")

p.write_text(content)
print("OK: endpoint edit applied")
