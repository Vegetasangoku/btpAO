/**
 * Espace client réellement consulté.
 *
 * Constat du 10/09, signalé par le client : « Ouvrir l'espace entreprise »
 * depuis l'administration n'ouvrait PAS un espace dédié à l'administrateur,
 * mais l'espace du premier client (BTP Entreprise & Travaux Publics). La cause
 * n'était pas un bug d'affichage : le compte d'administration n'avait aucun
 * `tenant_id`, et le code — front comme API — le rabattait sur un identifiant
 * de tenant écrit en dur. Les deux comptes n'étaient donc pas isolés du tout :
 * c'était le même espace, vu sous deux étiquettes.
 *
 * Depuis, l'administrateur a son propre espace, et consulter celui d'un client
 * est devenu un acte EXPLICITE : il choisit l'entreprise dans l'administration,
 * ce choix est mémorisé ici, et un bandeau le lui rappelle en permanence. Il
 * n'y a plus de repli silencieux : sans espace, l'API refuse et le dit.
 */

const CLE_ESPACE = 'btp_espace_consulte';
const CLE_LIBELLE = 'btp_espace_consulte_nom';

export type EspaceConsulte = { id: string; nom: string } | null;

function disponible(): boolean {
  return typeof window !== 'undefined';
}

/** L'espace client que l'administrateur a explicitement choisi d'inspecter. */
export function lireEspaceConsulte(): EspaceConsulte {
  if (!disponible()) return null;
  try {
    const id = window.localStorage.getItem(CLE_ESPACE);
    if (!id) return null;
    return { id, nom: window.localStorage.getItem(CLE_LIBELLE) || id };
  } catch {
    return null;
  }
}

/** Mémorise l'espace client à inspecter. `null` revient à son propre espace. */
export function ecrireEspaceConsulte(espace: EspaceConsulte): void {
  if (!disponible()) return;
  try {
    if (!espace) {
      window.localStorage.removeItem(CLE_ESPACE);
      window.localStorage.removeItem(CLE_LIBELLE);
      return;
    }
    window.localStorage.setItem(CLE_ESPACE, espace.id);
    window.localStorage.setItem(CLE_LIBELLE, espace.nom);
  } catch {
    /* navigation privée, stockage refusé : on continue sans mémoriser */
  }
}

/**
 * Identifiant d'espace à envoyer à l'API.
 *
 * Ordre volontaire : l'espace explicitement inspecté l'emporte (c'est un choix
 * conscient de l'administrateur), sinon celui du jeton de session. Aucun repli
 * codé en dur : renvoyer `null` est la bonne réponse quand on ne sait pas.
 */
export function resoudreEspace(tenantDuJeton?: string | null): string | null {
  const choisi = lireEspaceConsulte();
  if (choisi?.id) return choisi.id;
  return tenantDuJeton || null;
}
