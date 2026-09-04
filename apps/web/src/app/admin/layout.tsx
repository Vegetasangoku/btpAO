import React from 'react';
import { SuperAdminSidebar } from '@/components/layout/super-admin-sidebar';

export default function SuperAdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-background text-foreground font-sans">
      <SuperAdminSidebar />
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <div className="flex-1 px-5 sm:px-7 lg:px-9 py-6 lg:py-8 max-w-[1320px] w-full mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
