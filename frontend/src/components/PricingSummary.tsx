"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatBRL } from "@/lib/format";

type Catalog = {
  plans: { code: string; name: string; kind: string; price_cents: number; credits_per_cycle: number | null }[];
  packages: { price_cents: number }[];
};

/** Prices come from the backend catalog (editable by admins), never hard-coded in the page. */
export function PricingSummary() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  useEffect(() => {
    let active = true;
    api<Catalog>("/catalog").then((c) => active && setCatalog(c)).catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);
  if (!catalog) return <p className="text-slate-700">Conta gratuita com 5 fichas por dia, planos mensais, vitalício e fichas avulsas.</p>;
  const parts = ["Gratuita: 5 fichas por dia"];
  for (const p of catalog.plans) {
    if (p.kind === "recurring") parts.push(`${p.name}: ${formatBRL(p.price_cents)}/mês (${p.credits_per_cycle} fichas)`);
    if (p.kind === "lifetime") parts.push(`${p.name}: ${formatBRL(p.price_cents)} (pagamento único, com uso justo)`);
  }
  const cheapest = Math.min(...catalog.packages.map((p) => p.price_cents));
  if (Number.isFinite(cheapest)) parts.push(`fichas avulsas a partir de ${formatBRL(cheapest)}`);
  return <p className="text-slate-700">{parts.join(" · ")}.</p>;
}
