'use client';

import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, X } from 'lucide-react';

interface DismissibleNoticeProps {
  message: string;
  detail?: string;
  variant?: 'error' | 'success';
  onDismiss?: () => void;
}

export function DismissibleNotice({ message, detail, variant = 'error', onDismiss }: DismissibleNoticeProps) {
  const [showDetail, setShowDetail] = useState(false);

  const isError = variant === 'error';
  const styles = isError
    ? 'bg-danger/20 border-danger/30 text-danger'
    : 'bg-positive/20 border-positive/30 text-positive';
  const Icon = isError ? AlertTriangle : CheckCircle2;

  return (
    <div className={`p-3.5 rounded-xl border text-xs flex items-start gap-2.5 animate-in fade-in ${styles}`}>
      <Icon className="w-4 h-4 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="font-bold">{message}</p>
          {detail && (
            <button
              type="button"
              onClick={() => setShowDetail((v) => !v)}
              title={showDetail ? 'Masquer le d\u00e9tail technique' : 'Voir le d\u00e9tail technique'}
              className="shrink-0 w-4 h-4 rounded-full border border-current flex items-center justify-center text-[10px] font-bold opacity-60 hover:opacity-100 transition-opacity cursor-pointer"
            >
              i
            </button>
          )}
        </div>
        {detail && showDetail && (
          <p className="mt-1.5 font-mono text-[10px] opacity-80 break-all">{detail}</p>
        )}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 opacity-50 hover:opacity-100 transition-opacity cursor-pointer"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
