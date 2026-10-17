"use client";

import Link from "next/link";
import { useSubmit } from "@/components/forms";
import { Alert, Button, Card, TextField } from "@/components/ui";
import { api } from "@/lib/api";

export default function LoginPage() {
  const { onSubmit, pending, error } = useSubmit(async (form) => {
    await api("/auth/login", {
      method: "POST",
      body: { email: form.get("email"), password: form.get("password") },
    });
    // Full reload on purpose: route state is preserved across navigations (cacheComponents),
    // so a client push would keep the previous user's header/session view.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/painel");
    return true;
  });

  return (
    <div className="mx-auto max-w-md">
      <Card title="Entrar">
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          {error && <Alert kind="error">{error}</Alert>}
          <TextField label="E-mail" id="email" name="email" type="email" autoComplete="email" required />
          <TextField label="Senha" id="password" name="password" type="password" autoComplete="current-password" required />
          <Button type="submit" disabled={pending}>
            {pending ? "Entrando…" : "Entrar"}
          </Button>
        </form>
        <div className="mt-4 flex justify-between text-sm">
          <Link href="/recuperar-senha" className="text-blue-700 hover:underline">
            Esqueci minha senha
          </Link>
          <Link href="/cadastrar" className="text-blue-700 hover:underline">
            Criar conta
          </Link>
        </div>
      </Card>
    </div>
  );
}
