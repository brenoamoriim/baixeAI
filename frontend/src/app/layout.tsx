import type { Metadata } from "next";
import Link from "next/link";
import { ConsentBanner } from "@/components/ConsentBanner";
import { SiteHeader } from "@/components/SiteHeader";
import { SITE_NAME, SITE_URL } from "@/lib/site";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: `${SITE_NAME} — conversores, removedor de fundo, removedor de objetos e baixador de vídeos`, template: `%s · ${SITE_NAME}` },
  description: "Utilitários online em português: converta documentos, imagens, áudio e vídeo, remova fundos e objetos de fotos e baixe vídeos públicos.",
  openGraph: { siteName: SITE_NAME, locale: "pt_BR", type: "website" },
};

const LEGAL = [
  { href: "/termos", label: "Termos de uso" },
  { href: "/privacidade", label: "Privacidade" },
  { href: "/reembolso", label: "Reembolso" },
  { href: "/cookies", label: "Cookies" },
  { href: "/direitos-de-conteudo", label: "Direitos de conteúdo" },
  { href: "/contato", label: "Contato e suporte" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <a href="#conteudo" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded focus:bg-white focus:px-3 focus:py-2">
          Pular para o conteúdo
        </a>
        <SiteHeader />
        <main id="conteudo" className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
          {children}
        </main>
        <footer className="border-t border-slate-200 bg-white py-8 text-sm text-slate-600">
          <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 sm:flex-row sm:justify-between">
            <p>© {SITE_NAME}. Utilitários online.</p>
            <nav aria-label="Links legais">
              <ul className="flex flex-wrap gap-x-4 gap-y-2">
                {LEGAL.map((l) => (
                  <li key={l.href}><Link href={l.href} className="hover:underline">{l.label}</Link></li>
                ))}
              </ul>
            </nav>
          </div>
        </footer>
        <ConsentBanner />
      </body>
    </html>
  );
}
