import type { Metadata } from "next";
import Link from "next/link";
import { AdSlot } from "@/components/AdSlot";
import { PricingSummary } from "@/components/PricingSummary";
import { ToolSearch } from "@/components/ToolSearch";

export const metadata: Metadata = { alternates: { canonical: "/" } };

const CATEGORIES = [
  { href: "/conversores", title: "Documentos", text: "Word, PDF, ODT, RTF, planilhas e CSV." },
  { href: "/conversores", title: "Imagens", text: "JPG, PNG, WEBP, AVIF, HEIC, GIF, TIFF, ICO." },
  { href: "/conversores", title: "Áudio e vídeo", text: "MP3, WAV, OPUS, FLAC, MP4, WEBM, MKV, GIF." },
  { href: "/removedor-de-fundo", title: "Edição com IA", text: "Remover fundo e remover objetos de fotos." },
];

const FEATURED = [
  { href: "/conversores", title: "Conversores", text: "Conversões testadas com arquivos reais." },
  { href: "/removedor-de-fundo", title: "Removedor de fundo", text: "PNG transparente ou cor sólida." },
  { href: "/remover-objeto", title: "Removedor de objetos", text: "Pinte e a IA preenche a área." },
  { href: "/baixar-videos", title: "Baixador de vídeos", text: "Vídeos públicos em MP4 ou só o áudio." },
];

const FAQ = [
  { q: "É grátis?", a: "Visitantes têm 1 ficha para experimentar. Com a conta gratuita você recebe 5 fichas por dia, renovadas à meia-noite." },
  { q: "O que é uma ficha?", a: "É a unidade de uso: cada processamento concluído consome fichas (normalmente 1; vídeos podem custar 2)." },
  { q: "Meus arquivos ficam salvos?", a: "Não. Arquivos e resultados são apagados automaticamente em poucas horas e só você baixa o resultado." },
  { q: "Como pago?", a: "Pelo Mercado Pago, com Pix, cartão de crédito ou débito. As fichas são liberadas após a confirmação do pagamento." },
];

export default function HomePage() {
  return (
    <div className="flex flex-col gap-12">
      <section className="flex flex-col gap-4 py-6">
        <h1 className="text-3xl font-bold text-slate-900 sm:text-4xl">Utilitários online, sem complicação</h1>
        <p className="max-w-2xl text-lg text-slate-700">
          Converta arquivos, remova fundos e objetos de fotos e baixe vídeos públicos — tudo no navegador.
        </p>
        <ToolSearch />
      </section>

      <section aria-labelledby="categorias">
        <h2 id="categorias" className="mb-4 text-xl font-semibold">Categorias</h2>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {CATEGORIES.map((c) => (
            <li key={c.title}>
              <Link href={c.href} className="block h-full rounded-lg border border-slate-200 bg-white p-4 hover:border-blue-400">
                <span className="font-semibold text-slate-900">{c.title}</span>
                <span className="mt-1 block text-sm text-slate-600">{c.text}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="destaques">
        <h2 id="destaques" className="mb-4 text-xl font-semibold">Ferramentas</h2>
        <ul className="grid gap-3 sm:grid-cols-2">
          {FEATURED.map((t) => (
            <li key={t.href}>
              <Link href={t.href} className="block rounded-lg border border-slate-200 bg-white p-5 hover:border-blue-400">
                <span className="text-lg font-semibold text-blue-800">{t.title}</span>
                <span className="mt-1 block text-slate-700">{t.text}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="precos-resumo" className="rounded-lg border border-slate-200 bg-white p-6">
        <h2 id="precos-resumo" className="mb-2 text-xl font-semibold">Planos</h2>
        <PricingSummary />
        <Link href="/precos" className="mt-3 inline-block font-semibold text-blue-700 hover:underline">Ver preços e detalhes</Link>
      </section>

      <section aria-labelledby="faq" className="flex flex-col gap-3">
        <h2 id="faq" className="text-xl font-semibold">Perguntas frequentes</h2>
        {FAQ.map((f) => (
          <details key={f.q} className="rounded-md border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer font-medium">{f.q}</summary>
            <p className="mt-2 text-slate-700">{f.a}</p>
          </details>
        ))}
      </section>

      <AdSlot slot="home_bottom" />
    </div>
  );
}
