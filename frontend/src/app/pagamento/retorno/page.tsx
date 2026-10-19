"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Alert, Card } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

type Status = { id: string; purpose: string; status: string; fulfilled: boolean };

const MAX_TRIES = 60; // ~2 min of polling; afterwards the user can come back later

/** Return page after Mercado Pago. It NEVER grants anything: it only shows what our backend recorded
 * from the verified webhook (or reconciliation). */
function ReturnStatus() {
  const ref = useSearchParams().get("ref") ?? "";
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    if (!ref) return;
    let active = true;
    (async () => {
      for (let i = 0; i < MAX_TRIES && active; i++) {
        try {
          const current = await api<Status>(`/payments/${ref}`);
          if (!active) return;
          setStatus(current);
          if (current.fulfilled || ["rejected", "cancelled", "expired", "refunded", "canceled"].includes(current.status)) return;
        } catch (err) {
          if (active) setError(err instanceof ApiError ? err.message : "Não foi possível consultar o pagamento.");
          return;
        }
        await new Promise((r) => setTimeout(r, 2000));
      }
      if (active) setGaveUp(true);
    })();
    return () => {
      active = false;
    };
  }, [ref]);

  if (!ref) return <Alert kind="error">Referência de pagamento ausente.</Alert>;
  if (error) return <Alert kind="error">{error}</Alert>;
  if (!status) return <p>Consultando o pagamento…</p>;
  if (status.fulfilled)
    return (
      <Alert kind="success">
        Pagamento confirmado! <Link href="/painel" className="font-semibold underline">Ver minhas fichas</Link>
      </Alert>
    );
  if (["rejected", "cancelled", "expired", "canceled"].includes(status.status))
    return <Alert kind="error">O pagamento não foi concluído. Nenhum valor foi cobrado por nós.</Alert>;
  return (
    <Alert kind="info">
      Aguardando a confirmação do Mercado Pago{gaveUp ? ". Pode levar alguns minutos (Pix costuma ser imediato)" : "…"}.
      Você pode fechar esta página: as fichas aparecem no painel assim que o pagamento for confirmado.
    </Alert>
  );
}

export default function PaymentReturnPage() {
  return (
    <div className="mx-auto max-w-lg">
      <Card title="Pagamento" heading="h1">
        <Suspense fallback={<p>Carregando…</p>}>
          <ReturnStatus />
        </Suspense>
      </Card>
    </div>
  );
}
