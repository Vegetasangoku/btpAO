'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { BarChart3, RefreshCw, Calendar, AlertTriangle, Plus, Trash2, Flag, Sparkles, SlidersHorizontal, Layers, Save, CornerDownRight, Wand2, X } from 'lucide-react';
// @ts-ignore -- vendored, untyped-by-upstream JS bundle; see index.d.ts for the hand-written surface we rely on.
import Gantt from '@/vendor/frappe-gantt/frappe-gantt.es.js';
import '@/vendor/frappe-gantt/frappe-gantt.css';
import '@/vendor/frappe-gantt/frappe-gantt-overrides.css';
import { api } from '@/lib/api';
import { GanttTask, GanttSettings, GanttDetailReport } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';
import { Bascule } from '@/components/ui/bascule';

const HEX_RE = /^#?[0-9a-fA-F]{6}$/;

function parseHex(hex: unknown): [number, number, number] | null {
  if (typeof hex !== 'string' || !HEX_RE.test(hex.trim())) return null;
  const n = parseInt(hex.trim().replace('#', ''), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Eclaircit (amount > 0) ou fonce (amount < 0) une couleur hex. Sert a deriver la
 *  teinte de progression et le liseré depuis la seule primary_color de la charte,
 *  pour ne pas demander trois couleurs a l'utilisateur. */
function shade(hex: string, amount: number): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  const out = rgb.map((v) => Math.max(0, Math.min(255, Math.round(v * (1 + amount)))));
  return `#${((out[0] << 16) | (out[1] << 8) | out[2]).toString(16).padStart(6, '0')}`;
}

/** Noir ou blanc selon la luminance percue (ITU-R BT.601) -- meme regle que
 *  _readable_text_color cote backend, pour que le Gantt interactif et le PNG genere
 *  prennent la meme decision sur une charte claire (jaune, cyan...). */
function readableOn(hex: string): string {
  const rgb = parseHex(hex);
  if (!rgb) return '#ffffff';
  return (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000 > 150 ? '#0f172a' : '#ffffff';
}

/** shape_style de la charte -> arrondi des barres. Memes trois valeurs que le backend
 *  (_boxstyle_for dans diagram_service), pour que planning interactif et PNG exporte
 *  aient la meme silhouette. */
const SHAPE_RADIUS: Record<string, string> = {
  anguleux: '0px',
  arrondi: '4px',
  pilule: '999px',
};

/** Luminance relative percue, 0 (noir) a 1 (blanc). */
function luminance(hex: string): number {
  const rgb = parseHex(hex);
  if (!rgb) return 0.5;
  return (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000 / 255;
}

/**
 * Une couleur de charte peut etre inexploitable pour une barre de planning : le
 * secondary_color de ce tenant est #0f172a, quasi noir, donc invisible sur le fond
 * sombre du graphique (#111A24) -- et symetriquement une charte tres claire
 * disparaitrait en theme clair. On n'ecrase pas la charte pour autant : on se contente
 * d'ecarter la couleur quand elle sort de la bande lisible, et l'appelant retombe alors
 * sur une teinte derivee de la couleur primaire.
 */
function isUsableBarColor(hex: string): boolean {
  const l = luminance(hex);
  return l > 0.16 && l < 0.9;
}

function buildGanttBrandVars(cfg: Record<string, any> | null | undefined): Record<string, string> {
  const vars: Record<string, string> = {};
  if (!cfg) return vars;
  const primary = typeof cfg.primary_color === 'string' && HEX_RE.test(cfg.primary_color.trim())
    ? cfg.primary_color.trim() : null;
  const rawSecondary = typeof cfg.secondary_color === 'string' && HEX_RE.test(cfg.secondary_color.trim())
    ? cfg.secondary_color.trim() : null;
  // Jalons : on n'accepte la couleur secondaire que si elle reste lisible (voir
  // isUsableBarColor). Sinon on derive du primaire plus bas.
  const secondary = rawSecondary && isUsableBarColor(rawSecondary) ? rawSecondary : null;
  if (primary) {
    vars['--btp-gantt-bar'] = primary;
    vars['--btp-gantt-bar-progress'] = shade(primary, -0.28);
    vars['--btp-gantt-bar-stroke'] = shade(primary, -0.45);
    vars['--btp-gantt-bar-text'] = readableOn(primary);
    vars['--btp-gantt-today'] = primary;
    if (!secondary) {
      vars['--btp-gantt-milestone'] = shade(primary, 0.22);
      vars['--btp-gantt-milestone-progress'] = primary;
    }
  }
  if (secondary) {
    vars['--btp-gantt-milestone'] = secondary;
    vars['--btp-gantt-milestone-progress'] = shade(secondary, -0.28);
  }
  const radius = SHAPE_RADIUS[String(cfg.shape_style || '').toLowerCase()];
  if (radius) vars['--btp-gantt-radius'] = radius;
  return vars;
}

/** Reglages par defaut -- identiques a DEFAULT_GANTT_SETTINGS cote API. */
const REGLAGES_DEFAUT: GanttSettings = {
  niveau_detail: 'sous_taches',
  couleur_par: 'phase',
  palette: [],
  chemin_critique: true,
  jalons: true,
  durees: true,
  liens: true,
};

const PALETTE_BTP = ['#0369a1', '#0f766e', '#b45309', '#7c3aed', '#be123c', '#4d7c0f', '#1d4ed8', '#a16207'];

/** Eclaircit vers le blanc (amount > 0) ou fonce (amount < 0) -- meme formule que
 *  _shade dans gantt_service.py, pour que l'ecran et le PNG du memoire concordent. */
function teinte(hex: string, amount: number): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  const out = rgb.map((c) => Math.round(amount >= 0 ? c + (255 - c) * amount : c * (1 + amount)));
  return `#${out.map((v) => Math.max(0, Math.min(255, v)).toString(16).padStart(2, '0')).join('')}`;
}

/** Couleur de chaque ligne selon les reglages : phase / lot / uniforme, les
 *  sous-taches en plus clair, la couleur posee sur la ligne en priorite.
 *  Transcription exacte de color_for() dans gantt_service.py. */
function couleursDesLignes(tasks: GanttTask[], reglages: GanttSettings, brand: string | null): Record<string, string> {
  const brandOk = brand && HEX_RE.test(brand) ? (brand.startsWith('#') ? brand : `#${brand}`) : null;
  const palette = reglages.palette.length
    ? reglages.palette
    : brandOk ? [brandOk, ...PALETTE_BTP.filter((c) => c.toLowerCase() !== brandOk.toLowerCase())] : PALETTE_BTP;
  const parId = new Map(tasks.map((t) => [t.id, t]));
  const racine = (t: GanttTask): GanttTask => {
    let cur = t;
    const vus = new Set<string>();
    while (cur.parent_id && parId.has(cur.parent_id) && !vus.has(cur.id)) {
      vus.add(cur.id);
      cur = parId.get(cur.parent_id)!;
    }
    return cur;
  };
  const phase: Record<string, string> = {};
  tasks.filter((t) => !t.parent_id).forEach((t, i) => {
    phase[t.id] = (t.color && HEX_RE.test(t.color) ? t.color : null) || palette[i % palette.length];
  });
  const lots: Record<string, string> = {};
  const out: Record<string, string> = {};
  for (const t of tasks) {
    const lvl = t.level ?? 0;
    if (t.color && HEX_RE.test(t.color)) { out[t.id] = t.color; continue; }
    let base: string;
    if (reglages.couleur_par === 'uniforme') base = palette[0];
    else if (reglages.couleur_par === 'lot' && (t.lot || '').trim()) {
      const k = t.lot!.trim().toLowerCase();
      if (!lots[k]) lots[k] = palette[Object.keys(lots).length % palette.length];
      base = lots[k];
    } else base = phase[racine(t).id] || palette[0];
    out[t.id] = lvl >= 2 ? teinte(base, 0.35) : base;
  }
  return out;
}

interface InteractiveGanttChartProps {
  projectId: string;
  projectTitle?: string;
}

/** Adds `days` to an ISO "YYYY-MM-DD" string via a UTC-noon pivot (sidesteps any DST
 *  edge case entirely) -- used for pure date-only arithmetic that never touches a
 *  timezone-sensitive `Date` object constructed by the browser. */
function addDaysIso(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number);
  const t = Date.UTC(y, (m || 1) - 1, d || 1, 12) + days * 86400000;
  const dt = new Date(t);
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}-${String(dt.getUTCDate()).padStart(2, '0')}`;
}

/** Reads a `Date` object's LOCAL calendar fields (never `.toISOString()`, which
 *  converts to UTC and can silently shift the date by a day depending on the
 *  viewer's timezone offset) -- used to convert the Date objects frappe-gantt hands
 *  back from on_date_change into the "YYYY-MM-DD" strings the API expects. */
function localIso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function InteractiveGanttChart({ projectId, projectTitle = 'Projet BTP' }: InteractiveGanttChartProps) {
  const { t, language } = useTranslation();
  const [tasks, setTasks] = useState<GanttTask[]>([]);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [authExpired, setAuthExpired] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportInfo, setExportInfo] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'Day' | 'Week' | 'Month'>('Week');
  // Personnalisation du planning (10/09).
  // Retour Charbel : « les options de personnalisation des schémas sont trop
  // limitées ». Il n'y avait en effet que l'échelle de temps. Chaque réglage
  // ci-dessous s'appuie sur une donnée réellement présente sur les tâches
  // (jalon, chemin critique, avancement, dépendances) : aucun n'est décoratif.
  const [panneauOuvert, setPanneauOuvert] = useState(false);
  const [filtre, setFiltre] = useState<'tout' | 'critique' | 'jalons'>('tout');
  const [densite, setDensite] = useState<'compact' | 'normal' | 'aere'>('normal');
  const [afficherAvancement, setAfficherAvancement] = useState(true);
  // Reglages partages avec le PNG du memoire (11/09) : niveau de detail, couleurs,
  // chemin critique, jalons, durees, liens. Charges depuis l'API, enregistres par
  // projet ou comme defaut de l'entreprise.
  const [reglages, setReglages] = useState<GanttSettings>(REGLAGES_DEFAUT);
  const [palettes, setPalettes] = useState<Record<string, string[]>>({});
  const [brandColor, setBrandColor] = useState<string | null>(null);
  const [reglagesModifies, setReglagesModifies] = useState(false);
  const [enregistrement, setEnregistrement] = useState<'projet' | 'entreprise' | null>(null);
  const [messageReglages, setMessageReglages] = useState<string | null>(null);
  const majReglages = useCallback((patch: Partial<GanttSettings>) => {
    setReglages((r) => ({ ...r, ...patch }));
    setReglagesModifies(true);
    setMessageReglages(null);
  }, []);
  const afficherLiens = reglages.liens;
  const setAfficherLiens = (v: boolean) => majReglages({ liens: v });
  const afficherJalons = reglages.jalons;
  const setAfficherJalons = (v: boolean) => majReglages({ jalons: v });
  const couleurCharte = true;
  // Decomposition automatique du planning (11/09).
  const [menuDetail, setMenuDetail] = useState(false);
  const [detailEnCours, setDetailEnCours] = useState(false);
  const [rapportDetail, setRapportDetail] = useState<GanttDetailReport | null>(null);
  const [erreurDetail, setErreurDetail] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<{ niveau: 'taches' | 'sous_taches'; count: number } | null>(null);
  // Voir scrollToFirstBar() : la vue n'est recalee automatiquement qu'une fois, pour ne
  // pas ecraser le defilement que l'utilisateur fait lui-meme ensuite.
  const hasAutoScrolledRef = useRef(false);
  // Charte graphique du tenant appliquee au planning (04/09, demande Charbel : le Gantt
  // doit reprendre les couleurs de la charte comme le font deja les PNG generes).
  const [brandVars, setBrandVars] = useState<Record<string, string>>({});
  const [nameEdits, setNameEdits] = useState<Record<string, string>>({});
  const [learningProposal, setLearningProposal] = useState<{
    section_type: string;
    summary: string;
    suggested_content: string;
    diff_percentage: number;
  } | null>(null);
  const [savingLearning, setSavingLearning] = useState(false);
  const [learningScope, setLearningScope] = useState<'this_ao' | 'similar_aos' | 'all_future'>('similar_aos');
  const containerRef = useRef<HTMLDivElement | null>(null);
  const ganttRef = useRef<any>(null);
  const geometrieRef = useRef<string>('normal');

  // Combien de tâches le filtre laisse voir : l'utilisateur doit savoir qu'il
  // en masque, sinon un planning tronqué passe pour un planning incomplet.
  const niveauMax = reglages.niveau_detail === 'phases' ? 0 : reglages.niveau_detail === 'taches' ? 1 : 99;
  const nbVisibles = tasks.filter((task) => {
    if ((task.level ?? 0) > niveauMax) return false;
    if (filtre === 'critique') return task.is_critical;
    if (filtre === 'jalons') return Boolean(task.is_milestone || (task.milestone_label || '').trim());
    return true;
  }).length || tasks.length;

  /**
   * Dessine les jalons du projet sur le planning (10/09).
   *
   * frappe-gantt ne connaît que des barres : un jalon n'y avait aucune
   * existence graphique, d'où le retour « les jalons ne ressortent pas ».
   * On ajoute donc une couche SVG par-dessus le rendu : un losange plein à la
   * date du jalon (fin de la phase qui le porte), son libellé, et un trait
   * vertical qui le rattache à l'échelle de temps. La couche est entièrement
   * recalculée à chaque rendu et ne modifie jamais le SVG de frappe-gantt.
   */
  const dessinerJalons = useCallback(() => {
    const conteneur = containerRef.current;
    if (!conteneur) return;
    const svg = conteneur.querySelector('svg.gantt') as SVGSVGElement | null;
    if (!svg) return;

    svg.querySelector('.couche-jalons')?.remove();
    if (!afficherJalons) return;

    const parJalon = tasks.filter((t) => t.is_milestone || (t.milestone_label || '').trim());
    if (parJalon.length === 0) return;

    const NS = 'http://www.w3.org/2000/svg';
    const couche = document.createElementNS(NS, 'g');
    couche.setAttribute('class', 'couche-jalons');
    couche.setAttribute('pointer-events', 'none');

    let dessines = 0;
    for (const t of parJalon) {
      const wrapper = svg.querySelector(`.bar-wrapper[data-id="${t.id}"] .bar`) as SVGRectElement | null;
      if (!wrapper) continue;
      const x = parseFloat(wrapper.getAttribute('x') || '0');
      const y = parseFloat(wrapper.getAttribute('y') || '0');
      const w = parseFloat(wrapper.getAttribute('width') || '0');
      const h = parseFloat(wrapper.getAttribute('height') || '0');
      // Un jalon de durée nulle se place sur la barre ; un jalon de fin de
      // phase se place à la date de fin, c'est-à-dire au bord droit.
      const cx = t.is_milestone ? x + w / 2 : x + w;
      const cy = y + h / 2;
      const r = Math.max(7, h / 2 + 1);

      const trait = document.createElementNS(NS, 'line');
      trait.setAttribute('x1', String(cx));
      trait.setAttribute('x2', String(cx));
      trait.setAttribute('y1', String(y - 4));
      trait.setAttribute('y2', String(y + h + 4));
      trait.setAttribute('class', 'jalon-trait');
      couche.appendChild(trait);

      const losange = document.createElementNS(NS, 'path');
      losange.setAttribute('d', `M ${cx} ${cy - r} L ${cx + r} ${cy} L ${cx} ${cy + r} L ${cx - r} ${cy} Z`);
      losange.setAttribute('class', 'jalon-repere');
      couche.appendChild(losange);

      const libelle = (t.milestone_label || t.name || '').trim();
      if (libelle) {
        const texte = document.createElementNS(NS, 'text');
        // SOUS la barre, pas au-dessus : au-dessus, le libellé du premier
        // jalon passait derrière l'en-tête de dates et se retrouvait coupé.
        texte.setAttribute('x', String(cx));
        texte.setAttribute('y', String(y + h + 11));
        texte.setAttribute('class', 'jalon-libelle');
        // Centré en général, mais rabattu vers l'intérieur près des bords :
        // un libellé centré sur le dernier jalon dépassait du planning.
        const largeurTotale = svg.getBoundingClientRect().width || 0;
        const marge = 90;
        const ancrage = cx > largeurTotale - marge ? 'end' : cx < marge ? 'start' : 'middle';
        texte.setAttribute('text-anchor', ancrage);
        texte.textContent = libelle;
        couche.appendChild(texte);
      }
      dessines += 1;
    }

    if (dessines > 0) svg.appendChild(couche);
  }, [tasks, afficherJalons]);

  /**
   * Couleurs et silhouettes du planning hierarchique (11/09). frappe-gantt ne sait
   * dessiner qu'une barre par tache, toutes identiques : on repasse sur son SVG
   * apres chaque rendu pour
   *  - colorer chaque barre selon les reglages (phase / lot / uniforme, palette) ;
   *  - aplatir une phase dont le detail est affiche en barre de synthese fine ;
   *  - affiner les sous-taches.
   * Le SVG de frappe-gantt n'est jamais reconstruit ici, seulement retouche.
   */
  const appliquerStyles = useCallback(() => {
    const svg = containerRef.current?.querySelector('svg.gantt');
    if (!svg) return;
    const couleurs = couleursDesLignes(tasks, reglages, brandColor);
    for (const t of tasks) {
      const wrapper = svg.querySelector(`.bar-wrapper[data-id="${t.id}"]`);
      if (!wrapper) continue;
      const bar = wrapper.querySelector('.bar') as SVGRectElement | null;
      const prog = wrapper.querySelector('.bar-progress') as SVGRectElement | null;
      const label = wrapper.querySelector('.bar-label') as SVGTextElement | null;
      if (!bar) continue;
      const couleur = couleurs[t.id];
      const resume = wrapper.classList.contains('gantt-resume');
      const lvl = t.level ?? 0;
      // Hauteur d'origine memorisee : les retouches ne doivent pas se cumuler.
      const h0 = parseFloat(bar.dataset.h0 || bar.getAttribute('height') || '0');
      const y0 = parseFloat(bar.dataset.y0 || bar.getAttribute('y') || '0');
      bar.dataset.h0 = String(h0);
      bar.dataset.y0 = String(y0);
      let h = h0;
      if (resume) h = Math.max(5, h0 * 0.38);
      else if (lvl >= 2) h = h0 * 0.72;
      const y = y0 + (h0 - h) / 2;
      for (const r of [bar, prog]) {
        if (!r) continue;
        r.setAttribute('height', String(h));
        r.setAttribute('y', String(y));
      }
      const critique = wrapper.classList.contains('gantt-critical');
      if (couleur) {
        bar.style.fill = resume ? teinte(couleur, -0.25) : couleur;
        // Chemin critique : liseré rouge, comme dans le PNG du mémoire -- la couleur
        // de la ligne reste lisible au lieu d'un aplat rouge.
        bar.style.stroke = critique ? '#dc2626' : teinte(couleur, -0.4);
        bar.style.strokeWidth = critique ? '2' : '';
        if (prog) prog.style.fill = teinte(couleur, -0.3);
      }
      if (prog) prog.style.display = resume ? 'none' : '';
      if (label && couleur && !label.classList.contains('big')) {
        label.style.fill = resume ? 'var(--foreground, #0f172a)' : readableOn(couleur);
      }
      if (label && resume) {
        // Libelle de synthese au-dessus de la barre fine, en gras.
        label.style.fontWeight = '700';
        label.setAttribute('y', String(y - 3));
        label.style.fill = 'currentColor';
      }
    }
  }, [tasks, reglages, brandColor]);

  const reload = useCallback(async () => {
    try {
      const res = await api.listGanttTasks(projectId);
      setTasks(res);
      setLoadState('ready');
      // Boucle d'apprentissage par corrections (03/09) : verifie apres chaque
      // mutation si l'ecart au plan initial merite d'etre memorise. Lecture seule et
      // non-bloquant -- un echec ici ne doit jamais casser l'affichage du Gantt.
      try {
        const check = await api.checkGanttLearning(projectId);
        if (check.learning_opportunity && check.learning_proposal) {
          setLearningProposal(check.learning_proposal);
        }
      } catch (checkErr) {
        console.error('Gantt learning check failed', checkErr);
      }
    } catch (err: any) {
      console.error('Failed to load Gantt tasks', err);
      setAuthExpired(err?.status === 401);
      setLoadState('error');
    }
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;
    setLoadState('loading');
    ganttRef.current = null;
    api.listGanttTasks(projectId)
      .then((res) => {
        if (cancelled) return;
        setTasks(res);
        setLoadState('ready');
      })
      .catch((err: any) => {
        console.error('Failed to load Gantt tasks', err);
        if (!cancelled) {
          setAuthExpired(err?.status === 401);
          setLoadState('error');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const persistDateChange = useCallback(async (taskId: string, start: Date, end: Date) => {
    try {
      await api.updateGanttTask(projectId, taskId, { start_date: localIso(start), end_date: localIso(end) });
      await reload();
    } catch (err) {
      console.error('Failed to persist Gantt date change', err);
      await reload(); // resync the chart with the server's authoritative state either way
    }
  }, [projectId, reload]);

  const persistProgressChange = useCallback(async (taskId: string, progress: number) => {
    try {
      await api.updateGanttTask(projectId, taskId, { progress: Math.round(progress) });
      await reload();
    } catch (err) {
      console.error('Failed to persist Gantt progress change', err);
      await reload();
    }
  }, [projectId, reload]);

  /**
   * frappe-gantt ouvre toujours la vue sur la date du jour. Or sur un appel d'offres
   * le chantier demarre presque toujours plus tard (ici : premiere tache au 01/10 alors
   * qu'on est le 04/09) : toutes les barres se retrouvent hors cadre a droite et
   * l'utilisateur voit une grille vide, en croyant que le planning est casse. Constate
   * en direct le 04/09 -- canvas de 4900 px pour une fenetre de 533 px, premiere barre
   * a x=600, scrollLeft a 0. On recale donc la vue sur la premiere tache.
   */
  useEffect(() => {
    let cancelled = false;
    api.getTenant()
      .then((tenant) => {
        if (!cancelled) setBrandVars(buildGanttBrandVars(tenant?.branding_config));
      })
      .catch((err) => {
        // La charte est un confort, jamais une dependance : en cas d'echec on laisse les
        // valeurs par defaut definies dans frappe-gantt-overrides.css.
        console.error('Failed to load tenant branding for Gantt', err);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let annule = false;
    api.getGanttSettings(projectId)
      .then((res) => {
        if (annule) return;
        setReglages({ ...REGLAGES_DEFAUT, ...res.settings });
        setPalettes(res.palettes || {});
        setBrandColor(res.brand_color || null);
        setReglagesModifies(false);
      })
      .catch((err) => console.error('Failed to load Gantt settings', err));
    return () => {
      annule = true;
    };
  }, [projectId]);

  const enregistrerReglages = async (portee: 'projet' | 'entreprise') => {
    setEnregistrement(portee);
    try {
      await api.saveGanttSettings(projectId, reglages, portee);
      setReglagesModifies(false);
      setMessageReglages(t('gantt.export.enregistre'));
    } catch (err: any) {
      setMessageReglages(err?.message || 'Erreur');
    } finally {
      setEnregistrement(null);
    }
  };

  const lancerDetail = async (niveau: 'taches' | 'sous_taches', remplacer = false) => {
    setMenuDetail(false);
    setConfirmation(null);
    setErreurDetail(null);
    setRapportDetail(null);
    setDetailEnCours(true);
    try {
      const rapport = await api.detailGantt(projectId, niveau, remplacer);
      if (rapport.deja_detaille) {
        setConfirmation({ niveau, count: rapport.lignes_existantes || 0 });
        return;
      }
      setRapportDetail(rapport);
      // Le detail vient d'etre cree : on l'affiche en entier.
      if (reglages.niveau_detail !== niveau) majReglages({ niveau_detail: niveau });
      await reload();
    } catch (err: any) {
      setErreurDetail(err?.message || String(err));
    } finally {
      setDetailEnCours(false);
    }
  };

  const ajouterSousLigne = async (parent: GanttTask) => {
    const fin = addDaysIso(parent.start_date, 7) < parent.end_date ? addDaysIso(parent.start_date, 7) : parent.end_date;
    try {
      await api.createGanttTask(projectId, {
        name: t('gantt.ligne.nouvelle'),
        start_date: parent.start_date,
        end_date: fin,
        progress: 0,
        is_milestone: false,
        depends_on: [],
        parent_id: parent.id,
        lot: parent.lot || null,
      });
      await reload();
    } catch (err) {
      console.error('Failed to add Gantt sub-task', err);
    }
  };

  const majLigne = async (task: GanttTask, patch: { lot?: string; color?: string }) => {
    try {
      await api.updateGanttTask(projectId, task.id, patch);
      await reload();
    } catch (err) {
      console.error('Failed to update Gantt line', err);
    }
  };

  const scrollToFirstBar = useCallback(() => {
    const container = containerRef.current?.querySelector('.gantt-container') as HTMLElement | null;
    if (!container) return;
    const xs = Array.from(container.querySelectorAll('.bar-wrapper .bar'))
      .map((b) => parseFloat(b.getAttribute('x') || ''))
      .filter((n) => !Number.isNaN(n));
    if (!xs.length) return;
    const firstX = Math.min(...xs);
    // Deja visible : on ne bouge pas (chantier deja commence, ou vue Month tres large).
    if (firstX < container.clientWidth - 40) return;
    container.scrollLeft = Math.max(0, firstX - 40);
  }, []);

  useEffect(() => {
    if (loadState !== 'ready') return;

    if (tasks.length === 0) {
      // Container isn't rendered in the empty state (see JSX below) -- any prior
      // instance is now bound to a detached node, so drop it. The next time tasks
      // becomes non-empty a fresh instance gets created against the freshly-mounted div.
      ganttRef.current = null;
      return;
    }
    if (!containerRef.current) return;

    // Un chemin critique n'informe que s'il DISTINGUE des taches. Sur un planning
    // enchaine bout a bout (le cas courant d'un phasage BTP), 100 % des taches sont
    // critiques : tout peindre en rouge ne dit plus rien et masque completement la
    // charte graphique du client. Dans ce cas on laisse les barres a la couleur de
    // marque -- l'information "tout est critique" reste portee par le compteur de
    // taches et l'infobulle, pas par un aplat rouge integral.
    const allCritical = tasks.length > 0 && tasks.every((t) => t.is_critical);

    // Même raisonnement pour les jalons, et c'est le défaut signalé le 10/09 :
    // « les jalons ne ressortent pas visuellement ». Sur ce projet, les cinq
    // tâches portent un `milestone_label` (chaque phase se termine par un
    // jalon) : styler les cinq barres comme des jalons ne distingue plus rien.
    // Un jalon est une DATE, pas une phase — on le dessine donc comme un
    // repère à la fin de la barre (voir dessinerJalons), et on ne réserve le
    // style de barre qu'aux vrais jalons de durée nulle.
    const tousPortentUnJalon =
      tasks.length > 1 && tasks.every((t) => t.is_milestone || (t.milestone_label || '').trim());

    const GEOMETRIE = {
      compact: { bar_height: 16, padding: 10 },
      normal:  { bar_height: 22, padding: 18 },
      aere:    { bar_height: 30, padding: 28 },
    }[densite];

    // Le filtre ne supprime jamais de tâche : il restreint l'affichage. On
    // conserve toujours au moins une barre, sinon l'utilisateur croit avoir
    // cassé son planning.
    const visibles = tasks.filter((task) => {
      if ((task.level ?? 0) > niveauMax) return false;
      if (filtre === 'critique') return task.is_critical;
      if (filtre === 'jalons') return Boolean(task.is_milestone || (task.milestone_label || '').trim());
      return true;
    });
    const retenues = visibles.length > 0 ? visibles : tasks;
    const idsRetenus = new Set(retenues.map((t) => t.id));
    // Une phase dont le detail est affiche devient une barre de synthese.
    const avecEnfantsVisibles = new Set(retenues.filter((t) => t.parent_id).map((t) => t.parent_id as string));

    const frappeTasks = retenues.map((task) => {
      const porteUnJalon = Boolean(task.is_milestone || (task.milestone_label || '').trim());
      const classes = [
        task.is_critical && !allCritical && reglages.chemin_critique ? 'gantt-critical' : '',
        `gantt-niveau-${Math.min(task.level ?? 0, 2)}`,
        avecEnfantsVisibles.has(task.id) ? 'gantt-resume' : '',
        porteUnJalon && !tousPortentUnJalon ? 'gantt-milestone' : '',
        couleurCharte ? '' : 'gantt-neutre',
      ].filter(Boolean).join(' ');
      return {
        id: task.id,
        // Le repère losange est désormais dessiné sur le planning ; on garde
        // le libellé du jalon dans le texte de la barre uniquement quand il n'y
        // a pas de repère à dessiner (jalon sans date de fin exploitable).
        name: porteUnJalon && !tousPortentUnJalon
          ? `${task.name}${task.milestone_label ? ' ◆ ' + task.milestone_label : ' ◆'}`
          : task.name,
        start: task.start_date,
        end: task.end_date,
        progress: afficherAvancement ? task.progress : 0,
        // Masquer les liens, c'est ne pas les déclarer à frappe-gantt : les
        // flèches disparaissent sans que la donnée soit perdue. On élague aussi
        // les dépendances vers des tâches filtrées, sinon la flèche pointe dans
        // le vide et le rendu saute.
        dependencies: afficherLiens
          ? task.depends_on.filter((d) => idsRetenus.has(d)).join(',')
          : '',
        custom_class: classes,
      };
    });

    if (ganttRef.current && geometrieRef.current !== densite) {
      containerRef.current.innerHTML = '';
      ganttRef.current = null;
    }
    geometrieRef.current = densite;

    if (!ganttRef.current) {
      ganttRef.current = new Gantt(containerRef.current, frappeTasks, {
        view_mode: viewMode,
        language,
        readonly: false,
        bar_height: GEOMETRIE.bar_height,
        padding: GEOMETRIE.padding,
        move_dependencies: true,
        popup_on: 'click',
        on_date_change: (task: any, start: Date, end: Date) => {
          persistDateChange(task.id, start, end);
        },
        on_progress_change: (task: any, progress: number) => {
          persistProgressChange(task.id, progress);
        },
      });
    } else {
      ganttRef.current.refresh(frappeTasks);
    }
    // Apres le rendu du SVG (d'ou le rAF), une seule fois : cf. scrollToFirstBar.
    // La couche de jalons se pose APRÈS le rendu du SVG par frappe-gantt.
    // frappe-gantt peut redessiner apres le premier frame (refresh -> change_view_mode) :
    // constate le 11/09, les couleurs posees au premier frame etaient effacees apres un
    // changement de niveau de detail. On repasse donc aussi un peu plus tard.
    const retouche = () => { appliquerStyles(); dessinerJalons(); };
    requestAnimationFrame(retouche);
    const minuteurs = [setTimeout(retouche, 80), setTimeout(retouche, 300)];
    if (!hasAutoScrolledRef.current) {
      requestAnimationFrame(() => {
        scrollToFirstBar();
        hasAutoScrolledRef.current = true;
      });
    }
    return () => minuteurs.forEach(clearTimeout);
    // Deliberately excludes persistDateChange/persistProgressChange/viewMode: the
    // handlers are captured once at instantiation and stay valid (they always fetch
    // fresh state via reload() rather than closing over stale `tasks`); viewMode has
    // its own effect below via change_view_mode so it doesn't need to force a rebuild.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks, loadState, filtre, densite, afficherLiens, afficherAvancement, couleurCharte, afficherJalons, dessinerJalons, niveauMax, reglages.chemin_critique, appliquerStyles]);

  useEffect(() => {
    if (ganttRef.current && tasks.length > 0) {
      ganttRef.current.change_view_mode(viewMode);
      requestAnimationFrame(() => { appliquerStyles(); dessinerJalons(); });
      setTimeout(() => { appliquerStyles(); dessinerJalons(); }, 120);
      // Changer d'echelle recalcule toute la geometrie : on repositionne la vue.
      hasAutoScrolledRef.current = false;
      requestAnimationFrame(() => {
        scrollToFirstBar();
        hasAutoScrolledRef.current = true;
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode]);

  const handleAddTask = async () => {
    const last = tasks.length > 0 ? [...tasks].sort((a, b) => a.end_date.localeCompare(b.end_date)).pop() : undefined;
    const start = last ? last.end_date : new Date().toISOString().slice(0, 10);
    try {
      await api.createGanttTask(projectId, {
        name: 'Nouvelle tâche',
        start_date: start,
        end_date: addDaysIso(start, 7),
        progress: 0,
        is_milestone: false,
        depends_on: last ? [last.id] : [],
      });
      await reload();
    } catch (err) {
      console.error('Failed to add Gantt task', err);
    }
  };

  const handleDelete = async (taskId: string) => {
    try {
      await api.deleteGanttTask(projectId, taskId);
      await reload();
    } catch (err) {
      console.error('Failed to delete Gantt task', err);
    }
  };

  const handleRenameCommit = async (task: GanttTask, newName: string) => {
    setNameEdits((prev) => {
      const next = { ...prev };
      delete next[task.id];
      return next;
    });
    const trimmed = newName.trim();
    if (!trimmed || trimmed === task.name) return;
    try {
      await api.updateGanttTask(projectId, task.id, { name: trimmed });
      await reload();
    } catch (err) {
      console.error('Failed to rename Gantt task', err);
    }
  };

  const handleSaveLearning = async () => {
    if (!learningProposal) return;
    setSavingLearning(true);
    try {
      await api.createLearning({
        title: `Ajustement planning — ${projectTitle}`,
        category: 'planning',
        section_type: learningScope === 'all_future' ? undefined : learningProposal.section_type,
        project_id: learningScope === 'this_ao' ? projectId : undefined,
        learned_content: learningProposal.suggested_content,
        learning_insight: learningProposal.summary,
        source_outcome: 'manual_edit',
      });
      setLearningProposal(null);
      setLearningScope('similar_aos');
    } catch (err) {
      console.error('Gantt learning save failed', err);
    } finally {
      setSavingLearning(false);
    }
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      // Le PNG est rendu avec les reglages ENREGISTRES : on enregistre d'abord ceux
      // de l'ecran, sinon l'image ne correspondrait pas a ce que l'utilisateur voit.
      if (reglagesModifies) {
        await api.saveGanttSettings(projectId, reglages, 'projet');
        setReglagesModifies(false);
      }
      const res = await api.generateGantt(projectId, projectTitle, []);
      const criticalCount = (res as any).critical_task_count;
      setExportInfo(
        t('visuals.gantt_interactive.export_weeks', { weeks: res.total_weeks }) +
        (typeof criticalCount === 'number' ? t('visuals.gantt_interactive.export_critical', { count: criticalCount }) : '') +
        t('visuals.gantt_interactive.export_delivery', { date: res.completion_date })
      );
    } catch (err) {
      console.error('Failed to export Gantt', err);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="card-modern p-5 space-y-4 font-sans">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-line">
        <div>
          <h3 className="text-[13px] font-bold text-foreground flex items-center gap-2 font-heading">
            <BarChart3 className="w-4 h-4 text-hl" />
            {t('visuals.gantt_interactive.title')}
          </h3>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            {t('visuals.gantt_interactive.subtitle')}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="tab-group !p-0.5">
            {(['Day', 'Week', 'Month'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setViewMode(m)}
                className={`px-2.5 py-1 text-[11px] font-mono font-medium transition-all duration-200 cursor-pointer rounded-md ${
                  viewMode === m
                    ? 'bg-hl text-hl-contrast font-bold shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {m === 'Day' ? t('visuals.gantt_interactive.view_day') : m === 'Week' ? t('visuals.gantt_interactive.view_week') : t('visuals.gantt_interactive.view_month')}
              </button>
            ))}
          </div>
          <button
            onClick={() => setPanneauOuvert((v) => !v)}
            aria-expanded={panneauOuvert}
            className={`btn-secondary !py-1.5 !px-2.5 !text-[11px] cursor-pointer ${panneauOuvert ? '!border-hl !text-hl' : ''}`}
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            {t('gantt.perso.bouton')}
          </button>
          <div className="relative">
            <button
              onClick={() => setMenuDetail((v) => !v)}
              disabled={detailEnCours || tasks.length === 0}
              aria-expanded={menuDetail}
              className="btn-secondary !py-1.5 !px-2.5 !text-[11px] cursor-pointer !border-hl/40 !text-hl"
            >
              <Wand2 className={`w-3.5 h-3.5 ${detailEnCours ? 'animate-pulse' : ''}`} />
              {t('gantt.detail.bouton')}
            </button>
            {menuDetail && (
              <div className="absolute right-0 z-20 mt-1 w-72 rounded-xl border border-line bg-card shadow-lg p-2 space-y-1">
                <p className="text-[10px] text-muted-foreground px-2 pb-1">{t('gantt.detail.aide')}</p>
                {(['taches', 'sous_taches'] as const).map((n) => (
                  <button
                    key={n}
                    onClick={() => lancerDetail(n)}
                    className="w-full text-left px-2.5 py-2 rounded-lg text-[12px] font-medium hover:bg-sunken cursor-pointer flex items-center gap-2"
                  >
                    <Layers className="w-3.5 h-3.5 text-hl" />
                    {t(n === 'taches' ? 'gantt.detail.bouton_taches' : 'gantt.detail.bouton_sous_taches')}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={handleAddTask}
            className="btn-secondary !py-1.5 !px-2.5 !text-[11px] cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            {t('visuals.gantt_interactive.add_task_btn')}
          </button>
          <button
            onClick={handleExport}
            disabled={isExporting || tasks.length === 0}
            className="btn-primary !py-1.5 !px-2.5 !text-[11px] cursor-pointer"
          >
            <RefreshCw className={`w-3 h-3 ${isExporting ? 'animate-spin' : ''}`} />
            {isExporting ? t('visuals.gantt_interactive.exporting') : t('visuals.gantt_interactive.export_btn')}
          </button>
        </div>
      </div>

      {panneauOuvert && (
        <div className="rounded-xl border border-line bg-sunken/40 p-4 space-y-4">
          <div className="space-y-1.5">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">
              {t('gantt.niveau.titre')}
            </p>
            <div className="tab-group !p-0.5 inline-flex flex-wrap">
              {(['phases', 'taches', 'sous_taches'] as const).map((n) => (
                <button
                  key={n}
                  onClick={() => majReglages({ niveau_detail: n })}
                  aria-pressed={reglages.niveau_detail === n}
                  className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-all cursor-pointer ${
                    reglages.niveau_detail === n ? 'bg-hl text-hl-contrast font-bold' : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {t(`gantt.niveau.${n}`)}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-muted-foreground">
              {t('gantt.niveau.aide')}{' '}
              {t('gantt.ligne.phases_detail', {
                phases: tasks.filter((x) => (x.level ?? 0) === 0).length,
                taches: tasks.filter((x) => (x.level ?? 0) === 1).length,
                sous: tasks.filter((x) => (x.level ?? 0) >= 2).length,
              })}
            </p>
          </div>

          <div className="space-y-2">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">
              {t('gantt.couleurs.titre')}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-muted-foreground">{t('gantt.couleurs.par')}</span>
              <div className="tab-group !p-0.5 inline-flex flex-wrap">
                {(['phase', 'lot', 'uniforme'] as const).map((c) => (
                  <button
                    key={c}
                    onClick={() => majReglages({ couleur_par: c })}
                    aria-pressed={reglages.couleur_par === c}
                    className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-all cursor-pointer ${
                      reglages.couleur_par === c ? 'bg-hl text-hl-contrast font-bold' : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {t(`gantt.couleurs.par_${c}`)}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {[['charte', [] as string[]] as const, ...Object.entries(palettes)].map(([nom, couleurs]) => {
                const actif = nom === 'charte'
                  ? reglages.palette.length === 0
                  : reglages.palette.join(',') === (couleurs as string[]).join(',');
                const apercu = nom === 'charte'
                  ? [brandColor || PALETTE_BTP[0], ...PALETTE_BTP.slice(1, 5)]
                  : (couleurs as string[]).slice(0, 5);
                return (
                  <button
                    key={nom}
                    onClick={() => majReglages({ palette: nom === 'charte' ? [] : [...(couleurs as string[])] })}
                    aria-pressed={actif}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded-lg border text-[11px] cursor-pointer ${
                      actif ? 'border-hl text-hl font-bold' : 'border-line text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <span className="flex">
                      {(apercu as string[]).map((c, i) => (
                        <span key={i} className="w-2.5 h-3.5 first:rounded-l last:rounded-r" style={{ background: c }} />
                      ))}
                    </span>
                    {t(`gantt.couleurs.palette_${nom}`)}
                  </button>
                );
              })}
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-muted-foreground mr-1">{t('gantt.couleurs.palette_perso')}</span>
              {(reglages.palette.length ? reglages.palette : [brandColor || PALETTE_BTP[0], ...PALETTE_BTP.slice(1)]).slice(0, 8).map((c, i, arr) => (
                <label key={i} className="relative w-6 h-6 rounded-md border border-line cursor-pointer overflow-hidden" style={{ background: c }} title={c}>
                  <input
                    type="color"
                    value={HEX_RE.test(c) ? (c.startsWith('#') ? c : `#${c}`) : '#0369a1'}
                    onChange={(e) => {
                      const base = [...arr];
                      base[i] = e.target.value;
                      majReglages({ palette: base });
                    }}
                    className="absolute inset-0 opacity-0 cursor-pointer"
                  />
                </label>
              ))}
            </div>
            <p className="text-[10px] text-muted-foreground">{t('gantt.couleurs.aide')}</p>
          </div>

          <div className="space-y-1.5">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">
              {t('gantt.perso.afficher')}
            </p>
            <div className="tab-group !p-0.5 inline-flex flex-wrap">
              {(['tout', 'critique', 'jalons'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFiltre(f)}
                  aria-pressed={filtre === f}
                  className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-all cursor-pointer ${
                    filtre === f ? 'bg-hl text-hl-contrast font-bold' : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {t(`gantt.perso.filtre_${f}`)}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-muted-foreground">
              {t('gantt.perso.afficher_aide', { visibles: nbVisibles, total: tasks.length })}
            </p>
          </div>

          <div className="space-y-1.5">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">
              {t('gantt.perso.densite')}
            </p>
            <div className="tab-group !p-0.5 inline-flex flex-wrap">
              {(['compact', 'normal', 'aere'] as const).map((d) => (
                <button
                  key={d}
                  onClick={() => setDensite(d)}
                  aria-pressed={densite === d}
                  className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-all cursor-pointer ${
                    densite === d ? 'bg-hl text-hl-contrast font-bold' : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {t(`gantt.perso.densite_${d}`)}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-muted-foreground">{t('gantt.perso.densite_aide')}</p>
          </div>

          <div className="space-y-1.5">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">
              {t('gantt.perso.elements')}
            </p>
            <Bascule
              titre={t('gantt.perso.liens')}
              description={t('gantt.perso.liens_aide')}
              actif={afficherLiens}
              onChange={setAfficherLiens}
              libelleActif={t('gantt.perso.affiche')}
              libelleInactif={t('gantt.perso.masque')}
              dense
            />
            <Bascule
              titre={t('gantt.perso.avancement')}
              description={t('gantt.perso.avancement_aide')}
              actif={afficherAvancement}
              onChange={setAfficherAvancement}
              libelleActif={t('gantt.perso.affiche')}
              libelleInactif={t('gantt.perso.masque')}
              dense
            />
            <Bascule
              titre={t('gantt.perso.jalons')}
              description={t('gantt.perso.jalons_aide')}
              actif={afficherJalons}
              onChange={setAfficherJalons}
              libelleActif={t('gantt.perso.affiche')}
              libelleInactif={t('gantt.perso.masque')}
              dense
            />
            <Bascule
              titre={t('gantt.perso.critique')}
              description={t('gantt.perso.critique_aide')}
              actif={reglages.chemin_critique}
              onChange={(v: boolean) => majReglages({ chemin_critique: v })}
              libelleActif={t('gantt.perso.affiche')}
              libelleInactif={t('gantt.perso.masque')}
              dense
            />
            <Bascule
              titre={t('gantt.perso.durees')}
              description={t('gantt.perso.durees_aide')}
              actif={reglages.durees}
              onChange={(v: boolean) => majReglages({ durees: v })}
              libelleActif={t('gantt.perso.affiche')}
              libelleInactif={t('gantt.perso.masque')}
              dense
            />
          </div>

          <div className="pt-3 border-t border-line space-y-2">
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">
              {t('gantt.export.titre')}
            </p>
            <p className="text-[10px] text-muted-foreground">{t('gantt.export.aide')}</p>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => enregistrerReglages('projet')}
                disabled={enregistrement !== null}
                className="btn-primary !py-1.5 !px-2.5 !text-[11px] cursor-pointer"
              >
                <Save className="w-3 h-3" />
                {t('gantt.export.projet')}
              </button>
              <button
                onClick={() => enregistrerReglages('entreprise')}
                disabled={enregistrement !== null}
                className="btn-secondary !py-1.5 !px-2.5 !text-[11px] cursor-pointer"
              >
                {t('gantt.export.entreprise')}
              </button>
              {reglagesModifies && !messageReglages && (
                <span className="text-[11px] text-warning font-medium">{t('gantt.export.non_enregistre')}</span>
              )}
              {messageReglages && <span className="text-[11px] text-positive font-medium">{messageReglages}</span>}
            </div>
          </div>
        </div>
      )}

      {detailEnCours && (
        <div className="p-3 rounded-xl border border-hl/25 bg-hl/8 text-[12px] text-hl flex items-center gap-2">
          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          {t('gantt.detail.en_cours')}
        </div>
      )}
      {confirmation && (
        <div className="p-3 rounded-xl border border-warning/30 bg-warning/10 text-[12px] space-y-2">
          <p>{t('gantt.detail.confirmer', { count: confirmation.count })}</p>
          <div className="flex gap-2">
            <button onClick={() => lancerDetail(confirmation.niveau, true)} className="btn-primary !py-1 !px-2.5 !text-[11px] cursor-pointer">
              {t('gantt.detail.remplacer')}
            </button>
            <button onClick={() => setConfirmation(null)} className="btn-secondary !py-1 !px-2.5 !text-[11px] cursor-pointer">
              {t('gantt.detail.annuler')}
            </button>
          </div>
        </div>
      )}
      {erreurDetail && (
        <div className="p-3 rounded-xl border border-danger/30 bg-danger/10 text-danger text-[12px] flex items-start gap-2">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span className="flex-1">{t('gantt.detail.erreur', { motif: erreurDetail })}</span>
          <button onClick={() => setErreurDetail(null)} className="cursor-pointer"><X className="w-3.5 h-3.5" /></button>
        </div>
      )}
      {rapportDetail && (
        <div className="p-3 rounded-xl border border-positive/25 bg-positive/8 text-[12px] space-y-1.5">
          <div className="flex items-start gap-2">
            <Sparkles className="w-3.5 h-3.5 mt-0.5 text-positive shrink-0" />
            <div className="flex-1 space-y-1">
              <p className="font-semibold text-positive">
                {t('gantt.detail.resultat', { taches: rapportDetail.taches ?? 0, sous: rapportDetail.sous_taches ?? 0 })}
              </p>
              {rapportDetail.origine && <p className="text-[11px] text-muted-foreground">{rapportDetail.origine}</p>}
              {!!rapportDetail.references_utilisees?.length && (
                <p className="text-[11px] text-muted-foreground">
                  {t('gantt.detail.references', { titres: rapportDetail.references_utilisees.slice(0, 3).join(' · ') + (rapportDetail.references_utilisees.length > 3 ? ' …' : '') })}
                </p>
              )}
              {!!rapportDetail.ajustements?.length && (
                <details className="text-[11px] text-muted-foreground">
                  <summary className="cursor-pointer">{t('gantt.detail.ajustements')} ({rapportDetail.ajustements.length})</summary>
                  <ul className="list-disc pl-4 mt-1 space-y-0.5">
                    {rapportDetail.ajustements.map((a, i) => <li key={i}>{a}</li>)}
                  </ul>
                </details>
              )}
            </div>
            <button onClick={() => setRapportDetail(null)} className="cursor-pointer text-muted-foreground"><X className="w-3.5 h-3.5" /></button>
          </div>
        </div>
      )}

      {learningProposal && (
        <div className="p-3.5 rounded-xl bg-hl/8 border border-hl/20 space-y-2.5 text-xs">
          <div>
            <p className="font-semibold text-hl">{t('editor.tiptap.learning_title', { percent: learningProposal.diff_percentage })}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">{learningProposal.summary || t('editor.tiptap.learning_default_summary')}</p>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] text-muted-foreground font-semibold uppercase tracking-wide mr-1">{t('editor.tiptap.learning_scope_label')}</span>
            {([
              { value: 'this_ao' as const, label: t('editor.tiptap.scope_this_ao') },
              { value: 'similar_aos' as const, label: t('editor.tiptap.scope_similar_aos') },
              { value: 'all_future' as const, label: t('editor.tiptap.scope_all_future') },
            ]).map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setLearningScope(opt.value)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-all cursor-pointer ${
                  learningScope === opt.value
                    ? 'bg-hl border-hl text-white'
                    : 'bg-card border-line text-foreground hover:text-hl'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handleSaveLearning}
              disabled={savingLearning}
              className="px-3 py-1.5 rounded-lg bg-hl hover:bg-hl-strong text-hl-contrast text-[11px] font-semibold disabled:opacity-50 cursor-pointer"
            >
              {savingLearning ? t('editor.tiptap.saving') : t('editor.tiptap.btn_memorize')}
            </button>
            <button
              onClick={() => { setLearningProposal(null); setLearningScope('similar_aos'); }}
              className="px-2 py-1.5 rounded-lg text-muted-foreground hover:text-foreground text-[11px] cursor-pointer"
            >
              {t('editor.tiptap.btn_ignore')}
            </button>
          </div>
        </div>
      )}

      {exportInfo && (
        <div className="p-2.5 rounded-xl bg-positive/8 border border-positive/20 text-positive text-[12px] flex items-center gap-2 font-mono">
          <Sparkles className="w-3.5 h-3.5 shrink-0 text-positive" />
          <span>{t('visuals.gantt_interactive.export_success_prefix')} {exportInfo}</span>
        </div>
      )}

      <div className="relative rounded-xl border border-line overflow-hidden card-inset min-h-[280px]">
        {loadState === 'loading' ? (
          <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground text-xs py-14 font-mono">
            <RefreshCw className="w-5 h-5 animate-spin text-hl" />
            {t('visuals.gantt_interactive.loading')}
          </div>
        ) : loadState === 'error' ? (
          <div className="flex flex-col items-center justify-center gap-2 text-danger text-xs text-center px-6 py-14">
            <AlertTriangle className="w-6 h-6" />
            {t(authExpired ? 'visuals.gantt_interactive.error_title_auth' : 'visuals.gantt_interactive.error_title')}
          </div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground text-xs text-center px-6 py-14">
            <Calendar className="w-7 h-7 opacity-40" />
            <p>{t('visuals.gantt_interactive.empty_title')}</p>
            <button onClick={handleAddTask} className="text-hl font-semibold underline cursor-pointer">
              {t('visuals.gantt_interactive.empty_add_btn')}
            </button>
          </div>
        ) : (
          <div ref={containerRef} className="gantt-target p-2" style={brandVars as React.CSSProperties} />
        )}
      </div>

      {tasks.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] font-mono font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <Flag className="w-3 h-3 text-hl" /> {t('visuals.gantt_interactive.tasks_count', { count: tasks.length })}
          </div>
          <div className="max-h-96 overflow-y-auto space-y-1 pr-1 divide-y divide-transparent">
            {tasks.filter((task) => (task.level ?? 0) <= niveauMax).map((task) => {
              const lvl = task.level ?? 0;
              const couleurLigne = couleursDesLignes(tasks, reglages, brandColor)[task.id];
              return (
              <div
                key={task.id}
                style={{ marginLeft: `${Math.min(lvl, 3) * 18}px` }}
                className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs border transition-colors ${
                  task.is_critical && reglages.chemin_critique
                    ? 'border-danger/25 bg-danger/50 dark:bg-danger/20'
                    : lvl === 0 ? 'border-line bg-sunken/60' : 'border-line bg-card'
                }`}
              >
                {lvl > 0 && <CornerDownRight className="w-3 h-3 text-muted-foreground shrink-0" />}
                <label className="relative w-3.5 h-3.5 rounded-sm shrink-0 cursor-pointer border border-black/10" style={{ background: couleurLigne }} title={t('gantt.ligne.couleur')}>
                  <input
                    type="color"
                    value={couleurLigne && HEX_RE.test(couleurLigne) ? couleurLigne : '#0369a1'}
                    onChange={(e) => majLigne(task, { color: e.target.value })}
                    className="absolute inset-0 opacity-0 cursor-pointer"
                  />
                </label>
                {task.is_critical && (
                  <span className="w-1.5 h-1.5 rounded-full bg-danger shrink-0" title={t('visuals.gantt_interactive.critical_path_title')} />
                )}
                <input
                  value={nameEdits[task.id] ?? task.name}
                  onChange={(e) => setNameEdits((prev) => ({ ...prev, [task.id]: e.target.value }))}
                  onBlur={(e) => handleRenameCommit(task, e.target.value)}
                  className={`flex-1 min-w-0 bg-transparent text-slate-800 dark:text-zinc-200 focus:outline-none focus:ring-1 focus:ring-hl rounded px-1 text-xs ${lvl === 0 ? 'font-bold' : lvl === 1 ? 'font-medium' : ''}`}
                />
                {lvl > 0 && (
                  <input
                    defaultValue={task.lot || ''}
                    placeholder={t('gantt.ligne.lot')}
                    onBlur={(e) => { if ((e.target.value || '') !== (task.lot || '')) majLigne(task, { lot: e.target.value }); }}
                    className="w-28 shrink-0 bg-transparent text-[10px] text-muted-foreground border border-line rounded px-1 py-0.5 focus:outline-none focus:ring-1 focus:ring-hl hidden sm:block"
                  />
                )}
                <span className="text-[10px] font-mono text-muted-foreground shrink-0 tabular-nums">
                  {task.start_date} → {task.end_date}
                </span>
                <span className="text-[10px] font-mono text-muted-foreground shrink-0 tabular-nums w-8 text-right font-semibold">{task.progress}%</span>
                {lvl < 2 && (
                  <button
                    onClick={() => ajouterSousLigne(task)}
                    className="text-muted-foreground hover:text-hl shrink-0 cursor-pointer p-0.5"
                    title={t('gantt.ligne.ajouter_sous')}
                  >
                    <Plus className="w-3 h-3" />
                  </button>
                )}
                {task.color && (
                  <button
                    onClick={() => majLigne(task, { color: '' })}
                    className="text-[9px] text-muted-foreground hover:text-hl shrink-0 cursor-pointer"
                    title={t('gantt.ligne.couleur_reset')}
                  >
                    ↺
                  </button>
                )}
                <button
                  onClick={() => handleDelete(task.id)}
                  className="text-slate-300 dark:text-zinc-600 hover:text-danger dark:hover:text-danger shrink-0 cursor-pointer p-0.5"
                  title={t('visuals.gantt_interactive.delete_task_title')}
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground pt-2 border-t border-line">
        <span>{t('visuals.gantt_interactive.footer_text')}</span>
        <span className="text-hl font-semibold">{t('visuals.section3_badge')}</span>
      </div>
    </div>
  );
}
