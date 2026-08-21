'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function RootRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/dashboard');
  }, [router]);

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400 text-sm">
      <span>Chargement de votre espace de travail BTP...</span>
    </div>
  );
}
