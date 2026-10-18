"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Tool } from "@/lib/api";
import { pluralFichas } from "@/lib/format";
import { Alert, Badge } from "./ui";

const TOOL_PAGES: Record<string, { href: string; label: string }> = {
  converter: { href: "/conversores", label: "Abrir conversores" },
  echo: { href: "/ferramentas/eco", label: "Abrir ferramenta de teste" },
};

/** Tools come from the backend registry: only `available` capabilities are usable. */
export function ToolCatalog() {
  const [tools, setTools] = useState<Tool[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<{ tools: Tool[] }>("/tools")
      .then((data) => setTools(data.tools))
      .catch(() => setError(true));
  }, []);

  if (error) return <Alert kind="error">Não foi possível carregar as ferramentas agora.</Alert>;
  if (!tools) return <p className="text-slate-600">Carregando ferramentas…</p>;

  return (
    <section aria-labelledby="ferramentas">
      <h2 id="ferramentas" className="mb-4 text-xl font-semibold">
        Ferramentas
      </h2>
      <ul className="grid gap-4 sm:grid-cols-2">
        {tools.map((tool) => (
          <li key={tool.id} className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between gap-2">
              <h3 className="font-semibold text-slate-900">{tool.name}</h3>
              {tool.status === "available" ? <Badge tone="ok">Disponível</Badge> : <Badge tone="soon">Em breve</Badge>}
            </div>
            {tool.status === "available" ? (
              <>
                <p className="text-sm text-slate-600">A partir de {pluralFichas(tool.base_cost)} por uso.</p>
                {TOOL_PAGES[tool.id] && (
                  <Link href={TOOL_PAGES[tool.id].href} className="text-sm font-medium text-blue-700 hover:underline">
                    {TOOL_PAGES[tool.id].label}
                  </Link>
                )}
              </>
            ) : (
              <p className="text-sm text-slate-600">Esta ferramenta ainda está em desenvolvimento.</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
