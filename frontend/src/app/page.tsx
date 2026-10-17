import { ToolCatalog } from "@/components/ToolCatalog";

export default function HomePage() {
  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h1 className="text-3xl font-bold text-slate-900">Utilitários online, sem complicação</h1>
        <p className="max-w-2xl text-slate-700">
          Converta arquivos, remova fundos e objetos de imagens e baixe vídeos públicos. Visitantes têm 1
          ficha para experimentar; com a conta gratuita você recebe 5 fichas por dia.
        </p>
      </section>
      <ToolCatalog />
    </div>
  );
}
