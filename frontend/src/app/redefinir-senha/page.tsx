"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useSubmit } from "@/components/forms";
import { Alert, Button, Card, TextField } from "@/components/ui";
import { api } from "@/lib/api";

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const { onSubmit, pending, error, result } = useSubmit(async (form) => {
    const body = await api<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: { token, password: form.get("password") },
    });
    return body.message;
  });

  if (!token) return <Alert kind="error">Link inválido. Peça um novo em “Esqueci minha senha”.</Alert>;
  if (result)
    return (
      <Alert kind="success">
        {result}{" "}
        <Link href="/entrar" className="font-semibold underline">
          Entrar
        </Link>
      </Alert>
    );
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {error && <Alert kind="error">{error}</Alert>}
      <TextField
        label="Nova senha"
        id="password"
        name="password"
        type="password"
        autoComplete="new-password"
        minLength={10}
        hint="Mínimo de 10 caracteres. Você sairá de todos os dispositivos."
        required
      />
      <Button type="submit" disabled={pending}>
        {pending ? "Salvando…" : "Salvar nova senha"}
      </Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="mx-auto max-w-md">
      <Card title="Criar nova senha">
        <Suspense fallback={<p>Carregando…</p>}>
          <ResetForm />
        </Suspense>
      </Card>
    </div>
  );
}
