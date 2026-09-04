'use client';

import React, { useState } from 'react';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Shield,
  Layers,
  Search,
} from 'lucide-react';
import { DCECriterion } from '@/lib/types';
import { api } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';

interface DCEUploaderProps {
  projectId: string;
  criteria?: DCECriterion[];
  onCriteriaExtracted?: (criteria: DCECriterion[]) => void;
}

export function DCEUploader({ projectId, criteria = [], onCriteriaExtracted }: DCEUploaderProps) {
  const { t } = useTranslation();
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [docType, setDocType] = useState('rc');
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    setIsUploading(true);
    setUploadProgress(20);
    setStatusMessage(t('dce.uploader.status_uploading'));

    try {
      setTimeout(() => setUploadProgress(50), 400);
      setTimeout(() => setStatusMessage(t('dce.uploader.status_analyzing')), 800);
      setTimeout(() => setUploadProgress(80), 1200);
      setTimeout(() => setStatusMessage(t('dce.uploader.status_indexing')), 1600);

      const res = await api.uploadDCE(projectId, docType, file);
      setUploadProgress(100);
      setStatusMessage(t('dce.uploader.status_success'));

      // Refresh criteria
      const updatedCriteria = await api.getCriteria(projectId);
      if (onCriteriaExtracted) {
        onCriteriaExtracted(updatedCriteria);
      }
    } catch (err) {
      console.error('Upload failed', err);
      setStatusMessage(t('dce.uploader.status_error'));
    } finally {
      setTimeout(() => {
        setIsUploading(false);
        setUploadProgress(0);
      }, 3000);
    }
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Upload Box Card */}
      <div className="card-modern p-6 sm:p-7 space-y-5 rounded-2xl">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-line">
          <div>
            <h3 className="text-[14px] font-bold text-foreground flex items-center gap-2 font-heading">
              <UploadCloud className="w-4 h-4 text-hl" />
              {t('dce.uploader.title')}
            </h3>
            <p className="text-[12px] text-muted-foreground mt-0.5">
              {t('dce.uploader.subtitle')}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-[12px] text-muted-foreground font-medium">{t('dce.uploader.doc_type_label')}</label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="input-field !w-auto !py-1.5 !px-3 !text-[12px] cursor-pointer"
            >
              <option value="rc">{t('dce.uploader.opt_rc')}</option>
              <option value="cctp">{t('dce.uploader.opt_cctp')}</option>
              <option value="ccap">{t('dce.uploader.opt_ccap')}</option>
              <option value="bpu">{t('dce.uploader.opt_bpu')}</option>
              <option value="autre">{t('dce.uploader.opt_autre')}</option>
            </select>
          </div>
        </div>

        {/* Drag & Drop Zone */}
        <label className="border-2 border-dashed border-slate-300 dark:border-line hover:border-hl/60 rounded-2xl p-8 flex flex-col items-center justify-center gap-3 cursor-pointer card-inset transition-all duration-200 group">
          <div className="w-12 h-12 rounded-xl bg-hl text-hl-contrast flex items-center justify-center group-hover:scale-105 transition-transform shadow-xs">
            <UploadCloud className="w-6 h-6" />
          </div>
          <div className="text-center space-y-1">
            <p className="text-[13px] font-bold text-foreground font-heading">
              {t('dce.uploader.dropzone_text')}<span className="text-hl underline ml-1">{t('dce.uploader.dropzone_link')}</span>
            </p>
            <p className="text-[11px] text-muted-foreground">
              {t('dce.uploader.dropzone_formats')}
            </p>
          </div>
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileUpload}
            disabled={isUploading}
            className="hidden"
          />
        </label>

        {/* Upload Progress Bar */}
        {isUploading && (
          <div className="space-y-2 p-4 rounded-xl card-inset border border-hl/30">
            <div className="flex justify-between text-[12px] font-semibold">
              <span className="text-hl flex items-center gap-2">
                <Sparkles className="w-3.5 h-3.5 text-hl animate-spin" />
                {statusMessage}
              </span>
              <span className="text-muted-foreground font-mono">{uploadProgress}%</span>
            </div>
            <div className="w-full bg-slate-200 dark:bg-raised rounded-full h-2 overflow-hidden">
              <div
                className="bg-gradient-to-r from-hl to-positive h-2 transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Extracted Criteria Table */}
      <div className="card-modern p-6 sm:p-7 space-y-5 rounded-2xl">
        <div className="flex items-center justify-between pb-3 border-b border-line">
          <div>
            <h3 className="text-[14px] font-bold text-foreground flex items-center gap-2 font-heading">
              <Layers className="w-4 h-4 text-positive" />
              {t('dce.uploader.criteria_title')}
            </h3>
            <p className="text-[12px] text-muted-foreground mt-0.5">
              {t('dce.uploader.criteria_subtitle')}
            </p>
          </div>

          <span className="badge-pill-emerald text-[10px]">
            {t('dce.uploader.weight_badge')}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {criteria.map((c, idx) => (
            <div
              key={c.id || idx}
              className="p-4 rounded-xl card-inset hover:border-hl/40 transition-all flex flex-col justify-between space-y-3"
            >
              <div className="space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <h4 className="text-[13px] font-bold text-foreground font-heading">{c.criterion_title}</h4>
                  <span className="shrink-0 badge-pill text-[10px] font-mono font-bold">
                    {c.weight_percentage}%
                  </span>
                </div>
                <p className="text-[12px] text-muted-foreground leading-relaxed">{c.description}</p>
              </div>

              <div className="space-y-1.5 pt-2 border-t border-line">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {t('dce.uploader.expectations_label')}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {c.key_expectations.map((exp, eIdx) => (
                    <span
                      key={eIdx}
                      className="text-[10px] badge-pill-slate"
                    >
                      ✓ {exp}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
