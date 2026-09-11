'use client';

/**
 * Lexique des acronymes du BTP et de la commande publique.
 *
 * Constat du 10/09 : l'interface affichait « 50% RC » à des clients qui ne
 * savent pas ce qu'est un « RC ». Un sigle métier n'est jamais évident pour
 * celui qui découvre l'outil : soit on écrit le terme en toutes lettres,
 * soit on l'accompagne de sa définition. Ce composant centralise les deux
 * pour que la règle s'applique partout de la même façon.
 */

import { useTranslation } from '@/components/i18n-provider';

type Langue = 'fr' | 'en' | 'ar';

interface Entree {
  /** Le terme développé, court, tel qu'on l'écrirait dans une phrase. */
  libelle: Record<Langue, string>;
  /** Ce que ça veut dire concrètement pour l'utilisateur. */
  definition: Record<Langue, string>;
}

export const LEXIQUE: Record<string, Entree> = {
  RC: {
    libelle: {
      fr: 'règlement de consultation',
      en: 'tender rules',
      ar: 'نظام الاستشارة',
    },
    definition: {
      fr: "Le règlement de consultation est la pièce du marché qui fixe les règles du jeu : ce que l'acheteur attend, les critères sur lesquels il note les offres et le poids de chacun.",
      en: 'The tender rules document sets the rules of the game: what the buyer expects, the criteria used to score bids, and the weight of each.',
      ar: 'نظام الاستشارة هو الوثيقة التي تحدد قواعد المنافسة: ما يتوقعه المشتري، ومعايير تقييم العروض، ووزن كل معيار.',
    },
  },
  CCTP: {
    libelle: {
      fr: 'cahier des clauses techniques particulières',
      en: 'technical specifications',
      ar: 'دفتر الشروط الفنية',
    },
    definition: {
      fr: "Le cahier des clauses techniques particulières décrit précisément les ouvrages à réaliser : matériaux, performances, contraintes de mise en œuvre.",
      en: 'The technical specifications describe precisely what must be built: materials, performance levels, and construction constraints.',
      ar: 'دفتر الشروط الفنية يصف بدقة الأعمال المطلوب تنفيذها: المواد والأداء وقيود التنفيذ.',
    },
  },
  CCAP: {
    libelle: {
      fr: 'cahier des clauses administratives particulières',
      en: 'administrative clauses',
      ar: 'دفتر الشروط الإدارية',
    },
    definition: {
      fr: "Le cahier des clauses administratives particulières fixe les règles contractuelles : délais, pénalités, modalités de paiement, garanties.",
      en: 'The administrative clauses set the contractual rules: deadlines, penalties, payment terms and guarantees.',
      ar: 'دفتر الشروط الإدارية يحدد القواعد التعاقدية: المهل والغرامات وشروط الدفع والضمانات.',
    },
  },
  DPGF: {
    libelle: {
      fr: 'décomposition du prix global et forfaitaire',
      en: 'pricing breakdown',
      ar: 'جدول تفصيل الأسعار',
    },
    definition: {
      fr: "La décomposition du prix global et forfaitaire détaille, poste par poste, comment se construit le prix que vous proposez.",
      en: 'The pricing breakdown details, line by line, how the price you offer is built up.',
      ar: 'جدول تفصيل الأسعار يبيّن، بنداً ببند، كيفية تكوين السعر المقترح.',
    },
  },
  BPU: {
    libelle: {
      fr: 'bordereau des prix unitaires',
      en: 'schedule of unit rates',
      ar: 'جدول الأسعار الإفرادية',
    },
    definition: {
      fr: "Le bordereau des prix unitaires liste le prix de chaque prestation prise isolément (le mètre cube de béton, le mètre linéaire de réseau…).",
      en: 'The schedule of unit rates lists the price of each item taken separately (a cubic metre of concrete, a linear metre of pipework…).',
      ar: 'جدول الأسعار الإفرادية يسرد سعر كل بند على حدة (متر مكعب من الخرسانة، متر طولي من الشبكة…).',
    },
  },
  DCE: {
    libelle: {
      fr: 'dossier de consultation des entreprises',
      en: 'tender file',
      ar: 'ملف المناقصة',
    },
    definition: {
      fr: "Le dossier de consultation des entreprises est l'ensemble des pièces remises par l'acheteur pour préparer votre offre.",
      en: 'The tender file is the complete set of documents the buyer provides so you can prepare your bid.',
      ar: 'ملف المناقصة هو مجموعة الوثائق التي يقدمها المشتري لإعداد عرضك.',
    },
  },
  PPSPS: {
    libelle: {
      fr: 'plan particulier de sécurité et de protection de la santé',
      en: 'site health & safety plan',
      ar: 'خطة السلامة والصحة الخاصة بالموقع',
    },
    definition: {
      fr: "Le plan particulier de sécurité et de protection de la santé décrit les risques de votre chantier et les mesures que vous prenez pour les maîtriser.",
      en: 'The site health & safety plan describes the risks of your site and the measures you take to control them.',
      ar: 'خطة السلامة والصحة تصف مخاطر ورشتك والتدابير المتخذة للسيطرة عليها.',
    },
  },
  RSE: {
    libelle: {
      fr: 'responsabilité sociétale des entreprises',
      en: 'corporate social responsibility',
      ar: 'المسؤولية المجتمعية للشركات',
    },
    definition: {
      fr: "La responsabilité sociétale des entreprises couvre vos engagements environnementaux et sociaux : déchets, carbone, insertion, conditions de travail.",
      en: 'Corporate social responsibility covers your environmental and social commitments: waste, carbon, inclusion, working conditions.',
      ar: 'المسؤولية المجتمعية تشمل التزاماتك البيئية والاجتماعية: النفايات والكربون والإدماج وظروف العمل.',
    },
  },
  QSE: {
    libelle: {
      fr: 'qualité, sécurité, environnement',
      en: 'quality, safety, environment',
      ar: 'الجودة والسلامة والبيئة',
    },
    definition: {
      fr: "Qualité, sécurité, environnement : les trois volets sur lesquels l'acheteur vérifie votre organisation de chantier.",
      en: 'Quality, safety, environment: the three areas on which the buyer checks how you run a site.',
      ar: 'الجودة والسلامة والبيئة: المحاور الثلاثة التي يتحقق منها المشتري في تنظيم ورشتك.',
    },
  },
  OCR: {
    libelle: {
      fr: 'reconnaissance de texte',
      en: 'text recognition',
      ar: 'التعرّف الضوئي على الحروف',
    },
    definition: {
      fr: "La reconnaissance de texte relit les documents scannés pour en extraire le texte, même quand le PDF n'est qu'une image.",
      en: 'Text recognition reads scanned documents to extract their text, even when the PDF is only an image.',
      ar: 'التعرّف الضوئي يقرأ المستندات الممسوحة لاستخراج نصها حتى لو كان الملف صورة فقط.',
    },
  },
};

