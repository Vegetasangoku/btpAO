import React from 'react';
import { UserSidebar } from '@/components/layout/user-sidebar';
import { Header } from '@/components/layout/header';
import { ProjectPipelineNav } from '@/components/layout/project-pipeline-nav';

export default function ProjectsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-hl-soft dark:bg-sunken text-foreground font-sans transition-colors duration-150">
      <UserSidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-y-auto p-5 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <ProjectPipelineNav />
          {children}
        </main>
      </div>
    </div>
  );
}
