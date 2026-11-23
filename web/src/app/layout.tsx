import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono, Instrument_Serif } from 'next/font/google';
import './globals.css';

const sans = Geist({ subsets: ['latin'], variable: '--font-geist', display: 'swap' });
const mono = Geist_Mono({ subsets: ['latin'], variable: '--font-geist-mono', display: 'swap' });
const serif = Instrument_Serif({
  subsets: ['latin'],
  weight: '400',
  style: ['normal', 'italic'],
  variable: '--font-instrument',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Multi-Agent Risk & Compliance Console | Google ADK + A2A + MCP',
  description:
    'Google ADK orchestrator delegating over A2A to specialist agents with stdio MCP tools on private Cloud Run, fronted by a server-side OIDC BFF.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#F3F1EA',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} ${serif.variable}`}>
      <body className="min-h-screen bg-paper font-sans text-ink antialiased">{children}</body>
    </html>
  );
}
