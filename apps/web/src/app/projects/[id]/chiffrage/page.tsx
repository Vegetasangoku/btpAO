'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { PricingChiffrage } from '@/components/pricing/pricing-chiffrage';

export default function ChiffragePage() {
  const params = useParams();
  const projectId = params.id as string;
  return <PricingChiffrage projectId={projectId} />;
}
