'use client';

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
    content_html: activeSection?.content_html || '<p>Cliquez sur "Générer avec l\'IA" ou commencez à rédiger...</p>',
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
