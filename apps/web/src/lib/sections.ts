/**
 * Liste de référence des sections du mémoire technique (10/09).
 *
 * Elle était dupliquée — et divergente — entre l'éditeur et la page d'export :
 * l'export vérifiait la complétion sur 5 sections dont une (`qse_environnement`)
 * n'était jamais générée par l'éditeur, donc affichée « en attente » pour
 * toujours, tandis que 5 sections réellement produites n'apparaissaient nulle
 * part dans le récapitulatif. Une seule source de vérité désormais.
 */

export interface MemoSection {
  key: string;
  /** Clé i18n utilisée par l'éditeur. */
  labelKey: string;
  /** Libellé numéroté affiché dans le récapitulatif d'export et l'aperçu global. */
  title: string;
  mandatory: boolean;
  /** Section rendue par un éditeur visuel dédié et non par l'éditeur de texte. */
  visual?: 'gantt';
}

export const MEMO_SECTIONS: MemoSection[] = [
  { key: 'presentation_entreprise', labelKey: 'editor.section.presentation_entreprise', title: '1. Présentation de l’entreprise', mandatory: true },
  { key: 'references_similaires',   labelKey: 'editor.section.references_similaires',   title: '2. Références similaires',            mandatory: true },
  { key: 'moyens_humains',          labelKey: 'editor.section.moyens_humains',          title: '3. Moyens humains & encadrement',     mandatory: true },
  { key: 'moyens_materiels',        labelKey: 'editor.section.moyens_materiels',        title: '4. Moyens matériels & équipements',   mandatory: true },
  { key: 'methodologie_phasage',    labelKey: 'editor.section.methodologie_phasage',    title: '5. Méthodologie & phasage travaux',   mandatory: true },
  { key: 'qualite_controle',        labelKey: 'editor.section.qualite_controle',        title: '6. Qualité & contrôles',              mandatory: true },
  { key: 'securite_ppsps',          labelKey: 'editor.section.securite_ppsps',          title: '7. Sécurité & PPSPS',                 mandatory: true },
  { key: 'rse_environnement',       labelKey: 'editor.section.rse_environnement',       title: '8. RSE & environnement',              mandatory: false },
  { key: 'sous_traitance',          labelKey: 'editor.section.sous_traitance',          title: '9. Sous-traitance',                   mandatory: false },
  { key: 'planning_gantt',          labelKey: 'editor.section.planning_gantt',          title: '10. Planning des travaux',            mandatory: true, visual: 'gantt' },
];

/** Sections rédigées par le modèle, hors visuels — celles que l'auto-remplissage traite. */
export const AUTO_FILL_KEYS = MEMO_SECTIONS
  .filter((s) => s.mandatory && !s.visual)
  .map((s) => s.key);
