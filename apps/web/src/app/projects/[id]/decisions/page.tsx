'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { DecisionForm } from '@/components/decisions/decision-form';

export default function DecisionsPage() {
  const params = useParams();
  const projectId = params.id as string;

  return (
    <div className="space-y-6 pb-12">
      <div>
        <h1 className="text-2xl font-extrabold text-white">Données & Choix Conducteur de Travaux</h1>
        <p className="text-sm text-slate-400 mt-1">
          Renseignez les paramètres spécifiques au chantier : délais contractuels, matériel lourd, encadrement qualifié,
          phasage des travaux, engagements RSE/déchets et plan PPSPS.
          Ces données alimentent directement l'IA de génération.
        </p>
      </div>
      <DecisionForm projectId={projectId} />
    </div>
  );
}
