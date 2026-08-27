#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Full-file replace of apps/web/src/app/projects/[id]/editor/page.tsx.

Uses the ENTIRE original file (as last read) as the match anchor via the same
exact-match-count-of-1 apply_patch() helper used everywhere else this session —
this doubles as a concurrent-edit safety check: if the other AI (or anyone else)
touched this file since it was last read, the whole-file string won't match
exactly and the script aborts with ZERO writes instead of silently clobbering
whatever the file currently contains.

What changes and why (see patch_ux_fixes_batch1.py's docstring for the full
investigation — this is the companion patch for the same 3 bug reports):
  - Section 10 "Planning Gantt Previsionnel" now renders the real, working
    GanttPreview component (Python/Matplotlib chart) instead of being routed
    through the generic AI-TEXT section-generation path, which could never
    produce a planning (wrong pipeline entirely).
  - Empty MANDATORY text sections now auto-generate on page load instead of
    requiring a manual click per section, using the exact same
    api.generateSection() call the manual button already used (no backend
    change needed — that path already does real RAG + honest missing-data
    banners per llm_generator.py).
  - Generation results are now polled for (every 4s, up to ~80s) so content
    actually appears once the background Celery worker finishes, instead of
    requiring a manual page refresh to see the result of a generation that
    already completed server-side.
  - The existing DCEChatSidebar + real RAG-with-citations /ask endpoint
    (already built, already working, just never mounted here) is now reachable
    from a visible "Assistant Q&A" button.
"""
import sys

def apply_patch(path, replacements):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for label, old, new in replacements:
        count = content.count(old)
        if count != 1:
            print(f"ABORT [{path}] block '{label}': found {count} occurrences (expected 1). No changes written.")
            print("This usually means the file was modified since it was last read (possibly by the other AI). Re-read and regenerate the patch.")
            sys.exit(1)
        content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"OK: {path} patched ({len(replacements)} block(s)).")


if len(sys.argv) != 2:
    print("Usage: patch_editor_page_rewrite.py <repo_root>")
    sys.exit(1)

REPO_ROOT = sys.argv[1].rstrip("/")
EDITOR_PAGE = f"{REPO_ROOT}/apps/web/src/app/projects/[id]/editor/page.tsx"

ORIGINAL = """'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import {
  Sparkles,
  Loader2,
  CheckCircle2,
  Lock,
  Unlock,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
} from 'lucide-react';
import { api } from '@/lib/api';
import { TiptapEditor } from '@/components/editor/tiptap-editor';

import { GeneratedSection } from '@/lib/types';

const SECTION_KEYS: { key: string; label: string; mandatory: boolean }[] = [
  { key: 'presentation_entreprise',   label: "1. Présentation de l'Entreprise",                   mandatory: true },
  { key: 'references_similaires',     label: '2. Références de Travaux Similaires',                mandatory: true },
  { key: 'moyens_humains',            label: '3. Moyens Humains & Encadrement',                    mandatory: true },
  { key: 'moyens_materiels',          label: '4. Moyens Matériels & Engins',                       mandatory: true },
  { key: 'methodologie_phasage',      label: '5. Méthodologie & Planning Prévisionnel',            mandatory: true },
  { key: 'qualite_controle',          label: '6. Démarche Qualité & Autocontrôle',                 mandatory: true },
  { key: 'securite_ppsps',            label: '7. Sécurité, Prévention & PPSPS',                   mandatory: true },
  { key: 'rse_environnement',         label: '8. RSE, Déchets BTP & Bilan Carbone',               mandatory: false },
  { key: 'sous_traitance',            label: '9. Politique de Sous-Traitance',                     mandatory: false },
  { key: 'planning_gantt',            label: '10. Planning Gantt Prévisionnel',                    mandatory: true },
];

