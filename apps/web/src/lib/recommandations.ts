/**
 * Consolidation des recommandations (10/09).
 *
 * Constat : le moteur produit ses « lacunes » section par section. Comme la
 * plupart tiennent à une pièce manquante commune (le règlement de consultation,
 * par exemple), l'utilisateur voyait la même demande répétée neuf fois, noyée
 * dans une soixantaine d'entrées, formulée en sigles, et sans le moindre bouton
 * pour agir. D'où son retour : « je ne comprends ni l'action attendue ni
 * comment l'application va concrètement m'aider à l'appliquer ».
 *
 * Ce module transforme cette liste brute en un plan d'action :
 *   1. on regroupe les demandes identiques (une ligne, pas neuf) ;
 *   2. on dit combien de sections chaque point débloque — c'est ça, l'enjeu ;
 *   3. on rattache chaque point à l'écran qui permet de le traiter ;
 *   4. on énonce l'action à l'infinitif, en français lisible.
 *
 * Rien n'est inventé : si une lacune ne correspond à aucune action connue,
 * elle est conservée telle quelle, sans lien, plutôt que rangée de force.
 */

export interface LacuneBrute {
  missing?: string;
  impact?: string;
  how_to_fix?: string;
  lien?: string;
  lien_libelle?: string;
}

export interface Recommandation {
  /** Identifiant stable, sert de clé React et de test d'unicité. */
  id: string;
  /** L'action, à l'infinitif : « Déposer le règlement de consultation ». */
  action: string;
  /** Pourquoi ça compte, en une phrase. */
  pourquoi: string;
  /** Ce que l'application fera une fois le point traité. */
  ceQueLAppFait: string;
  /** Où aller pour le faire. Absent si aucun écran ne s'y prête. */
  lien?: string;
  lienLibelle?: string;
  /** Sections concernées (clés), pour dire « débloque 9 sections ». */
  sections: string[];
  /** Détail original, conservé pour qui veut le texte du moteur. */
  details: string[];
  /** Priorité calculée : plus le chiffre est haut, plus c'est urgent. */
  poids: number;
}

