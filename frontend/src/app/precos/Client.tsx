"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, Button, Card } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import { useMe } from "@/lib/useMe";

type Catalog = {
  plans: { code: string; name: string; kind: string; price_cents: number; credits_per_cycle: number | null }[];
  packages: { code: string; tool_id: string; tool_name: string; credits: number; price_cents: number; validity_days: number }[];
  lifetime_seats_left: number;
};

export default function PricingPage() {
  const { me } = useMe();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    api<Catalog>("/catalog").then(setCatalog).catch(() => setError("Não foi possível carregar os preços."));
  }, []);

  async function buy(product: string, mode: "manual" | "card_auto" = "manual") {
    setError(null);
    setBusy(`${product}-${mode}`);
    try {
      // Only the product is sent. The price is decided by the backend.
      const { redirect_url } = await api<{ redirect_url: string }>("/checkout", { method: "POST", body: { product, mode } });
      window.location.assign(redirect_url); // Mercado Pago hosted checkout (card data never touches our site)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao iniciar o pagamento.");
      setBusy(null);
    }
  }

  if (!catalog) return error ? <Alert kind="error">{error}</Alert> : <p>Carregando…</p>;
  const plans = catalog.plans.filter((p) => p.kind === "recurring");
  const lifetime = catalog.plans.find((p) => p.kind === "lifetime");
  const loginFirst = me === null;

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">Planos e fichas</h1>
        <p className="max-w-2xl text-slate-700">
          Cada uso de ferramenta consome fichas. Conta gratuita: 5 fichas por dia. Pagamento pelo Mercado Pago (Pix,
          cartão de crédito ou débito). As fichas só são liberadas depois que o Mercado Pago confirma o pagamento.
        </p>
      </header>

      {error && <Alert kind="error">{error}</Alert>}
      {loginFirst && (
        <Alert kind="info">
          <Link href="/entrar" className="font-semibold underline">Entre</Link> ou{" "}
          <Link href="/cadastrar" className="font-semibold underline">crie sua conta</Link> para comprar.
        </Alert>
      )}

      <section aria-labelledby="planos" className="grid gap-4 md:grid-cols-3">
        <h2 id="planos" className="sr-only">Planos</h2>
        {plans.map((plan) => (
          <Card key={plan.code} title={plan.name}>
            <p className="text-2xl font-bold">{formatBRL(plan.price_cents)}<span className="text-sm font-normal"> / mês</span></p>
            <p className="mb-4 text-sm text-slate-700">{plan.credits_per_cycle} fichas por ciclo, em qualquer ferramenta.</p>
            <div className="flex flex-col gap-2">
              <Button type="button" disabled={loginFirst || busy !== null} onClick={() => buy(`plan:${plan.code}`, "card_auto")}>
                Assinar no cartão (renova sozinho)
              </Button>
              <Button type="button" variant="secondary" disabled={loginFirst || busy !== null} onClick={() => buy(`plan:${plan.code}`)}>
                Pagar 1 mês (Pix ou débito)
              </Button>
              <p className="text-xs text-slate-600">No Pix e no débito a renovação é manual; avisamos por e-mail antes do vencimento.</p>
            </div>
          </Card>
        ))}
        {lifetime && (
          <Card title="Vitalício">
            <p className="text-2xl font-bold">{formatBRL(lifetime.price_cents)}<span className="text-sm font-normal"> pagamento único</span></p>
            <p className="mb-4 text-sm text-slate-700">
              Uso sem contagem de fichas, com limites de uso justo (2 processamentos simultâneos e 50 por dia, revisáveis a
              cada 6 meses). {catalog.lifetime_seats_left > 0 ? `${catalog.lifetime_seats_left} vagas restantes.` : "Vagas esgotadas."}
            </p>
            <Button type="button" disabled={loginFirst || busy !== null || catalog.lifetime_seats_left <= 0} onClick={() => buy("lifetime")}>
              Comprar vitalício
            </Button>
          </Card>
        )}
      </section>

      <section aria-labelledby="avulsas" className="flex flex-col gap-3">
        <h2 id="avulsas" className="text-xl font-semibold">Fichas avulsas</h2>
        <p className="text-sm text-slate-700">Pacotes de 10 fichas, válidos só na ferramenta comprada, por 90 dias.</p>
        <ul className="grid gap-3 sm:grid-cols-2">
          {catalog.packages.map((pack) => (
            <li key={pack.code} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-4">
              <div>
                <p className="font-medium">{pack.tool_name}</p>
                <p className="text-sm text-slate-600">{pack.credits} fichas · {formatBRL(pack.price_cents)}</p>
              </div>
              <Button type="button" variant="secondary" disabled={loginFirst || busy !== null} onClick={() => buy(`package:${pack.code}`)}>
                Comprar
              </Button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
