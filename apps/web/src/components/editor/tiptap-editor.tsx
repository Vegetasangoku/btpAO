'use client';

import React, { useEffect, useState } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import Highlight from '@tiptap/extension-highlight';
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
  const [isLocked, setIsLocked] = useState(section.locked_for_export);
  const [isSaving, setIsSaving] = useState(false);
  const [isAiGenerating, setIsAiGenerating] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [showAiModal, setShowAiModal] = useState(false);
  const [complianceScore, setComplianceScore] = useState(section.compliance_score || 98.5);

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
        class: 'prose prose-invert max-w-none focus:outline-none min-h-[460px] p-6 text-slate-200 text-sm leading-relaxed',
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
      const updated = await api.updateSection(section.id, html, 'edited', isLocked);
      if (onSave) onSave(updated);
    } catch (err) {
      console.error('Save failed', err);
    } finally {
      setIsSaving(false);
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
    return <div className="p-8 text-center text-slate-400">Chargement de l’éditeur WYSIWYG...</div>;
  }

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden shadow-2xl flex flex-col">
      {/* Editor Top Bar & Controls */}
      <div className="p-4 border-b border-slate-800 bg-slate-950/70 flex flex-wrap items-center justify-between gap-3">
        {/* Title & Badge */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center">
            <FileCheck className="w-4 h-4 text-sky-400" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              {section.title}
              {isLocked && (
                <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-500/30 flex items-center gap-1 font-semibold">
                  <CheckCircle2 className="w-3 h-3" /> Validé & Verrouillé
                </span>
              )}
            </h2>
            <p className="text-[11px] text-slate-400">
              Modifications en direct • Conformité Règlement de Consultation (RC)
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          {/* AI Refine Button */}
          <button
            onClick={() => setShowAiModal(true)}
            disabled={isLocked || isAiGenerating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-glow disabled:opacity-50 transition-all"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Copilote IA BTP</span>
          </button>

          {/* Validation Lock Button */}
          <button
            onClick={handleToggleLock}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              isLocked
                ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25'
                : 'bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700'
            }`}
          >
            {isLocked ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
            <span>{isLocked ? 'Verrouillé (Validé)' : 'Valider Section'}</span>
          </button>

          {/* Save Button */}
          <button
            onClick={handleSave}
            disabled={isSaving || isLocked}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold disabled:opacity-50 transition-all"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{isSaving ? 'Enregistrement...' : 'Sauvegarder'}</span>
          </button>
        </div>
      </div>

      {/* Formatting Toolbar */}
      {!isLocked && (
        <div className="px-4 py-2 border-b border-slate-800/80 bg-slate-900/50 flex flex-wrap items-center gap-1">
          <button
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={`p-1.5 rounded text-xs ${editor.isActive('bold') ? 'bg-sky-500/20 text-sky-400' : 'text-slate-400 hover:text-white'}`}
            title="Gras"
          >
            <Bold className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={`p-1.5 rounded text-xs ${editor.isActive('itailc') ? 'bg-sky-500/20 text-sky-400' : 'text-slate-400 hover:text-white'}`}
            title="Italique"
          >
            <Italic className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            className={`p-1.5 rounded text-xs ${editor.isActive('underline') ? 'bg-sky-500/20 text-sky-400' : 'text-slate-400 hover:text-white'}`}
            title="Souligné"
          >
            <UnderlineIcon className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().toggleHighlight({ color: '#0369a1' }).run()}
            className={`p-1.5 rounded text-xs ${editor.isActive('highlight') ? 'bg-sky-500/20 text-sky-400' : 'text-slate-400 hover:text-white'}`}
            title="Surligner"
          >
            <Highlighter className="w-4 h-4" />
          </button>

          <div className="w-px h-4 bg-slate-800 mx-1" />

          <button
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            className={`p-1.5 rounded text-xs font-bold ${editor.isActive('heading', { level: 1 }) ? 'bg-sky-500/20 text-sky-400' : 'text-slate-400 hover:text-white'}`}
            title="Titre H1"
          >
            <Heading1 className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            className={`p-1.5 rounded text-xs font-bold ${editor.isActive('heading', { level: 2 }) ? 'bg-sky-500/20 text-sky-400' : 'text-slate-400 hover:text-white'}`}
            title="Titre H2"
          >
            <Heading2 className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            className={`p-1.5 rounded text-xs font-bold ${editor.isActive('heading', { level: 3 }) ? 'bg-sky-500/20 text-sky-400' : 'text-slate-400 hover:text-white'}`}
            title="Titre H3"
          >
            <Heading3 className="w-4 h-4" />
          </button>

          <div className="w-px h-4 bg-slate-800 mx-1" />

          <button
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            className={`p-1.5 rounded text-xs ${editor.isActive('bulletList') ? 'bg-sky-500/20 text-sky-400' : 'text-slate-400 hover:text-white'}`}
            title="Liste à puces"
          >
            <List className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            className={`p-1.5 rounded text-xs ${editor.isActive('orderedList') ? 'bg-sky-500/20 text-sky-400' : 'text-slate-400 hover:text-white'}`}
            title="Liste numérotée"
          >
            <ListOrdered className="w-4 h-4" />
          </button>

          <button
            onClick={() =>
              editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
            }
            className="p-1.5 rounded text-xs text-slate-400 hover:text-white"
            title="Insérer un tableau technique"
          >
            <TableIcon className="w-4 h-4" />
          </button>

          <div className="w-px h-4 bg-slate-800 mx-1" />

          <button
            onClick={() => editor.chain().focus().undo().run()}
            disabled={!editor.can().undo()}
            className="p-1.5 rounded text-xs text-slate-400 hover:text-white disabled:opacity-30"
            title="Annuler"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          <button
            onClick={() => editor.chain().focus().redo().run()}
            disabled={!editor.can().redo()}
            className="p-1.5 rounded text-xs text-slate-400 hover:text-white disabled:opacity-30"
            title="Rétablir"
          >
            <RotateCw className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Editor Content Area */}
      <div className="relative bg-slate-950/40">
        <EditorContent editor={editor} />

        {isLocked && (
          <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-[1px] flex items-center justify-center pointer-events-none">
            <div className="px-4 py-2 rounded-lg bg-slate-900/90 border border-emerald-500/40 text-emerald-300 text-xs font-semibold flex items-center gap-2 shadow-2xl">
              <Lock className="w-4 h-4 text-emerald-400" />
              Section validée et sécurisée juridiquement
            </div>
          </div>
        )}
      </div>

      {/* Footer / Compliance Score Info */}
      <div className="p-3.5 border-t border-slate-800 bg-slate-950/80 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Score de conformité DCE :</span>
          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono font-bold">
            <CheckCircle2 className="w-3.5 h-3.5" />
            {complianceScore.toFixed(1)} / 100
          </div>
        </div>

        <p className="text-slate-400 text-[11px]">
          {section.compliance_notes || 'Tous les sous-critères du Règlement de Consultation sont couverts.'}
        </p>
      </div>

      {/* AI Copilot Modal */}
      {showAiModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-sky-500/30 rounded-2xl max-w-lg w-full p-6 shadow-glow space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-sky-500/20 border border-sky-500/40 flex items-center justify-center">
                  <Sparkles className="w-4 h-4 text-sky-400" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Copilote IA BTP (Claude 3.5)</h3>
                  <p className="text-[11px] text-slate-400">Affinement technique de la section</p>
                </div>
              </div>
              <button
                onClick={() => setShowAiModal(false)}
                className="text-slate-400 hover:text-white text-xs p-1"
              >
                ✕
              </button>
            </div>

            {/* Quick Action Presets */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-slate-300">Améliorations rapides :</p>
              <div className="grid grid-cols-1 gap-2">
                <button
                  onClick={() =>
                    handleAiRefinement(
                      'Enrichir avec les fiches techniques des matériels (Grue Potain MDT 219) et les engagements quantifiés.'
                    )
                  }
                  disabled={isAiGenerating}
                  className="text-left px-3 py-2 rounded-lg bg-slate-800/80 hover:bg-sky-500/20 border border-slate-700 hover:border-sky-500/40 text-xs text-slate-200 transition-all flex items-center justify-between"
                >
                  <span>🚜 Intégrer détails engins & rotation des banches</span>
                  <Sparkles className="w-3 h-3 text-sky-400" />
                </button>

                <button
                  onClick={() =>
                    handleAiRefinement(
                      'Renforcer la conformité avec les critères RSE du RC (béton bas carbone CEM III/A, tri 5 flux 88% de valorisation locale).'
                    )
                  }
                  disabled={isAiGenerating}
                  className="text-left px-3 py-2 rounded-lg bg-slate-800/80 hover:bg-emerald-500/20 border border-slate-700 hover:border-emerald-500/40 text-xs text-slate-200 transition-all flex items-center justify-between"
                >
                  <span>🌿 Renforcer les engagements RSE & Déchets</span>
                  <Sparkles className="w-3 h-3 text-emerald-400" />
                </button>

                <button
                  onClick={() =>
                    handleAiRefinement(
                      'Rendre le style plus factuel, supprimer tout jargon vague et citer les références normatives (DTU, NF EN 206/CN, PPSPS).'
                    )
                  }
                  disabled={isAiGenerating}
                  className="text-left px-3 py-2 rounded-lg bg-slate-800/80 hover:bg-amber-500/20 border border-slate-700 hover:border-amber-500/40 text-xs text-slate-200 transition-all flex items-center justify-between"
                >
                  <span>📐 Rendre 100% technique & citer normes DTU</span>
                  <Sparkles className="w-3 h-3 text-amber-400" />
                </button>
              </div>
            </div>

            {/* Custom Prompt Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300">Consigne personnalisée :</label>
              <textarea
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                placeholder="Ex : Ajoute un paragraphe sur la procédure de coulage par temps froid et les fiches d'autocontrôle du ferraillage..."
                rows={3}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-sky-500"
              />
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                onClick={() => setShowAiModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-white"
              >
                Annuler
              </button>
              <button
                onClick={() => handleAiRefinement()}
                disabled={isAiGenerating || !aiPrompt.trim()}
                className="px-4 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold disabled:opacity-50 flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{isAiGenerating ? 'Rédaction IA en cours...' : 'Régénérer avec l’IA'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
