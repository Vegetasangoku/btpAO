'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import {
  Sparkles,
  Loader2,
  CheckCircle2,
  Lock,
  AlertTriangle,
} from 'lucide-react';
import { api } from '@/lib/api';
import { TiptapEditor } from '@/components/editor/tiptap-editor';
import { InteractiveGanttChart } from '@/components/visuals/interactive-gantt-chart';
import { SectionDiagnostics } from '@/components/editor/section-diagnostics';
import { MEMO_SECTIONS, AUTO_FILL_KEYS } from '@/lib/sections';
import { MemoOverview } from '@/components/editor/memo-overview';
import { WorkerHealthBanner, useWorkerHealth } from '@/components/editor/worker-health-banner';

import { GeneratedSection, Project } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

const SECTION_KEYS = MEMO_SECTIONS;

export default function EditorPage() {
  const params = useParams();
  const projectId = params.id as string;
  const { t } = useTranslation();
  const [project, setProject] = useState<Project | null>(null);
  const [sections, setSections] = useState<GeneratedSection[]>([]);
  const [activeKey, setActiveKey] = useState(SECTION_KEYS[0].key);
  const [generating, setGenerating] = useState<Set<string>>(new Set());
  const [failedKeys, setFailedKeys] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const autoFillTriggered = useRef(false);
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  // File d'attente de l'auto-remplissage (10/09). Voir le commentaire de l'effet
  // correspondant plus bas : les 9 sections partaient auparavant EN PARALLELE.
  const [autoQueue, setAutoQueue] = useState<string[]>([]);
  const [autoStopped, setAutoStopped] = useState(false);
  // 'section' = navigation pièce par pièce (vue historique)
  // 'apercu'  = le mémoire entier d'un seul tenant, toujours modifiable en place
  const [vue, setVue] = useState<'section' | 'apercu'>('section');
  // On ne lance jamais la rédaction automatique sur un moteur hors service ou
  // périmé : ce serait dépenser les crédits du client pour un résultat qu'on sait
  // d'avance faux. Tant que la sonde n'a pas répondu, on attend.
  const { bloquant: moteurIndisponible, verifie: moteurVerifie } = useWorkerHealth();

  useEffect(() => {
    api.getProject(projectId).then(setProject).catch(() => setProject(null));
    api.getSections(projectId)
      .then((data) => setSections(data))
      .catch(() => setSections([]))
      .finally(() => setLoading(false));
  }, [projectId]);

  function findSection(key: string): GeneratedSection | undefined {
    return sections.find((s) => s.section_key === key);
  }

  async function handleGenerate(sectionKey: string) {
    setGenerating((prev) => new Set(prev).add(sectionKey));
    setFailedKeys((prev) => {
      if (!prev.has(sectionKey)) return prev;
      const next = new Set(prev);
      next.delete(sectionKey);
      return next;
    });
    try {
      // Mode de secours quand le worker de fond est arrêté ou périmé : la rédaction
      // s'exécute dans l'API, avec le code à jour. Sans ça, l'utilisateur cliquerait
      // dans le vide — ou obtiendrait un texte produit par l'ancien code sans le savoir.
      const result = moteurIndisponible
        ? await api.generateSectionSync(projectId, sectionKey)
        : await api.generateSection(projectId, sectionKey);
      setSections((prev) => {
        const existing = prev.findIndex((s) => s.section_key === sectionKey);
        if (existing >= 0) {
          const updated = [...prev];
          updated[existing] = { ...updated[existing], ...result };
          return updated;
        }
        return [...prev, result];
      });
      if (moteurIndisponible) {
        // La réponse synchrone EST le résultat final : rien à attendre du worker.
        setGenerating((prev) => {
          const next = new Set(prev);
          next.delete(sectionKey);
          return next;
        });
      }
    } catch (err) {
      console.error('Generation error:', err);
      setGenerating((prev) => {
        const next = new Set(prev);
        next.delete(sectionKey);
        return next;
      });
      setFailedKeys((prev) => new Set(prev).add(sectionKey));
    }
    // On ne retire PAS la clé de `generating` ici en cas de succès : la génération réelle
    // se termine en tâche de fond (Celery). Le polling ci-dessous détecte la fin
    // (status !== 'processing') et nettoie `generating` à ce moment-là -- ou signale un
    // échec explicite (statut 'failed' ou timeout) au lieu de laisser un état ambigu.
  }

  // Auto-remplissage : au premier chargement, lance la génération IA pour toute section
  // obligatoire encore vide, pour que l'utilisateur arrive sur un mémoire déjà pré-rempli
  // depuis sa base de connaissances au lieu d'un éditeur vide nécessitant un clic manuel
  // section par section.
  useEffect(() => {
    if (loading || autoFillTriggered.current) return;
    if (!moteurVerifie) return;  // on attend le verdict de la sonde avant de dépenser
    autoFillTriggered.current = true;
    const aTraiter = AUTO_FILL_KEYS.filter((key) => {
      const sec = findSection(key);
      const estVide = !sec || !sec.content_html || sec.content_html.trim().length === 0;
      return estVide && sec?.status !== 'processing';
    });
    setAutoQueue(aTraiter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, moteurVerifie, moteurIndisponible]);

  // Consommation de la file UNE SECTION A LA FOIS (10/09).
  //
  // L'ancienne version lançait les 9 sections obligatoires en parallèle dès
  // l'ouverture de l'éditeur. Trois conséquences payées comptant :
  //   - quota fournisseur explosé d'un coup (Gemini palier gratuit : 20 requêtes
  //     par jour, donc 429 dès la première ouverture) ;
  //   - 9 prompts massifs facturés simultanément, sans que personne ne puisse
  //     interrompre la série en voyant le premier résultat ;
  //   - impossible de savoir où on en est : tout tournait en même temps.
  // On enchaîne désormais, et on s'arrête au premier échec plutôt que de brûler
  // huit appels de plus qui échoueront pour la même raison.
  useEffect(() => {
    if (autoStopped || autoQueue.length === 0 || generating.size > 0) return;
    const [suivante, ...reste] = autoQueue;
    setAutoQueue(reste);
    handleGenerate(suivante);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoQueue, generating.size, autoStopped]);

  // Un échec pendant l'enchaînement automatique interrompt la file : la cause est
  // presque toujours commune (quota, clé, worker arrêté) et les sections suivantes
  // échoueraient identiquement, en consommant des tokens pour rien.
  useEffect(() => {
    if (failedKeys.size > 0 && autoQueue.length > 0 && !autoStopped) {
      setAutoStopped(true);
      setAutoQueue([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [failedKeys.size]);

  function reprendreAutoRemplissage() {
    const aTraiter = AUTO_FILL_KEYS.filter((key) => {
      const sec = findSection(key);
      return !sec || !sec.content_html || sec.content_html.trim().length === 0;
    });
    setFailedKeys(new Set());
    setAutoStopped(false);
    setAutoQueue(aTraiter);
  }

  // Polling : tant qu'au moins une section est en génération, on réinterroge le backend
  // toutes les 4s pour récupérer le contenu réel dès que le worker Celery a terminé, au
  // lieu d'exiger un rafraîchissement manuel de la page.
  useEffect(() => {
    const anyPending = generating.size > 0;
    if (!anyPending) {
      if (pollTimer.current) {
        clearInterval(pollTimer.current);
        pollTimer.current = null;
      }
      return;
    }
    if (pollTimer.current) return; // déjà en cours de polling
    let attempts = 0;
    pollTimer.current = setInterval(async () => {
      attempts += 1;
      try {
        const fresh = await api.getSections(projectId);
        setSections(fresh);
        setGenerating((prev) => {
          const next = new Set(prev);
          for (const key of Array.from(next)) {
            const sec = fresh.find((s) => s.section_key === key);
            if (sec && sec.status !== 'processing') {
              next.delete(key);
              if (sec.status === 'failed') {
                setFailedKeys((f) => new Set(f).add(key));
              }
            }
          }
          return next;
        });
      } catch (e) {
        console.error('Polling error:', e);
      }
      if (attempts >= 20 && pollTimer.current) {
        // Sécurité : on arrête après ~80s pour ne pas boucler indéfiniment si le worker
        // Celery ne répond pas (ex. worker non démarré côté serveur). On ne masque plus
        // l'échec : toute clé encore en cours à ce stade est explicitement marquée en échec
        // (icône + message dédiés) au lieu de disparaître silencieusement.
        clearInterval(pollTimer.current);
        pollTimer.current = null;
        setGenerating((prev) => {
          if (prev.size > 0) {
            setFailedKeys((f) => {
              const next = new Set(f);
              prev.forEach((k) => next.add(k));
              return next;
            });
          }
          return new Set();
        });
      }
    }, 4000);
    return () => {
      if (pollTimer.current) {
        clearInterval(pollTimer.current);
        pollTimer.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [generating.size, projectId]);

  function handleSectionSaved(savedSection: GeneratedSection) {
    setSections((prev) => {
      const idx = prev.findIndex((s) => s.id === savedSection.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = savedSection;
        return next;
      }
      return [...prev, savedSection];
    });
  }

  const activeSection = findSection(activeKey);
  const activeMetaSection = SECTION_KEYS.find((s) => s.key === activeKey);
  const isGanttSection = activeKey === 'planning_gantt';
  const isActiveGenerating = generating.has(activeKey);

  const isActiveFailed = failedKeys.has(activeKey) || activeSection?.status === 'failed';
  const isActiveProcessing = activeSection?.status === 'processing';

  const fallbackSection: GeneratedSection = {
    id: `temp-${activeKey}`,
    tenant_id: '11111111-1111-1111-1111-111111111111',
    project_id: projectId,
    section_key: activeKey,
    title: activeMetaSection ? t(activeMetaSection.labelKey) : t('editor.fallback_section_title'),
    order_index: SECTION_KEYS.findIndex((s) => s.key === activeKey),
    // Le statut 'processing' en base ne veut JAMAIS dire "contenu prêt" -- son content_html
    // n'est que le texte-placeholder écrit à l'insertion. On ne l'affiche donc plus jamais
    // tel quel : un message honnête et actionnable remplace systématiquement les états
    // échec / en cours / jamais lancée.
    content_html:
      isActiveFailed
        ? `<p style="color:#A8301A">⚠️ ${t('editor.fallback_failed_html')}</p>`
        : (isActiveGenerating || isActiveProcessing)
          ? `<p>⏳ ${t('editor.fallback_generating_html')}</p>`
          : (activeSection?.content_html || `<p>${t('editor.fallback_empty_html')}</p>`),
    content_json: {},
    visual_placeholders: [],
    // `?? 0` (jamais `|| 85`) : un score réel de 0 doit rester 0, pas être masqué par une
    // fausse valeur par défaut -- c'est exactement le bug "85% alors que tout est vide".
    compliance_score: activeSection?.compliance_score ?? 0,
    status: activeSection?.status || 'missing_data',
    locked_for_export: activeSection?.locked_for_export || false,
    updated_at: new Date().toISOString(),
  };

  const currentSection = activeSection || fallbackSection;

  const basculeVue = (
    <div className="inline-flex rounded-xl border border-line bg-sunken p-0.5 shrink-0">
      {([['section', t('editor.vue_section')], ['apercu', t('editor.vue_apercu')]] as const).map(([v, libelle]) => (
        <button
          key={v}
          onClick={() => setVue(v)}
          className={`px-3 py-1.5 rounded-[10px] text-[11px] font-semibold transition-all cursor-pointer ${
            vue === v ? 'bg-hl/10 text-hl shadow-xs' : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {libelle}
        </button>
      ))}
    </div>
  );

  if (vue === 'apercu') {
    return (
      <div className="h-[calc(100vh-120px)] overflow-y-auto pb-8 space-y-4">
        <WorkerHealthBanner />
        <div className="flex flex-wrap items-center justify-between gap-3">
          {basculeVue}
          {autoQueue.length > 0 && (
            <span className="text-[11px] text-hl flex items-center gap-1.5">
              <Loader2 className="w-3 h-3 animate-spin" />
              {t('editor.file_attente_court', { n: autoQueue.length })}
            </span>
          )}
        </div>
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-hl" />
          </div>
        ) : (
          <MemoOverview
            projectId={projectId}
            projectTitle={project?.title || t('editor.default_project_title')}
            sections={sections}
            generating={generating}
            failedKeys={failedKeys}
            onSectionSaved={handleSectionSaved}
            onRegenerate={handleGenerate}
          />
        )}
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-120px)] gap-4 pb-4">
      {/* Left Panel: Section Navigator */}
      <div className="w-64 shrink-0 overflow-y-auto card-modern p-3 space-y-1">
        <p className="text-[10px] font-bold uppercase text-muted-foreground px-2 pb-2 tracking-widest">{t('editor.sections_title')}</p>
        {SECTION_KEYS.map((meta) => {
          const sec = findSection(meta.key);
          const isActive = activeKey === meta.key;
          const isDone = meta.key === 'planning_gantt'
            ? true
            : (sec?.status === 'generated' || sec?.status === 'edited' || sec?.status === 'validated' || sec?.status === 'restored') && Boolean(sec?.content_html);
          const hasFailed = failedKeys.has(meta.key) || sec?.status === 'failed';
          const isKeyGenerating = generating.has(meta.key);
          const score = sec?.compliance_score;
          const isLocked = sec?.locked_for_export;
          // Un canevas de secours n'est pas une rédaction : il ne doit jamais
          // s'afficher comme une section terminée avec un score. Le moteur pose
          // un bandeau reconnaissable en tête du corps ; on s'y raccroche plutôt
          // que de deviner à partir du score.
          const estCanevas = (sec?.content_html || '').includes('Canevas de secours');

          return (
            <button
              key={meta.key}
              onClick={() => setActiveKey(meta.key)}
              className={`w-full text-left px-3 py-2.5 rounded-xl flex items-start gap-2.5 transition-all cursor-pointer group ${
                isActive
                  ? 'bg-hl/10 border border-hl/40 text-hl font-semibold shadow-xs'
                  : 'hover:bg-slate-100/70 dark:hover:bg-raised text-muted-foreground hover:text-foreground'
              }`}
            >
              <div className="mt-0.5 shrink-0">
                {isKeyGenerating
                  ? <Loader2 className="w-3.5 h-3.5 text-hl animate-spin" />
                  : hasFailed || estCanevas
                    ? <AlertTriangle className="w-3.5 h-3.5 text-danger" />
                    : isLocked
                      ? <Lock className="w-3.5 h-3.5 text-positive" />
                      : isDone
                        ? <CheckCircle2 className="w-3.5 h-3.5 text-positive" />
                        : <div className="w-3.5 h-3.5 rounded-full border border-slate-300 dark:border-line border-dashed" />
                }
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-semibold leading-tight line-clamp-2">{t(meta.labelKey)}</p>
                {meta.key === 'planning_gantt' ? (
                  <p className="text-[10px] font-mono mt-0.5 text-hl">{t('editor.studio_visuals')}</p>
                ) : hasFailed ? (
                  <p className="text-[10px] font-mono mt-0.5 text-danger">{t('editor.generation_failed')}</p>
                ) : estCanevas ? (
                  <p className="text-[10px] font-mono mt-0.5 text-danger">{t('editor.canevas_a_regenerer')}</p>
                ) : isKeyGenerating ? (
                  <p className="text-[10px] font-mono mt-0.5 text-hl">{t('editor.generating')}</p>
                ) : isDone && score !== undefined ? (
                  <p
                    title={t('editor.score_rc_infobulle')}
                    className={`text-[10px] font-mono mt-0.5 ${score >= 90 ? 'text-positive' : score >= 70 ? 'text-hl' : 'text-danger'}`}
                  >
                    {t('editor.score_rc', { score })}
                  </p>
                ) : (
                  <p className="text-[10px] font-mono mt-0.5 text-muted-foreground">{t('editor.not_generated')}</p>
                )}
              </div>
              {!meta.mandatory && (
                <span className="text-[9px] font-semibold text-muted-foreground bg-sunken px-1.5 py-0.5 rounded shrink-0">{t('editor.optional_tag')}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Right Panel: Editor */}
      <div className="flex-1 overflow-y-auto space-y-4">
        {/* Section Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl card-modern">
          <div>
            <h2 className="text-[14px] font-bold text-foreground font-heading">{activeMetaSection ? t(activeMetaSection.labelKey) : ''}</h2>
            {!activeMetaSection?.mandatory && (
              <p className="text-[11px] text-muted-foreground">{t('editor.optional_note')}</p>
            )}
            {isGanttSection && (
              <p className="text-[11px] text-muted-foreground">{t('editor.gantt_note')}</p>
            )}
          </div>

          <div className="flex items-center gap-2">
            {basculeVue}
            {!isGanttSection && (
              <button
                onClick={() => handleGenerate(activeKey)}
                disabled={isActiveGenerating}
                className="btn-primary !py-1.5 !px-3 !text-[12px]"
              >
                {isActiveGenerating
                  ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('editor.generating_ai')}</>
                  : <><Sparkles className="w-3.5 h-3.5" /> {t('editor.btn_generate_ai')}</>
                }
              </button>
            )}
          </div>
        </div>

        <WorkerHealthBanner />

        {/* File d'auto-remplissage : l'utilisateur voit où en est l'enchaînement,
            et surtout ce qu'il reste à consommer comme appels payants. */}
        {autoQueue.length > 0 && (
          <div className="p-3 rounded-xl border border-hl/20 bg-hl/8 text-[12px] text-hl flex items-center gap-2.5">
            <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
            <span>{t('editor.file_attente', { n: autoQueue.length })}</span>
          </div>
        )}
        {autoStopped && (
          <div className="p-3 rounded-xl border border-danger/20 bg-danger/8 text-[12px] text-danger flex flex-wrap items-center gap-2.5">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span className="flex-1 min-w-[240px]">{t('editor.file_interrompue')}</span>
            <button onClick={reprendreAutoRemplissage} className="btn-primary !py-1 !px-2.5 !text-[11px]">
              {t('editor.reprendre')}
            </button>
          </div>
        )}

        {/* Editor Area */}
        {loading ? (
          <div className="flex items-center justify-center py-20 text-[13px] text-muted-foreground font-mono">
            <Loader2 className="w-8 h-8 animate-spin text-hl" />
          </div>
        ) : isGanttSection ? (
          <InteractiveGanttChart projectId={projectId} projectTitle={project?.title || t('editor.default_project_title')} />
        ) : (
          <div className="card-modern overflow-hidden">
            <TiptapEditor
              key={activeKey}
              projectId={projectId}
              section={currentSection}
              onSave={handleSectionSaved}
              onRegenerate={() => handleGenerate(activeKey)}
            />
          </div>
        )}

        {/* Compliance Badge */}
        {!isGanttSection && (
          isActiveFailed ? (
            <div className="p-4 rounded-xl border text-[13px] font-semibold flex items-center gap-2.5 bg-danger/8 border-danger/20 text-danger">
              <AlertTriangle className="w-4 h-4" />
              {t('editor.badge_failed')}
            </div>
          ) : (isActiveGenerating || isActiveProcessing) ? (
            <div className="p-4 rounded-xl border text-[13px] font-semibold flex items-center gap-2.5 bg-hl/8 border-hl/20 text-hl">
              <Loader2 className="w-4 h-4 animate-spin" />
              {t('editor.badge_generating')}
            </div>
          ) : (currentSection?.status === 'generated' || currentSection?.status === 'edited' || currentSection?.status === 'validated' || currentSection?.status === 'restored') ? (
            <div className={`p-4 rounded-xl border text-[13px] font-semibold flex items-center gap-2.5 ${
              (currentSection.compliance_score ?? 0) >= 90
                ? 'bg-positive/8 border-positive/20 text-positive'
                : (currentSection.compliance_score ?? 0) >= 70
                  ? 'bg-hl/8 border-hl/20 text-hl'
                  : 'bg-danger/8 border-danger/20 text-danger'
            }`}>
              {(currentSection.compliance_score ?? 0) >= 90
                ? <CheckCircle2 className="w-4 h-4 text-positive" />
                : <AlertTriangle className="w-4 h-4 text-hl" />
              }
              {t('editor.badge_score_prefix')}<span className="font-mono text-base font-bold">{currentSection.compliance_score ?? 0}%</span>
              {(currentSection.compliance_score ?? 0) < 80 && t('editor.badge_score_warning')}
            </div>
          ) : (
            <div className="p-4 rounded-xl card-inset text-[13px] text-muted-foreground flex items-center gap-2">
              {t('editor.badge_not_generated')}
            </div>
          )
        )}

        {!isGanttSection && <SectionDiagnostics placeholders={activeSection?.visual_placeholders} />}
      </div>

    </div>
  );
}
