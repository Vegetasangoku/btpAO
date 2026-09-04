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
import { useTranslation } from '@/components/i18n-provider';

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
  projectId?: string;
  projectTitle?: string;
  isOpen: boolean;
  onClose: () => void;
  // 'project' (défaut) interroge le DCE + corpus du projet en cours (nécessite projectId).
  // 'company' interroge le savoir-faire entreprise (Mon Entreprise), sans projet particulier.
  mode?: 'project' | 'company';
}

export function DCEChatSidebar({ projectId, projectTitle, isOpen, onClose, mode = 'project' }: DCEChatSidebarProps) {
  const { t } = useTranslation();
  const [sourceMode, setSourceMode] = useState<'corpus' | 'corpus_web' | 'web'>('corpus');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'm-1',
      sender: 'assistant',
      text: mode === 'company'
        ? t('chat.sidebar.welcome_company')
        : t('chat.sidebar.welcome_project', { title: projectTitle || t('chat.sidebar.project_fallback') }),
      source_mode: 'corpus',
      sources: mode === 'company'
        ? [{ title: t('chat.sidebar.src_company_title'), citation: t('chat.sidebar.src_company_citation'), snippet: t('chat.sidebar.src_company_snippet') }]
        : [{ title: t('chat.sidebar.src_project_title'), page: 1, citation: t('chat.sidebar.src_project_citation'), snippet: t('chat.sidebar.src_project_snippet') }],
      timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const SUGGESTED_PROMPTS = mode === 'company'
    ? [
        t('chat.sidebar.prompt_company_1'),
        t('chat.sidebar.prompt_company_2'),
        t('chat.sidebar.prompt_company_3'),
        t('chat.sidebar.prompt_company_4'),
      ]
    : [
        t('chat.sidebar.prompt_project_1'),
        t('chat.sidebar.prompt_project_2'),
        t('chat.sidebar.prompt_project_3'),
        t('chat.sidebar.prompt_project_4'),
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
      const res = mode === 'company'
        ? await api.askCompany(q, sourceMode)
        : await api.askProject(projectId as string, q, sourceMode);

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
        ? t('chat.sidebar.error_session_expired')
        : (err?.message || t('chat.sidebar.error_generic'));

      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'assistant',
          text: `⚠️ **${t('chat.sidebar.error_prefix')}** : ${errorText}`,
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
    <div className="fixed inset-y-0 right-0 w-full sm:w-[480px] bg-card backdrop-blur-xl border-l border-line shadow-floating z-50 flex flex-col animate-in slide-in-from-right duration-300 font-sans">
      {/* Header */}
      <div className="p-4 border-b border-line bg-sunken space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-hl text-hl-contrast flex items-center justify-center shadow-xs">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-foreground flex items-center gap-1.5 font-heading">
                <span>{mode === 'company' ? t('chat.sidebar.header_title_company') : t('chat.sidebar.header_title_project')}</span>
                <span className="w-2 h-2 rounded-full bg-positive animate-pulse" />
              </h3>
              <p className="text-[10px] text-muted-foreground truncate max-w-[260px]">
                {mode === 'company' ? t('chat.sidebar.header_sub_company') : (projectTitle || t('chat.sidebar.header_sub_project_fallback'))}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-card transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 3-Choice Source Selector */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px] text-muted-foreground font-medium">
            <span>{t('chat.sidebar.scope_label')}</span>
            <span className="text-hl font-bold">
              {sourceMode === 'corpus' && (mode === 'company' ? t('chat.sidebar.scope_corpus_company') : t('chat.sidebar.scope_corpus_project'))}
              {sourceMode === 'corpus_web' && t('chat.sidebar.scope_corpus_web')}
              {sourceMode === 'web' && (mode === 'company' ? t('chat.sidebar.scope_web_company') : t('chat.sidebar.scope_web_project'))}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-1.5 p-1 rounded-xl bg-card border border-line text-[11px]">
            <button
              type="button"
              onClick={() => setSourceMode('corpus')}
              className={`py-1.5 px-2 rounded-lg font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                sourceMode === 'corpus'
                  ? 'bg-hl text-hl-contrast shadow-xs'
                  : 'text-muted-foreground hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-raised'
              }`}
            >
              <Database className="w-3 h-3" />
              <span>{t('chat.sidebar.btn_corpus')}</span>
            </button>

            <button
              type="button"
              onClick={() => setSourceMode('corpus_web')}
              className={`py-1.5 px-2 rounded-lg font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                sourceMode === 'corpus_web'
                  ? 'bg-hl text-hl-contrast shadow-xs'
                  : 'text-muted-foreground hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-raised'
              }`}
            >
              <Layers className="w-3 h-3" />
              <span>{t('chat.sidebar.btn_corpus_web')}</span>
            </button>

            <button
              type="button"
              onClick={() => setSourceMode('web')}
              className={`py-1.5 px-2 rounded-lg font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                sourceMode === 'web'
                  ? 'bg-hl text-hl-contrast shadow-xs'
                  : 'text-muted-foreground hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-raised'
              }`}
            >
              <Globe className="w-3 h-3" />
              <span>{t('chat.sidebar.btn_web')}</span>
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
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              {m.sender === 'user' ? (
                <>
                  <span className="px-1.5 py-0.5 rounded bg-slate-200 dark:bg-raised text-foreground font-mono text-[9px]">
                    {t('chat.sidebar.mode_prefix', { mode: m.source_mode || 'corpus' })}
                  </span>
                  <span>{t('chat.sidebar.you')}</span>
                  <span>•</span>
                  <span>{m.timestamp}</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3 h-3 text-hl" />
                  <span className="font-bold text-foreground">{t('chat.sidebar.assistant_name')}</span>
                  <span>•</span>
                  <span>{m.timestamp}</span>
                </>
              )}
            </div>

            <div
              className={`p-3.5 rounded-2xl max-w-[92%] leading-relaxed ${
                m.sender === 'user'
                  ? 'bg-hl text-hl-contrast rounded-tr-sm shadow-xs'
                  : 'bg-sunken border border-line text-foreground rounded-tl-sm'
              }`}
            >
              {m.is_degraded && (
                <div className="mb-2 p-2.5 rounded-xl bg-slate-100 dark:bg-card border border-line text-foreground text-[10px] flex items-center gap-1.5 font-medium">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0 text-hl" />
                  {/* Le serveur renvoie la cause exacte (clé absente, plafond
                      atteint, appel refusé). L'afficher évite d'envoyer chercher
                      une panne là où il manque un réglage. */}
                  <span>{m.degraded_reason || t('chat.sidebar.degraded_notice')}</span>
                </div>
              )}

              <div className="whitespace-pre-wrap">{m.text}</div>

              {/* Source Citations with strict tags */}
              {m.sources && m.sources.length > 0 && (
                <div className="mt-3 pt-2.5 border-t border-line space-y-1.5">
                  <p className="text-[10px] font-bold text-muted-foreground flex items-center gap-1 font-heading">
                    <BookOpen className="w-3 h-3 text-hl" />
                    <span>{t('chat.sidebar.sources_identified', { count: m.sources.length })}</span>
                  </p>
                  <div className="space-y-1">
                    {m.sources.map((s, idx) => (
                      <div
                        key={idx}
                        className="p-2 rounded-lg bg-card border border-line text-[10px] text-foreground space-y-0.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-foreground flex items-center gap-1">
                            {s.type === 'web' ? <Globe className="w-3 h-3 text-positive" /> : <FileText className="w-3 h-3 text-hl" />}
                            {s.citation || s.title || t('chat.sidebar.source_fallback', { n: idx + 1 })}
                          </span>
                          {s.url && (
                            <a
                              href={s.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[9px] text-hl hover:underline flex items-center gap-0.5"
                            >
                              <span>{t('chat.sidebar.open_link')}</span>
                              <ExternalLink className="w-2.5 h-2.5" />
                            </a>
                          )}
                        </div>
                        {s.snippet && (
                          <p className="text-[10px] text-muted-foreground line-clamp-2">
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
          <div className="flex items-center gap-2 p-3 rounded-2xl bg-white dark:bg-raised border border-line text-xs text-hl">
            <Loader2 className="w-4 h-4 animate-spin shrink-0" />
            <div className="space-y-0.5">
              <p className="font-semibold">{t('chat.sidebar.loading_search', { mode: sourceMode })}</p>
              <p className="text-[10px] text-muted-foreground">{t('chat.sidebar.loading_detail')}</p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Prompts if few messages */}
      {messages.length <= 2 && (
        <div className="px-4 py-2 border-t border-line bg-slate-50 dark:bg-card">
          <p className="text-[10px] font-bold text-muted-foreground mb-1.5 uppercase tracking-wider">
            {t('chat.sidebar.suggested_questions')}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTED_PROMPTS.map((p, idx) => (
              <button
                key={idx}
                onClick={() => handleSendMessage(p)}
                className="text-[10px] py-1 px-2.5 rounded-lg bg-white dark:bg-raised hover:bg-sunken border border-line text-foreground hover:text-hl transition-colors text-left cursor-pointer"
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="p-4 border-t border-line bg-sunken">
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
            placeholder={mode === 'company' ? t('chat.sidebar.placeholder_company', { mode: sourceMode }) : t('chat.sidebar.placeholder_project', { mode: sourceMode })}
            disabled={isLoading}
            className="input-field !py-2 !text-xs"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="p-2.5 rounded-xl bg-hl hover:bg-hl-strong text-hl-contrast disabled:opacity-40 shadow-xs transition-all cursor-pointer"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