/** Normalise pour comparer : minuscules, sans accents, sans ponctuation. */
function normaliser(texte: string): string {
  return (texte || '')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9 ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Familles d'actions reconnues. L'ordre compte : la première qui correspond
 * l'emporte, donc les motifs les plus spécifiques passent devant.
 */
interface Famille {
  id: string;
  /** Tous les mots doivent être présents (dans la version normalisée). */
  motsRequis: string[][];
  action: string;
  ceQueLAppFait: string;
  lien: (projectId: string) => string | undefined;
  lienLibelle: string;
  poids: number;
}

const FAMILLES: Famille[] = [
  {
    id: 'reglement-consultation',
    motsRequis: [['reglement', 'consultation'], ['critere', 'notation'], ['rc']],
    action: 'Déposer le règlement de consultation',
    ceQueLAppFait:
      "L'application en extrait les critères de notation et leur poids, puis mesure chaque section contre cette grille au lieu de deviner ce que l'acheteur attend.",
    lien: (p) => `/projects/${p}/dce`,
    lienLibelle: 'Déposer la pièce',
    poids: 100,
  },
  {
    id: 'pieces-techniques',
    motsRequis: [['cctp'], ['plan', 'fonctionnel'], ['lot', 'decomposition'], ['dpgf'], ['metre']],
    action: 'Compléter les pièces techniques du dossier',
    ceQueLAppFait:
      'Chaque exigence chiffrée du cahier technique devient citable dans le mémoire, avec son article de référence.',
    lien: (p) => `/projects/${p}/dce`,
    lienLibelle: 'Ajouter les pièces',
    poids: 90,
  },
  {
    id: 'calendrier',
    motsRequis: [['calendrier', 'contractuel'], ['planning', 'detaille'], ['jalon', 'validation']],
    action: 'Renseigner le calendrier contractuel',
    ceQueLAppFait:
      'Le planning de chantier est recalé sur les dates réelles du marché, jalons et marges compris, au lieu de durées types.',
    lien: (p) => `/projects/${p}/decisions`,
    lienLibelle: 'Saisir les dates',
    poids: 80,
  },
  {
    id: 'effectifs',
    motsRequis: [['effectif'], ['nominative'], ['organigramme'], ['habilitation'], ['sst']],
    action: "Déclarer vos effectifs et l'encadrement affecté",
    ceQueLAppFait:
      "Les noms déclarés remplacent les « À pourvoir » de l'organigramme, et les qualifications deviennent vérifiables une par une.",
    lien: (p) => `/projects/${p}/decisions`,
    lienLibelle: 'Déclarer les équipes',
    poids: 75,
  },
  {
    id: 'sites-reference',
    motsRequis: [['site', 'reference']],
    action: 'Corriger vos sites de référence',
    ceQueLAppFait:
      'Les pages lisibles alimentent la rédaction avec vos propres références ; celles en erreur sont aujourd’hui ignorées en silence.',
    lien: () => '/dashboard/company',
    lienLibelle: 'Vérifier les adresses',
    poids: 60,
  },
  {
    id: 'apprentissages',
    motsRequis: [['enseignement'], ['apprentissage']],
    action: 'Valider les enseignements des dossiers passés',
    ceQueLAppFait:
      'Vos corrections manuelles sont rejouées automatiquement sur les prochains dossiers, au lieu d’être refaites à chaque fois.',
    lien: () => '/knowledge',
    lienLibelle: 'Voir les propositions',
    poids: 50,
  },
  {
    id: 'materiels',
    motsRequis: [['vgp'], ['maintenance'], ['engin'], ['materiel'], ['grue', 'levage']],
    action: 'Joindre les justificatifs de vos matériels',
    ceQueLAppFait:
      'Chaque engin cité peut être présenté avec son contrôle réglementaire à jour, ce que l’acheteur vérifie systématiquement.',
    lien: () => '/dashboard/company',
    lienLibelle: 'Ajouter les documents',
    poids: 45,
  },
  {
    id: 'environnement',
    motsRequis: [['pemd'], ['fdes'], ['re2020'], ['carbone'], ['dechet', 'tonnage'], ['exutoire']],
    action: 'Fournir les données environnementales du chantier',
    ceQueLAppFait:
      'Les objectifs annoncés (valorisation, carbone) sont convertis en quantités justifiées plutôt qu’en pourcentages non étayés.',
    lien: (p) => `/projects/${p}/dce`,
    lienLibelle: 'Ajouter les études',
    poids: 40,
  },
  {
    id: 'securite',
    motsRequis: [['pgc'], ['sps'], ['ppsps']],
    action: 'Transmettre le plan général de sécurité du chantier',
    ceQueLAppFait:
      'Les mesures de prévention sont rattachées aux risques réellement identifiés sur cette opération, pas à une trame générique.',
    lien: (p) => `/projects/${p}/dce`,
    lienLibelle: 'Déposer le plan',
    poids: 35,
  },
  {
    id: 'geotechnique',
    motsRequis: [['geotechnique'], ['g1'], ['g2'], ['fondation', 'sol']],
    action: "Fournir l'étude de sol",
    ceQueLAppFait:
      'Les méthodes de fondation et les cadences de terrassement sont justifiées par les résultats de sondage.',
    lien: (p) => `/projects/${p}/dce`,
    lienLibelle: "Déposer l'étude",
    poids: 30,
  },
];

function familleDe(texte: string): Famille | undefined {
  const n = normaliser(texte);
  return FAMILLES.find((f) =>
    f.motsRequis.some((groupe) => groupe.every((mot) => n.includes(mot))),
  );
}

export interface SectionAvecLacunes {
  section_key?: string;
  title?: string;
  visual_placeholders?: unknown;
}

function lacunesDe(section: SectionAvecLacunes): LacuneBrute[] {
  const ph = section.visual_placeholders;
  if (!Array.isArray(ph)) return [];
  const bloc = ph.find(
    (b) => typeof b === 'object' && b !== null && (b as { type?: string }).type === 'lacunes',
  ) as { items?: LacuneBrute[] } | undefined;
  return Array.isArray(bloc?.items) ? bloc!.items! : [];
}

/**
 * Construit le plan d'action consolidé à partir des sections générées.
 * Déduplique, regroupe, ordonne, et rattache chaque point à un écran.
 */
export function construireRecommandations(
  sections: SectionAvecLacunes[],
  projectId: string,
): Recommandation[] {
  const parId = new Map<string, Recommandation>();

  for (const section of sections) {
    const cle = section.section_key || section.title || '?';
    for (const lacune of lacunesDe(section)) {
      const brut = `${lacune.missing || ''} ${lacune.how_to_fix || ''}`.trim();
      if (!brut) continue;

      const famille = familleDe(brut);
      // Sans famille reconnue, on regroupe sur le texte normalisé : on
      // déduplique quand même, mais on n'invente ni action ni destination.
      const id = famille ? famille.id : `libre:${normaliser(lacune.missing || brut).slice(0, 60)}`;

      let reco = parId.get(id);
      if (!reco) {
        reco = {
          id,
          action: famille ? famille.action : (lacune.missing || '').trim() || 'Point à traiter',
          pourquoi: (lacune.impact || '').trim(),
          ceQueLAppFait: famille ? famille.ceQueLAppFait : '',
          lien: famille ? famille.lien(projectId) : lacune.lien,
          lienLibelle: famille ? famille.lienLibelle : lacune.lien_libelle,
          sections: [],
          details: [],
          poids: famille ? famille.poids : 10,
        };
        parId.set(id, reco);
      }

      if (!reco.sections.includes(cle)) reco.sections.push(cle);
      const detail = (lacune.how_to_fix || lacune.missing || '').trim();
      if (detail && !reco.details.includes(detail)) reco.details.push(detail);
      if (!reco.pourquoi && lacune.impact) reco.pourquoi = lacune.impact.trim();
    }
  }

  // Un point qui bloque neuf sections passe devant un point qui en bloque une.
  return Array.from(parId.values()).sort(
    (a, b) => b.sections.length * 10 + b.poids - (a.sections.length * 10 + a.poids),
  );
}
