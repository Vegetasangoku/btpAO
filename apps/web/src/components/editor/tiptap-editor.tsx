'use client';

import React, { useEffect, useState } from 'react';
import { useTranslation } from '@/components/i18n-provider';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import Highlight from '@tiptap/extension-highlight';

/* Lavis d'ocre corten — le rôle « accent » de la charte, aplati sur blanc.
   Littéral et non une variable CSS : cette couleur part dans le HTML du
   document et doit survivre à l'export Word. */
const EDITOR_HIGHLIGHT = '#F3E2CC';
import Underline from '@tiptap/extension-underline';
import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Heading1,
  Heading2,
  Heading3,
  List,
  ListOrdered,
  Table as TableIcon,
  Sparkles,
  Lock,
  Unlock,
  Save,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  RotateCw,
  Highlighter,
  FileCheck,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { GeneratedSection } from '@/lib/types';
import { api } from '@/lib/api';

interface TiptapEditorProps {
  section: GeneratedSection;
  projectId: string;
  onSave?: (updatedSection: GeneratedSection) => void;
  onRegenerate?: () => void;
}

export function TiptapEditor({ section, projectId, onSave, onRegenerate }: TiptapEditorProps) {
  const { t } = useTranslation();
  const [isLocked, setIsLocked] = useState(section.locked_for_export);
  const [isSaving, setIsSaving] = useState(false);
  const [isAiGenerating, setIsAiGenerating] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [showAiModal, setShowAiModal] = useState(false);
  const [complianceScore, setComplianceScore] = useState(section.compliance_score || 98.5);
  const [learningProposal, setLearningProposal] = useState<{
    section_type: string;
    summary: string;
    suggested_content: string;
    diff_percentage: number;
  } | null>(null);
  const [savingLearning, setSavingLearning] = useState(false);
  const [learningScope, setLearningScope] = useState<'this_ao' | 'similar_aos' | 'all_future'>('similar_aos');

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Underline,
      Highlight.configure({ multicolor: true }),
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: section.content_html,
    editable: !isLocked,
    editorProps: {
      attributes: {
        class: 'prose dark:prose-invert max-w-none focus:outline-none min-h-[460px] p-6 text-slate-700 dark:text-slate-200 text-sm leading-relaxed',
      },
    },
  });

  // Update content when section changes
  useEffect(() => {
    if (editor && section.content_html) {
      if (editor.getHTML() !== section.content_html) {
        editor.commands.setContent(section.content_html);
      }
      setIsLocked(section.locked_for_export);
      editor.setEditable(!section.locked_for_export);
    }
  }, [section, editor]);

  const handleSave = async () => {
    if (!editor) return;
    setIsSaving(true);
    try {
      const html = editor.getHTML();
      const res = await api.updateSection(section.id, html, 'edited', isLocked);
      if (onSave) onSave(res.section);
      if (res.learning_opportunity && res.learning_proposal) {
        setLearningProposal(res.learning_proposal);
      }
    } catch (err) {
      console.error('Save failed', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveLearning = async () => {
    if (!learningProposal) return;
    setSavingLearning(true);
    try {
      await api.createLearning({
        title: `Ajustement sur ${section.title}`,
        category: 'methodology',
        section_type: learningScope === 'all_future' ? undefined : learningProposal.section_type,
        project_id: learningScope === 'this_ao' ? projectId : undefined,
        learned_content: learningProposal.suggested_content,
        learning_insight: learningProposal.summary,
        source_outcome: 'manual_edit',
      });
      setLearningProposal(null);
      setLearningScope('similar_aos');
    } catch (err) {
      console.error('Learning save failed', err);
    } finally {
      setSavingLearning(false);
    }
  };

  const handleToggleLock = async () => {
    const newLock = !isLocked;
    setIsLocked(newLock);
    if (editor) editor.setEditable(!newLock);

    if (newLock) {
      // Trigger celebratory confetti on validation
      confetti({
        particleCount: 50,
        spread: 60,
        origin: { y: 0.8 },
      });
    }

    try {
      await api.updateSection(section.id, editor?.getHTML() || section.content_html, newLock ? 'validated' : 'edited', newLock);
    } catch (e) {
      console.warn('Update lock notice', e);
    }
  };

  const handleAiRefinement = async (presetInstruction?: string) => {
    setIsAiGenerating(true);
    const instruction = presetInstruction || aiPrompt;
    try {
      const regenerated = await api.generateSection(projectId, section.section_key, instruction);
      if (editor && regenerated.content_html) {
        editor.commands.setContent(regenerated.content_html);
        setComplianceScore(regenerated.compliance_score);
      }
      setShowAiModal(false);
      setAiPrompt('');
      if (onSave) onSave(regenerated);
    } catch (err) {
      console.error('AI generation failed', err);
    } finally {
      setIsAiGenerating(false);
    }
  };

  if (!editor) {
    return <div className="p-8 text-center text-slate-500 dark:text-slate-400">{t('editor.tiptap.loading')}</div>;
  }

  return (
    <div className="bg-card border border-line rounded-2xl overflow-hidden shadow-xs flex flex-col font-sans">
      {/* Editor Top Bar & Controls */}
      <div className="p-4 border-b border-line bg-sunken/80 flex flex-wrap items-center justify-between gap-3">
        {/* Title & Badge */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-hl/10 border border-hl/20 flex items-center justify-center">
            <FileCheck className="w-4 h-4 text-hl" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
              {section.title}
              {isLocked && (
                <span className="text-[10px] bg-positive/15 text-positive px-2 py-0.5 rounded-full border border-positive/30 flex items-center gap-1 font-semibold">
                  <CheckCircle2 className="w-3 h-3" /> {t('editor.tiptap.locked_badge')}
                </span>
              )}
            </h2>
            <p className="text-[11px] text-muted-foreground">
              {t('editor.tiptap.live_edits_subtitle')}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          {/* AI Refine Button */}
          <button
            onClick={() => setShowAiModal(true)}
            disabled={isLocked || isAiGenerating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-hl hover:bg-hl-strong text-hl-contrast text-xs font-semibold shadow-xs disabled:opacity-50 transition-all cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{t('editor.tiptap.btn_copilot')}</span>
          </button>

          {/* Validation Lock Button */}
          <button
            onClick={handleToggleLock}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
              isLocked
                ? 'bg-positive/15 border-positive/40 text-positive hover:bg-positive/25'
                : 'bg-sunken border-line text-foreground hover:bg-line/40'
            }`}
          >
            {isLocked ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
            <span>{isLocked ? t('editor.tiptap.btn_locked') : t('editor.tiptap.btn_validate')}</span>
          </button>

          {/* Save Button */}
          <button
            onClick={handleSave}
            disabled={isSaving || isLocked}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-hl hover:bg-hl-strong text-hl-contrast text-xs font-semibold disabled:opacity-50 transition-all cursor-pointer shadow-xs"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{isSaving ? t('editor.tiptap.saving') : t('editor.tiptap.btn_save')}</span>
          </button>
        </div>
      </div>

      {/* Learning Proposal Banner */}
      {learningProposal && (
        <div className="mx-4 mt-3 p-3.5 rounded-xl bg-hl/8 border border-hl/20 space-y-2.5 text-xs">
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

      {/* Formatting Toolbar */}
      {!isLocked && (
        <div className="px-4 py-2 border-b border-line bg-slate-50/50 dark:bg-card flex flex-wrap items-center gap-1">
          <button
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={`p-1.5 rounded-lg text-xs cursor-pointer ${editor.isActive('bold') ? 'bg-hl/15 text-hl' : 'text-muted-foreground hover:text-foreground'}`}
            title={t('editor.tiptap.tt_bold')}
          >
            <Bold className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={`p-1.5 rounded-lg text-xs cursor-pointer ${editor.isActive('itailc') ? 'bg-hl/15 text-hl' : 'text-muted-foreground hover:text-foreground'}`}
            title={t('editor.tiptap.tt_italic')}
          >
            <Italic className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            className={`p-1.5 rounded-lg text-xs cursor-pointer ${editor.isActive('underline') ? 'bg-hl/15 text-hl' : 'text-muted-foreground hover:text-foreground'}`}
            title={t('editor.tiptap.tt_underline')}
          >
            <UnderlineIcon className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().toggleHighlight({ color: EDITOR_HIGHLIGHT }).run()}
            className={`p-1.5 rounded-lg text-xs cursor-pointer ${editor.isActive('highlight') ? 'bg-hl/15 text-hl' : 'text-muted-foreground hover:text-foreground'}`}
            title={t('editor.tiptap.tt_highlight')}
          >
            <Highlighter className="w-4 h-4" />
          </button>

          <div className="w-px h-4 bg-slate-200 dark:bg-line mx-1" />

          <button
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            className={`p-1.5 rounded-lg text-xs font-bold cursor-pointer ${editor.isActive('heading', { level: 1 }) ? 'bg-hl/15 text-hl' : 'text-muted-foreground hover:text-foreground'}`}
            title={t('editor.tiptap.tt_h1')}
          >
            <Heading1 className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            className={`p-1.5 rounded-lg text-xs font-bold cursor-pointer ${editor.isActive('heading', { level: 2 }) ? 'bg-hl/15 text-hl' : 'text-muted-foreground hover:text-foreground'}`}
            title={t('editor.tiptap.tt_h2')}
          >
            <Heading2 className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            className={`p-1.5 rounded-lg text-xs font-bold cursor-pointer ${editor.isActive('heading', { level: 3 }) ? 'bg-hl/15 text-hl' : 'text-muted-foreground hover:text-foreground'}`}
            title={t('editor.tiptap.tt_h3')}
          >
            <Heading3 className="w-4 h-4" />
          </button>

          <div className="w-px h-4 bg-slate-200 dark:bg-line mx-1" />

          <button
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            className={`p-1.5 rounded-lg text-xs cursor-pointer ${editor.isActive('bulletList') ? 'bg-hl/15 text-hl' : 'text-muted-foreground hover:text-foreground'}`}
            title={t('editor.tiptap.tt_bullet_list')}
          >
            <List className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            className={`p-1.5 rounded-lg text-xs cursor-pointer ${editor.isActive('orderedList') ? 'bg-hl/15 text-hl' : 'text-muted-foreground hover:text-foreground'}`}
            title={t('editor.tiptap.tt_ordered_list')}
          >
            <ListOrdered className="w-4 h-4" />
          </button>

          <button
            onClick={() =>
              editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
            }
            className="p-1.5 rounded-lg text-xs text-muted-foreground hover:text-foreground cursor-pointer"
            title={t('editor.tiptap.tt_insert_table')}
          >
            <TableIcon className="w-4 h-4" />
          </button>

          <div className="w-px h-4 bg-slate-200 dark:bg-line mx-1" />

          <button
            onClick={() => editor.chain().focus().undo().run()}
            disabled={!editor.can().undo()}
            className="p-1.5 rounded-lg text-xs text-muted-foreground hover:text-foreground disabled:opacity-30 cursor-pointer"
            title={t('editor.tiptap.tt_undo')}
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().redo().run()}
            disabled={!editor.can().redo()}
            className="p-1.5 rounded-lg text-xs text-muted-foreground hover:text-foreground disabled:opacity-30 cursor-pointer"
            title={t('editor.tiptap.tt_redo')}
          >
            <RotateCw className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Editor Content Area */}
      <div className="relative bg-white dark:bg-sunken p-6">
        <EditorContent editor={editor} />

        {isLocked && (
          <div className="absolute inset-0 bg-white/70 dark:bg-sunken/70 backdrop-blur-[1px] flex items-center justify-center pointer-events-none">
            <div className="px-4 py-2 rounded-xl bg-card border border-positive/40 text-positive text-xs font-semibold flex items-center gap-2 shadow-xs">
              <Lock className="w-4 h-4 text-positive" />
              {t('editor.tiptap.locked_overlay')}
            </div>
          </div>
        )}
      </div>

      {/* Footer / Compliance Score Info */}
      <div className="p-3.5 border-t border-line bg-sunken/80 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">{t('editor.tiptap.compliance_label')}</span>
          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-positive/10 border border-positive/30 text-positive font-mono font-bold">
            <CheckCircle2 className="w-3.5 h-3.5" />
            {complianceScore.toFixed(1)} / 100
          </div>
        </div>

        <p className="text-muted-foreground text-[11px]">
          {section.compliance_notes || t('editor.tiptap.compliance_default_note')}
        </p>
      </div>

      {/* AI Copilot Modal */}
      {showAiModal && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-line rounded-2xl max-w-lg w-full p-6 shadow-floating space-y-4 animate-scale-in">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-hl/10 border border-hl/20 flex items-center justify-center">
                  <Sparkles className="w-4 h-4 text-hl" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-foreground font-heading">{t('editor.tiptap.modal_title')}</h3>
                  <p className="text-[11px] text-muted-foreground">{t('editor.tiptap.modal_subtitle')}</p>
                </div>
              </div>
              <button
                onClick={() => setShowAiModal(false)}
                className="text-slate-400 hover:text-slate-700 dark:hover:text-white text-xs p-1 cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Quick Action Presets */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-foreground">{t('editor.tiptap.quick_improvements')}</p>
              <div className="grid grid-cols-1 gap-2">
                <button
                  onClick={() =>
                    handleAiRefinement(
                      'Enrichir avec les fiches techniques des matériels (Grue Potain MDT 219) et les engagements quantifiés.'
                    )
                  }
                  disabled={isAiGenerating}
                  className="text-left px-3 py-2 rounded-xl bg-sunken hover:bg-hl/10 border border-line hover:border-hl/40 text-xs text-foreground transition-all flex items-center justify-between cursor-pointer"
                >
                  <span>{t('editor.tiptap.preset_engins')}</span>
                  <Sparkles className="w-3 h-3 text-hl" />
                </button>

                <button
                  onClick={() =>
                    handleAiRefinement(
                      'Renforcer la conformité avec les critères RSE du RC (béton bas carbone CEM III/A, tri 5 flux 88% de valorisation locale).'
                    )
                  }
                  disabled={isAiGenerating}
                  className="text-left px-3 py-2 rounded-xl bg-sunken hover:bg-positive/10 border border-line hover:border-positive/40 text-xs text-foreground transition-all flex items-center justify-between cursor-pointer"
                >
                  <span>{t('editor.tiptap.preset_rse')}</span>
                  <Sparkles className="w-3 h-3 text-positive" />
                </button>

                <button
                  onClick={() =>
                    handleAiRefinement(
                      'Rendre le style plus factuel, supprimer tout jargon vague et citer les références normatives (DTU, NF EN 206/CN, PPSPS).'
                    )
                  }
                  disabled={isAiGenerating}
                  className="text-left px-3 py-2 rounded-xl bg-sunken hover:bg-hl/10 border border-line hover:border-hl/40 text-xs text-foreground transition-all flex items-center justify-between cursor-pointer"
                >
                  <span>{t('editor.tiptap.preset_dtu')}</span>
                  <Sparkles className="w-3 h-3 text-hl" />
                </button>
              </div>
            </div>

            {/* Custom Prompt Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-foreground">{t('editor.tiptap.custom_prompt_label')}</label>
              <textarea
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                placeholder={t('editor.tiptap.custom_prompt_placeholder')}
                rows={3}
                className="input-field"
              />
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-line">
              <button
                onClick={() => setShowAiModal(false)}
                className="btn-secondary !py-2 !px-3 !text-xs cursor-pointer"
              >
                {t('editor.tiptap.btn_cancel')}
              </button>
              <button
                onClick={() => handleAiRefinement()}
                disabled={isAiGenerating || !aiPrompt.trim()}
                className="btn-primary !py-2 !px-4 !text-xs cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{isAiGenerating ? t('editor.tiptap.ai_writing') : t('editor.tiptap.btn_regenerate_ai')}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
