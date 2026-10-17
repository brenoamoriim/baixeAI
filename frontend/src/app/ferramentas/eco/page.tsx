"use client";

import { useEffect, useState } from "react";
import { ToolRunner } from "@/components/ToolRunner";
import { Alert, Card } from "@/components/ui";
import { api, type Tool } from "@/lib/api";

/** Development-only page for the "echo" test tool. In production the API never lists it. */
export default function EchoToolPage() {
  const [tool, setTool] = useState<Tool | null | undefined>(undefined);
  const [text, setText] = useState("Olá, BaixeAI!");

  useEffect(() => {
    api<{ tools: Tool[] }>("/tools")
      .then((data) => setTool(data.tools.find((t) => t.id === "echo" && t.status === "available") ?? null))
      .catch(() => setTool(null));
  }, []);

  if (tool === undefined) return <p>Carregando…</p>;
  if (tool === null) return <Alert kind="info">Ferramenta indisponível.</Alert>;

  return (
    <div className="mx-auto max-w-xl">
      <Card title="Eco (ferramenta de teste)">
        <ToolRunner
          toolId="echo"
          inputFormat="text"
          outputFormat="txt"
          displayCost={tool.base_cost}
          buildOptions={() => (text.trim() ? { text } : null)}
        >
          <Alert kind="info">Ferramenta interna para validar fichas e processamento. Não existe em produção.</Alert>
          <label htmlFor="texto" className="text-sm font-medium">
            Texto que será devolvido como arquivo .txt
          </label>
          <textarea
            id="texto"
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={2000}
            rows={4}
            className="rounded-md border border-slate-300 bg-white p-2"
          />
        </ToolRunner>
      </Card>
    </div>
  );
}
