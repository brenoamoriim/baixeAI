"use client";

import { useSubmit } from "@/components/forms";
import { Alert, Button, Card, TextField } from "@/components/ui";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const { onSubmit, pending, error, result } = useSubmit(async (form) => {
    const body = await api<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: { email: form.get("email") },
    });
    return body.message;
  });

  return (
    <div className="mx-auto max-w-md">
      <Card title="Recuperar senha" heading="h1">
        {result ? (
          <Alert kind="success">{result}</Alert>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
            {error && <Alert kind="error">{error}</Alert>}
            <TextField label="E-mail da conta" id="email" name="email" type="email" autoComplete="email" required />
            <Button type="submit" disabled={pending}>
              {pending ? "Enviando…" : "Enviar link"}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}
