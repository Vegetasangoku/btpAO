import type { Metadata } from 'next';
import './globals.css';
import { ThemeProvider } from '@/components/theme-provider';
import { I18nProvider } from '@/components/i18n-provider';

export const metadata: Metadata = {
  title: 'btpAO — Plateforme de Réponse aux Appels d’Offres BTP',
  description: 'Ingestion des pièces de marché, chiffrage chantier, rédaction assistée par IA et exports Word/PDF certifiés.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="fr"
      className="dark"
      suppressHydrationWarning
    >
      <body className="bg-background text-foreground min-h-screen antialiased font-sans selection:bg-hl/20 selection:text-hl dark:selection:text-hl transition-colors duration-150">
        <ThemeProvider>
          <I18nProvider>
            {children}
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
