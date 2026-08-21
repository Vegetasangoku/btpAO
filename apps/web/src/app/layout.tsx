import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'btpAO - Générateur de Mémoires Techniques BTP',
  description: 'Solution B2B dédiée au BTP : Ingestion DCE, Chiffrage, Rédaction assistée par IA et Export de mémoires techniques conformes.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" className="dark">
      <body className="bg-slate-950 text-slate-100 min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
