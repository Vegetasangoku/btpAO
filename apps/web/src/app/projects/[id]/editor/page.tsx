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

import { GeneratedSection, Project } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

const SECTION_KEYS: { key: string; labelKey: string; mandatory: boolean }[] = [
  { key: 'presentation_entreprise',   labelKey: 'editor.section.presentation_entreprise',   mandatory: true },
  { key: 'references_similaires',     labelKey: 'editor.section.references_similaires',     mandatory: true },
  { key: 'moyens_humains',            labelKey: 'editor.section.moyens_humains',            mandatory: true },
  { key: 'moyens_materiels',          labelKey: 'editor.section.moyens_materiels',          mandatory: true },
  { key: 'methodologie_phasage',      labelKey: 'editor.section.methodologie_phasage',      mandatory: true },
  { key: 'qualite_controle',          labelKey: 'editor.section.qualite_controle',          mandatory: true },
  { key: 'securite_ppsps',            labelKey: 'editor.section.securite_ppsps',            mandatory: true },
  { key: 'rse_environnement',         labelKey: 'editor.section.rse_environnement',         mandatory: false },
  { key: 'sous_traitance',            labelKey: 'editor.section.sous_traitance',            mandatory: false },
  { key: 'planning_gantt',            labelKey: 'editor.section.planning_gantt',            mandatory: true },
];

// Sections texte auto-remplies au chargement depuis le corpus RAG. Le Gantt (planning_gantt)
// n'est pas une section texte : c'est un visuel (PNG) rendu par GanttPreview ci-dessous.
const AUTO_FILL_KEYS = SECTION_KEYS.filter((s) => s.mandatory && s.key !== 'planning_gantt').map((s) => s.key);

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
      const result = await api.generateSection(projectId, sectionKey);
      setSections((prev) => {
        const existing = prev.findIndex((s) => s.section_key === sectionKey);
        if (existing >= 0) {
          const updated = [...prev];
          updated[existing] = { ...updated[existing], ...result };
          return updated;
        }
        return [...prev, result];
      });
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
    autoFillTriggered.current = true;
    for (const key of AUTO_FILL_KEYS) {
      const sec = findSection(key);
      const isEmpty = !sec || !sec.content_html || sec.content_html.trim().length === 0;
      if (isEmpty && sec?.status !== 'processing') {
        handleGenerate(key);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

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
                  : hasFailed
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
                ) : isKeyGenerating ? (
                  <p className="text-[10px] font-mono mt-0.5 text-hl">{t('editor.generating')}</p>
                ) : isDone && score !== undefined ? (
                  <p className={`text-[10px] font-mono mt-0.5 ${score >= 90 ? 'text-positive' : score >= 70 ? 'text-hl' : 'text-danger'}`}>
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
      </div>

    </div>
  );
}
