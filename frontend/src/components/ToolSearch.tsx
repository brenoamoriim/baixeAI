"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { searchTools } from "@/lib/toolSearch";

/** Universal search: type a format or a task ("pdf para word", "heic", "fundo") and jump to the tool. */
export function ToolSearch() {
  const [query, setQuery] = useState("");
  const results = useMemo(() => searchTools(query), [query]);
  return (
    <div className="flex max-w-xl flex-col gap-2">
      <label htmlFor="busca-ferramenta" className="text-sm font-medium text-slate-800">
        O que você quer fazer?
      </label>
      <input
        id="busca-ferramenta"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Ex.: pdf para word, heic, tirar fundo, mp3"
        className="rounded-md border border-slate-300 bg-white px-4 py-3 text-base"
        aria-describedby="busca-resultados"
      />
      <ul id="busca-resultados" aria-live="polite" className="flex flex-col gap-1">
        {query.trim() &&
          (results.length ? (
            results.map((r) => (
              <li key={r.href}>
                <Link href={r.href} className="block rounded-md bg-white px-4 py-2 text-blue-800 hover:bg-blue-50">
                  {r.title}
                </Link>
              </li>
            ))
          ) : (
            <li className="px-1 text-sm text-slate-600">Nenhuma ferramenta encontrada para “{query}”.</li>
          ))}
      </ul>
    </div>
  );
}
