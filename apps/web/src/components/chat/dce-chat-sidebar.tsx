'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  MessageSquare,
  Send,
  Sparkles,
  BookOpen,
  X,
  Loader2,
  CheckCircle2,
  FileText,
  ExternalLink,
  Bot,
  User,
  ShieldCheck,
  Globe,
  Database,
  Layers,
  AlertCircle,
} from 'lucide-react';
import { api } from '@/lib/api';

interface ChatSource {
  type?: string;
  source?: string;
  title?: string;
  page?: number;
  url?: string;
  citation?: string;
  snippet?: string;
}

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  source_mode?: 'corpus' | 'corpus_web' | 'web';
  sources?: ChatSource[];
  is_degraded?: boolean;
  degraded_reason?: string;
  timestamp: string;
}


interface DCEChatSidebarProps {
  projectId: string;
  projectTitle: string;
  isOpen: boolean;
  onClose: () => void;
}

export function DCEChatSidebar({ projectId, projectTitle, isOpen, onClose }: DCEChatSidebarProps) {
  const [sourceMode, setSourceMode] = useState<'corpus' | 'corpus_web' | 'web'>('corpus');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'm-1',
      sender: 'assistant',
      text: `Bonjour ! Je suis votre **Assistant Technique BTP** pour le projet **${projectTitle || 'en cours'}**.\n\nPosez une question technique et sélectionnez votre source :\n- **Corpus** : Pièces du DCE et base de savoir-faire entreprise\n- **Corpus + Web** : Synthèse enrichie avec veille normative externe\n- **Web** : Recherche externe temps réel (DTU, normes, données marché)`,
      source_mode: 'corpus',
      sources: [
        { title: 'Pièces de Marché DCE', page: 1, citation: '[Source : DCE]', snippet: 'CCTP, RC, DPGF et savoir-faire entreprise indexés sous Postgres RLS' },
      ],
      timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const SUGGESTED_PROMPTS = [
    'Quelles sont les pénalités de retard et le délai d\'exécution ?',
    'Quelles sont les exigences béton bas-carbone (RE2020) ?',
    'Quels sont les critères de notation et pondérations du RC ?',
    'Quelles normes DTU s\'appliquent au gros œuvre ?',
  ];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSendMessage(queryToSend?: string) {
    const q = queryToSend || input;
    if (!q.trim() || isLoading) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      sender: 'user',
      text: q,
      source_mode: sourceMode,
      timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!queryToSend) setInput('');
    setIsLoading(true);

    try {
      const res = await api.askProject(projectId, q, sourceMode);

      const assistantMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        sender: 'assistant',
        text: res.answer_markdown,
        source_mode: res.source_mode as any,
        sources: res.sources || [],
        is_degraded: Boolean(res.is_degraded),
        degraded_reason: res.degraded_reason,
        timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, assistantMsg]);

    } catch (err: any) {
      const errorText = err?.status === 401 || err?.message?.includes('401')
        ? 'Session expirée, reconnecte-toi.'
        : (err?.message || 'Erreur lors de la consultation des sources.');

      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'assistant',
          text: `⚠️ **Erreur** : ${errorText}`,
          source_mode: sourceMode,
          sources: [],
          timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[480px] bg-slate-900/95 backdrop-blur-xl border-l border-slate-800 shadow-2xl z-50 flex flex-col animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="p-4 border-b border-slate-800 bg-slate-950/70 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-sky-500/20 text-sky-400 flex items-center justify-center border border-sky-500/30 shadow-glow">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-white flex items-center gap-1.5">
                <span>Assistant Q&A DCE & Normes</span>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              </h3>
              <p className="text-[10px] text-slate-400 truncate max-w-[260px]">
                {projectTitle || 'Projet en cours'}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 3-Choice Source Selector */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px] text-slate-400 font-medium">
            <span>Périmètre des sources :</span>
            <span className="text-sky-400 font-bold">
              {sourceMode === 'corpus' && 'Documents Projet & Entreprise'}
              {sourceMode === 'corpus_web' && 'Corpus + Recherche Web'}
              {sourceMode === 'web' && 'Recherche Web Externe Seule'}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-1.5 p-1 rounded-xl bg-slate-950/90 border border-slate-800 text-[11px]">
            <button
              type="button"
              onClick={() => setSourceMode('corpus')}
              className={`py-1.5 px-2 rounded-lg font-bold flex items-center justify-center gap-1.5 transition-all ${
                sourceMode === 'corpus'
                  ? 'bg-sky-600 text-white shadow-glow'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Database className="w-3 h-3" />
              <span>Corpus</span>
            </button>

            <button
              type="button"
              onClick={() => setSourceMode('corpus_web')}
              className={`py-1.5 px-2 rounded-lg font-bold flex items-center justify-center gap-1.5 transition-all ${
                sourceMode === 'corpus_web'
                  ? 'bg-sky-600 text-white shadow-glow'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Layers className="w-3 h-3" />
              <span>Corpus + Web</span>
            </button>

            <button
              type="button"
              onClick={() => setSourceMode('web')}
              className={`py-1.5 px-2 rounded-lg font-bold flex items-center justify-center gap-1.5 transition-all ${
                sourceMode === 'web'
                  ? 'bg-sky-600 text-white shadow-glow'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Globe className="w-3 h-3" />
              <span>Web</span>
            </button>
          </div>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex flex-col gap-1.5 ${
              m.sender === 'user' ? 'items-end' : 'items-start'
            }`}
          >
            <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
              {m.sender === 'user' ? (
                <>
                  <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[9px]">
                    Mode : {m.source_mode || 'corpus'}
                  </span>
                  <span>Vous</span>
                  <span>•</span>
                  <span>{m.timestamp}</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3 h-3 text-sky-400" />
                  <span className="font-bold text-sky-300">Assistant Technique</span>
                  <span>•</span>
                  <span>{m.timestamp}</span>
                </>
              )}
            </div>

            <div
              className={`p-3.5 rounded-2xl max-w-[92%] leading-relaxed ${
                m.sender === 'user'
                  ? 'bg-sky-600 text-white rounded-tr-sm'
                  : 'bg-slate-950/80 border border-slate-800 text-slate-200 rounded-tl-sm'
              }`}
            >
              {m.is_degraded && (
                <div className="mb-2 p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[10px] flex items-center gap-1.5 font-medium">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0 text-amber-400" />
                  <span>Réponse simplifiée / extrait direct : le service IA était temporairement indisponible.</span>
                </div>
              )}

              <div className="whitespace-pre-wrap">{m.text}</div>


              {/* Source Citations with strict tags */}
              {m.sources && m.sources.length > 0 && (
                <div className="mt-3 pt-2.5 border-t border-slate-800/80 space-y-1.5">
                  <p className="text-[10px] font-bold text-slate-400 flex items-center gap-1">
                    <BookOpen className="w-3 h-3 text-sky-400" />
                    <span>Sources identifiées ({m.sources.length}) :</span>
                  </p>
                  <div className="space-y-1">
                    {m.sources.map((s, idx) => (
                      <div
                        key={idx}
                        className="p-1.5 rounded-lg bg-slate-900/90 border border-slate-800/60 text-[10px] text-slate-300 space-y-0.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-sky-400 flex items-center gap-1">
                            {s.type === 'web' ? <Globe className="w-3 h-3 text-emerald-400" /> : <FileText className="w-3 h-3 text-sky-400" />}
                            {s.citation || s.title || `Source #${idx + 1}`}
                          </span>
                          {s.url && (
                            <a
                              href={s.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[9px] text-sky-400 hover:underline flex items-center gap-0.5"
                            >
                              <span>Ouvrir</span>
                              <ExternalLink className="w-2.5 h-2.5" />
                            </a>
                          )}
                        </div>
                        {s.snippet && (
                          <p className="text-[10px] text-slate-400 line-clamp-2">
                            {s.snippet}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 p-3 rounded-2xl bg-slate-950/80 border border-slate-800 text-xs text-sky-400">
            <Loader2 className="w-4 h-4 animate-spin shrink-0" />
            <div className="space-y-0.5">
              <p className="font-semibold">Recherche et synthèse en cours ({sourceMode})...</p>
              <p className="text-[10px] text-slate-500">Extraction des sources et vérification anti-hallucination</p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Prompts if few messages */}
      {messages.length <= 2 && (
        <div className="px-4 py-2 border-t border-slate-800/60 bg-slate-950/40">
          <p className="text-[10px] font-bold text-slate-500 mb-1.5 uppercase tracking-wider">
            Questions suggérées :
          </p>
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTED_PROMPTS.map((p, idx) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(p)}
                className="text-[10px] py-1 px-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition-colors text-left"
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/80">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Poser une question sur le projet (${sourceMode})...`}
            disabled={isLoading}
            className="flex-1 px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 focus:border-sky-500 text-white text-xs placeholder:text-slate-600 focus:outline-none transition-colors"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="p-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white disabled:opacity-40 shadow-glow transition-all"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
