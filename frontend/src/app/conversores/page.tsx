"use client";

import { useEffect, useMemo, useState } from "react";
import { ConverterTool } from "@/components/ConverterTool";
import { Alert } from "@/components/ui";
import { api, type Tool } from "@/lib/api";
import { CATEGORY_LABEL, catalog, formatLabel } from "@/lib/converter";

const ORDER = ["document", "image", "audio", "video"];

export default function ConvertersPage() {
  const [tool, setTool] = useState<Tool | null | undefined>(undefined);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api<{ tools: Tool[] }>("/tools")
      .then((data) => setTool(data.tools.find((t) => t.id === "converter" && t.status === "available") ?? null))
      .catch(() => setTool(null));
  }, []);

  const groups = useMemo(() => (tool ? catalog(tool.capabilities, query) : {}), [tool, query]);

  if (tool === undefined) return <p>Carregando…</p>;
  if (tool === null) return <Alert kind="info">Os conversores estão indisponíveis no momento.</Alert>;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">Conversores</h1>
        <p className="max-w-2xl text-slate-700">
          Documentos, imagens, áudio e vídeo. O formato real do arquivo é detectado automaticamente e só mostramos as
          conversões testadas.
        </p>
      </header>

      <ConverterTool tool={tool} />

      <section aria-labelledby="catalogo" className="flex flex-col gap-4">
        <h2 id="catalogo" className="text-xl font-semibold">
          Formatos suportados
        </h2>
        <label htmlFor="busca" className="sr-only">
          Buscar formato
        </label>
        <input
          id="busca"
          type="search"
          placeholder="Buscar formato (ex.: pdf, heic, mp3)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="max-w-sm rounded-md border border-slate-300 bg-white px-3 py-2"
        />
        {ORDER.filter((c) => groups[c]?.length).map((category) => (
          <div key={category}>
            <h3 className="mb-2 font-semibold text-slate-900">{CATEGORY_LABEL[category]}</h3>
            <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {groups[category].map(({ input, outputs }) => (
                <li key={input} className="rounded-md border border-slate-200 bg-white p-3 text-sm">
                  <span className="font-medium">{formatLabel(input)}</span>
                  <span className="text-slate-600"> → {outputs.map(formatLabel).join(", ")}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
        {Object.keys(groups).length === 0 && <p className="text-slate-600">Nenhum formato encontrado.</p>}
      </section>
    </div>
  );
}
