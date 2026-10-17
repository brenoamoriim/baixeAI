"use client";

import Link from "next/link";
import { useSubmit } from "@/components/forms";
import { Alert, Button, Card, TextField } from "@/components/ui";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const { onSubmit, pending, error, result } = useSubmit(async (form) => {
    const body = await api<{ message: string }>("/auth/register", {
      method: "POST",
      body: { email: form.get("email"), password: form.get("password") },
    });
    return body.message;
  });

  return (
    <div className="mx-auto max-w-md">
      <Card title="Criar conta grátis">
        {result ? (
          <Alert kind="success">
            {result} Abra o link do e-mail para ativar suas 5 fichas diárias.
          </Alert>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
            {error && <Alert kind="error">{error}</Alert>}
            <TextField label="E-mail" id="email" name="email" type="email" autoComplete="email" required />
            <TextField
              label="Senha"
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              minLength={10}
              hint="Mínimo de 10 caracteres."
              required
            />
            <Button type="submit" disabled={pending}>
              {pending ? "Criando…" : "Criar conta"}
            </Button>
          </form>
        )}
        <p className="mt-4 text-sm">
          Já tem conta?{" "}
          <Link href="/entrar" className="text-blue-700 hover:underline">
            Entrar
          </Link>
        </p>
      </Card>
    </div>
  );
}