export default function EditorPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [sections, setSections] = useState<GeneratedSection[]>([]);
  const [activeKey, setActiveKey] = useState(SECTION_KEYS[0].key);
  const [generating, setGenerating] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSections(projectId)
      .then((data) => setSections(data))
      .catch(() => setSections([]))
      .finally(() => setLoading(false));
  }, [projectId]);

  function findSection(key: string): GeneratedSection | undefined {
    return sections.find((s) => s.section_key === key);
  }

  async function handleGenerate(sectionKey: string) {
    setGenerating(sectionKey);
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
    } finally {
      setGenerating(null);
    }
  }

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

  const fallbackSection: GeneratedSection = {
    id: `temp-${activeKey}`,
    tenant_id: '11111111-1111-1111-1111-111111111111',
    project_id: projectId,
    section_key: activeKey,
    title: activeMetaSection?.label || 'Section',
    order_index: SECTION_KEYS.findIndex((s) => s.key === activeKey),
    content_html: activeSection?.content_html || '<p>Cliquez sur "Générer avec l\\'IA" ou commencez à rédiger...</p>',
    content_json: {},
    visual_placeholders: [],
    compliance_score: activeSection?.compliance_score || 85,
    status: activeSection?.status || 'generating',
    locked_for_export: activeSection?.locked_for_export || false,
    updated_at: new Date().toISOString(),
  };

  const currentSection = activeSection || fallbackSection;

  return (
    <div className="flex h-[calc(100vh-120px)] gap-4 pb-4">
      {/* Left Panel: Section Navigator */}
      <div className="w-64 shrink-0 overflow-y-auto rounded-2xl bg-slate-900/80 border border-slate-800 p-3 space-y-1">
        <p className="text-[10px] font-bold uppercase text-slate-500 px-2 pb-2 tracking-widest">Sections du Mémoire</p>
        {SECTION_KEYS.map((meta) => {
          const sec = findSection(meta.key);
          const isActive = activeKey === meta.key;
          const hasContent = Boolean(sec?.content_html);
          const score = sec?.compliance_score;
          const isLocked = sec?.locked_for_export;

          return (
            <button
              key={meta.key}
              onClick={() => setActiveKey(meta.key)}
              className={`w-full text-left px-3 py-2.5 rounded-xl flex items-start gap-2.5 transition-all group ${
                isActive
                  ? 'bg-sky-600/20 border border-sky-500/40 text-sky-300'
                  : 'hover:bg-slate-800/60 text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="mt-0.5 shrink-0">
                {isLocked
                  ? <Lock className="w-3.5 h-3.5 text-emerald-400" />
                  : hasContent
                    ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    : <div className="w-3.5 h-3.5 rounded-full border border-slate-600 border-dashed" />
                }
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-semibold leading-tight line-clamp-2">{meta.label}</p>
                {score !== undefined && (
                  <p className={`text-[10px] font-mono mt-0.5 ${score >= 90 ? 'text-emerald-400' : score >= 70 ? 'text-amber-400' : 'text-rose-400'}`}>
                    Score RC : {score}%
                  </p>
                )}
              </div>
              {!meta.mandatory && (
                <span className="text-[9px] font-semibold text-slate-600 bg-slate-800 px-1 py-0.5 rounded shrink-0">opt.</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Right Panel: Editor */}
      <div className="flex-1 overflow-y-auto space-y-4">
        {/* Section Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-2xl bg-slate-900/80 border border-slate-800">
          <div>
            <h2 className="text-sm font-bold text-white">{activeMetaSection?.label}</h2>
            {!activeMetaSection?.mandatory && (
              <p className="text-[11px] text-slate-500">Section optionnelle — peut être omise si non requise par le RC</p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleGenerate(activeKey)}
              disabled={generating === activeKey}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-sky-600/20 border border-sky-500/30 text-sky-300 text-xs font-semibold hover:bg-sky-600/30 transition-all disabled:opacity-60"
            >
              {generating === activeKey
                ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Génération IA…</>
                : <><Sparkles className="w-3.5 h-3.5" /> Générer avec l'IA</>
              }
            </button>
          </div>
        </div>

        {/* Editor Area */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
          </div>
        ) : (
          <div className="rounded-2xl overflow-hidden border border-slate-800 bg-slate-950/40">
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
        {currentSection?.compliance_score !== undefined && (
          <div className={`p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 ${
            currentSection.compliance_score >= 90
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : currentSection.compliance_score >= 70
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
          }`}>
            {currentSection.compliance_score >= 90
              ? <CheckCircle2 className="w-4 h-4" />
              : <AlertTriangle className="w-4 h-4" />
            }
            Score de conformité RC : <span className="font-mono text-lg">{currentSection.compliance_score}%</span>
            {currentSection.compliance_score < 80 && ' — Des critères RC manquent dans cette section. Régénérez ou complétez manuellement.'}
          </div>
        )}
      </div>
    </div>
  );
}
"""

NEW = """'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import {
  Sparkles,
  Loader2,
  CheckCircle2,
  Lock,
  AlertTriangle,
  MessageSquare,
} from 'lucide-react';
import { api } from '@/lib/api';
import { TiptapEditor } from '@/components/editor/tiptap-editor';
import { GanttPreview } from '@/components/visuals/gantt-preview';
import { DCEChatSidebar } from '@/components/chat/dce-chat-sidebar';

import { GeneratedSection, Project } from '@/lib/types';

const SECTION_KEYS: { key: string; label: string; mandatory: boolean }[] = [
  { key: 'presentation_entreprise',   label: "1. Présentation de l'Entreprise",                   mandatory: true },
  { key: 'references_similaires',     label: '2. Références de Travaux Similaires',                mandatory: true },
  { key: 'moyens_humains',            label: '3. Moyens Humains & Encadrement',                    mandatory: true },
  { key: 'moyens_materiels',          label: '4. Moyens Matériels & Engins',                       mandatory: true },
  { key: 'methodologie_phasage',      label: '5. Méthodologie & Planning Prévisionnel',            mandatory: true },
  { key: 'qualite_controle',          label: '6. Démarche Qualité & Autocontrôle',                 mandatory: true },
  { key: 'securite_ppsps',            label: '7. Sécurité, Prévention & PPSPS',                   mandatory: true },
  { key: 'rse_environnement',         label: '8. RSE, Déchets BTP & Bilan Carbone',               mandatory: false },
  { key: 'sous_traitance',            label: '9. Politique de Sous-Traitance',                     mandatory: false },
  { key: 'planning_gantt',            label: '10. Planning Gantt Prévisionnel',                    mandatory: true },
];

// Sections texte auto-remplies au chargement depuis le corpus RAG. Le Gantt (planning_gantt)
// n'est pas une section texte : c'est un visuel (PNG) rendu par GanttPreview ci-dessous.
const AUTO_FILL_KEYS = SECTION_KEYS.filter((s) => s.mandatory && s.key !== 'planning_gantt').map((s) => s.key);

export default function EditorPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [project, setProject] = useState<Project | null>(null);
  const [sections, setSections] = useState<GeneratedSection[]>([]);
  const [activeKey, setActiveKey] = useState(SECTION_KEYS[0].key);
  const [generating, setGenerating] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [chatOpen, setChatOpen] = useState(false);
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
    }
    // On ne retire PAS la clé de `generating` ici en cas de succès : la génération réelle
    // se termine en tâche de fond (Celery). Le polling ci-dessous détecte la fin
    // (status !== 'processing') et nettoie `generating` à ce moment-là.
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
            }
          }
          return next;
        });
      } catch (e) {
        console.error('Polling error:', e);
      }
      if (attempts >= 20 && pollTimer.current) {
        // Sécurité : on arrête après ~80s pour ne pas boucler indéfiniment si un worker
        // reste bloqué. Un clic manuel sur "Générer avec l'IA" relance la génération.
        clearInterval(pollTimer.current);
        pollTimer.current = null;
        setGenerating(new Set());
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

  const fallbackSection: GeneratedSection = {
    id: `temp-${activeKey}`,
    tenant_id: '11111111-1111-1111-1111-111111111111',
    project_id: projectId,
    section_key: activeKey,
    title: activeMetaSection?.label || 'Section',
    order_index: SECTION_KEYS.findIndex((s) => s.key === activeKey),
    content_html:
      activeSection?.content_html ||
      (isActiveGenerating
        ? '<p>⏳ Génération automatique en cours à partir de votre base de connaissances (RAG)…</p>'
        : '<p>Cliquez sur "Générer avec l\\'IA" ou commencez à rédiger...</p>'),
    content_json: {},
    visual_placeholders: [],
    compliance_score: activeSection?.compliance_score || 85,
    status: activeSection?.status || 'generating',
    locked_for_export: activeSection?.locked_for_export || false,
    updated_at: new Date().toISOString(),
  };

  const currentSection = activeSection || fallbackSection;

  return (
    <div className="flex h-[calc(100vh-120px)] gap-4 pb-4">
      {/* Left Panel: Section Navigator */}
      <div className="w-64 shrink-0 overflow-y-auto rounded-2xl bg-slate-900/80 border border-slate-800 p-3 space-y-1">
        <p className="text-[10px] font-bold uppercase text-slate-500 px-2 pb-2 tracking-widest">Sections du Mémoire</p>
        {SECTION_KEYS.map((meta) => {
          const sec = findSection(meta.key);
          const isActive = activeKey === meta.key;
          const hasContent = Boolean(sec?.content_html) || meta.key === 'planning_gantt';
          const isKeyGenerating = generating.has(meta.key);
          const score = sec?.compliance_score;
          const isLocked = sec?.locked_for_export;

          return (
            <button
              key={meta.key}
              onClick={() => setActiveKey(meta.key)}
              className={`w-full text-left px-3 py-2.5 rounded-xl flex items-start gap-2.5 transition-all group ${
                isActive
                  ? 'bg-sky-600/20 border border-sky-500/40 text-sky-300'
                  : 'hover:bg-slate-800/60 text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="mt-0.5 shrink-0">
                {isKeyGenerating
                  ? <Loader2 className="w-3.5 h-3.5 text-sky-400 animate-spin" />
                  : isLocked
                    ? <Lock className="w-3.5 h-3.5 text-emerald-400" />
                    : hasContent
                      ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      : <div className="w-3.5 h-3.5 rounded-full border border-slate-600 border-dashed" />
                }
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-semibold leading-tight line-clamp-2">{meta.label}</p>
                {meta.key === 'planning_gantt' ? (
                  <p className="text-[10px] font-mono mt-0.5 text-sky-400">Studio Visuels</p>
                ) : score !== undefined && (
                  <p className={`text-[10px] font-mono mt-0.5 ${score >= 90 ? 'text-emerald-400' : score >= 70 ? 'text-amber-400' : 'text-rose-400'}`}>
                    Score RC : {score}%
                  </p>
                )}
              </div>
              {!meta.mandatory && (
                <span className="text-[9px] font-semibold text-slate-600 bg-slate-800 px-1 py-0.5 rounded shrink-0">opt.</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Right Panel: Editor */}
      <div className="flex-1 overflow-y-auto space-y-4">
        {/* Section Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-2xl bg-slate-900/80 border border-slate-800">
          <div>
            <h2 className="text-sm font-bold text-white">{activeMetaSection?.label}</h2>
            {!activeMetaSection?.mandatory && (
              <p className="text-[11px] text-slate-500">Section optionnelle — peut être omise si non requise par le RC</p>
            )}
            {isGanttSection && (
              <p className="text-[11px] text-slate-500">Généré automatiquement (Python/Matplotlib) — voir aussi le Studio Visuels</p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setChatOpen(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-slate-200 text-xs font-semibold hover:bg-slate-700 transition-all"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Assistant Q&A
            </button>

            {!isGanttSection && (
              <button
                onClick={() => handleGenerate(activeKey)}
                disabled={isActiveGenerating}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-sky-600/20 border border-sky-500/30 text-sky-300 text-xs font-semibold hover:bg-sky-600/30 transition-all disabled:opacity-60"
              >
                {isActiveGenerating
                  ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Génération IA…</>
                  : <><Sparkles className="w-3.5 h-3.5" /> Générer avec l'IA</>
                }
              </button>
            )}
          </div>
        </div>

        {/* Editor Area */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
          </div>
        ) : isGanttSection ? (
          <GanttPreview projectId={projectId} projectTitle={project?.title || 'Projet BTP'} />
        ) : (
          <div className="rounded-2xl overflow-hidden border border-slate-800 bg-slate-950/40">
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
        {!isGanttSection && currentSection?.compliance_score !== undefined && (
          <div className={`p-4 rounded-2xl border text-sm font-semibold flex items-center gap-2 ${
            currentSection.compliance_score >= 90
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : currentSection.compliance_score >= 70
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
          }`}>
            {currentSection.compliance_score >= 90
              ? <CheckCircle2 className="w-4 h-4" />
              : <AlertTriangle className="w-4 h-4" />
            }
            Score de conformité RC : <span className="font-mono text-lg">{currentSection.compliance_score}%</span>
            {currentSection.compliance_score < 80 && ' — Des critères RC manquent dans cette section. Régénérez ou complétez manuellement.'}
          </div>
        )}
      </div>

      <DCEChatSidebar
        projectId={projectId}
        projectTitle={project?.title || ''}
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
      />
    </div>
  );
}
"""

apply_patch(EDITOR_PAGE, [("full-file replace", ORIGINAL, NEW)])
print("EDITOR PAGE REWRITE APPLIED SUCCESSFULLY.")