export function libelleAcronyme(sigle: string, langue: string): string {
  const entree = LEXIQUE[sigle.toUpperCase()];
  if (!entree) return sigle;
  return entree.libelle[(langue as Langue)] ?? entree.libelle.fr;
}

export function definitionAcronyme(sigle: string, langue: string): string {
  const entree = LEXIQUE[sigle.toUpperCase()];
  if (!entree) return '';
  return entree.definition[(langue as Langue)] ?? entree.definition.fr;
}

interface AcronymeProps {
  sigle: string;
  /**
   * 'developpe'  : on écrit le terme en toutes lettres (par défaut, le plus clair).
   * 'sigle'      : on garde le sigle, souligné, avec sa définition en infobulle.
   *                À réserver aux endroits où la place manque vraiment.
   */
  forme?: 'developpe' | 'sigle';
  className?: string;
}

/**
 * Affiche un terme métier de façon compréhensible par un non-initié.
 * Dans les deux formes, la définition complète reste accessible au survol
 * et aux lecteurs d'écran.
 */
export function Acronyme({ sigle, forme = 'developpe', className = '' }: AcronymeProps) {
  const { language } = useTranslation();
  const cle = sigle.toUpperCase();
  const entree = LEXIQUE[cle];

  if (!entree) return <span className={className}>{sigle}</span>;

  const definition = definitionAcronyme(cle, language);
  const texte = forme === 'sigle' ? cle : libelleAcronyme(cle, language);

  return (
    <abbr
      title={definition}
      aria-label={`${libelleAcronyme(cle, language)} — ${definition}`}
      className={`no-underline decoration-dotted underline-offset-2 [text-decoration:underline] cursor-help ${className}`}
    >
      {texte}
    </abbr>
  );
}

/**
 * Rend un texte quelconque — y compris produit par le moteur de rédaction —
 * en soulignant chaque sigle connu et en lui attachant sa définition.
 *
 * Le moteur écrit « un critère RC précis » ou « le CCTP intégral, les plans,
 * la DPGF » : on ne peut pas lui interdire les sigles du métier, mais on peut
 * garantir qu'aucun ne reste opaque pour le lecteur. Le texte n'est pas
 * réécrit, seulement annoté.
 */
export function TexteAvecAcronymes({ texte, className = '' }: { texte: string; className?: string }) {
  if (!texte) return null;

  const sigles = Object.keys(LEXIQUE).sort((a, b) => b.length - a.length);
  // Frontières de mot explicites : « RC » ne doit pas matcher dans « MARCHE ».
  const motif = new RegExp(`(?<![A-Za-zÀ-ÿ0-9])(${sigles.join('|')})(?![A-Za-zÀ-ÿ0-9])`, 'g');

  const morceaux: React.ReactNode[] = [];
  let dernier = 0;
  let m: RegExpExecArray | null;
  let i = 0;

  while ((m = motif.exec(texte)) !== null) {
    if (m.index > dernier) morceaux.push(texte.slice(dernier, m.index));
    morceaux.push(<Acronyme key={`a${i++}`} sigle={m[1]} forme="sigle" />);
    dernier = m.index + m[1].length;
  }
  if (dernier < texte.length) morceaux.push(texte.slice(dernier));

  return <span className={className}>{morceaux}</span>;
}
