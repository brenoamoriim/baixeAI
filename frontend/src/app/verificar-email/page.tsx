"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { Alert, Card } from "@/components/ui";
import { api, ApiError } from "@/lib/api";

function Verify() {
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<"pending" | "ok" | string>("pending");
  const sent = useRef(false);

  useEffect(() => {
    if (!token || sent.current) return;
    sent.current = true; // tokens are single-use: never submit twice (e.g. StrictMode)
    api("/auth/verify-email", { method: "POST", body: { token } })
      .then(() => setState("ok"))
      .catch((err) => setState(err instanceof ApiError ? err.message : "Não foi possível confirmar."));
  }, [token]);

  if (!token) return <Alert kind="error">Link inválido.</Alert>;
  if (state === "pending") return <p>Confirmando seu e-mail…</p>;
  if (state === "ok")
    return (
      <Alert kind="success">
        E-mail confirmado! Suas fichas diárias estão liberadas.{" "}
        <Link href="/painel" className="font-semibold underline">
          Ir para o painel
        </Link>
      </Alert>
    );
  return <Alert kind="error">{state}</Alert>;
}

export default function VerifyEmailPage() {
  return (
    <div className="mx-auto max-w-md">
      <Card title="Confirmação de e-mail">
        <Suspense fallback={<p>Carregando…</p>}>
          <Verify />
        </Suspense>
      </Card>
    </div>
  );
}
