'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { DCEUploader } from '@/components/dce/dce-uploader';

export default function DCEPage() {
  const params = useParams();
  const projectId = params.id as string;

  return (
    <div className="space-y-6 pb-12">
      <div>
        <h1 className="text-2xl font-extrabold text-white">Ingestion & Analyse du DCE</h1>
        <p className="text-sm text-slate-400 mt-1">
          Déposez le CCTP, le RC et tout autre document du Dossier de Consultation des Entreprises.
          L'OCR extrait automatiquement les critères de notation et les exigences techniques.
        </p>
      </div>
      <DCEUploader projectId={projectId} />
    </div>
  );
}
