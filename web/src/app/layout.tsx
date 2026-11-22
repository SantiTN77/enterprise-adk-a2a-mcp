import type { Metadata, Viewport } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Enterprise Multi-Agent Risk & Compliance Console | ADK + A2A + MCP',
  description:
    'Senior AI Architect portfolio console executing Google ADK multi-agent A2A delegation and MCP tool execution on private Cloud Run via a Vercel server-side OIDC BFF.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
