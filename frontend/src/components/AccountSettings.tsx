"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useSubmit } from "./forms";
import { Alert, Button, Card, TextField } from "./ui";

function PasswordForm() {
  const { onSubmit, pending, error, result } = useSubmit((form) =>
    api<{ message: string }>("/me/password", {
      method: "POST",
      body: { current_password: form.get("current"), new_password: form.get("new") },
    }),
  );
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <h3 className="font-semibold">Alterar senha</h3>
      <TextField id="pw-current" name="current" type="password" label="Senha atual" required autoComplete="current-password" />
      <TextField id="pw-new" name="new" type="password" label="Nova senha" required minLength={10} autoComplete="new-password"
        hint="Mínimo de 10 caracteres." />
      {error && <Alert kind="error">{error}</Alert>}
      {result && <Alert kind="success">{result.message}</Alert>}
      <div><Button type="submit" disabled={pending}>{pending ? "Salvando…" : "Alterar senha"}</Button></div>
    </form>
  );
}

function ExportData() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function download() {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/v1/me/export", { credentials: "same-origin" });
      if (!response.ok) throw new Error();
      const url = URL.createObjectURL(await response.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = "meus-dados-baixeai.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Não foi possível exportar agora. Tente novamente mais tarde.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="flex flex-col gap-2">
      <h3 className="font-semibold">Exportar meus dados</h3>
      <p className="text-sm text-slate-700">Baixe um arquivo JSON com sua conta, fichas, processamentos e pagamentos.</p>
      {error && <Alert kind="error">{error}</Alert>}
      <div><Button type="button" variant="secondary" onClick={download} disabled={busy}>{busy ? "Gerando…" : "Exportar dados"}</Button></div>
    </div>
  );
}

function DeleteAccount() {
  const { onSubmit, pending, error, result } = useSubmit(async (form) => {
    const r = await api<{ message: string }>("/me/delete", {
      method: "POST",
      body: { password: form.get("password"), confirm: form.get("confirm") },
    });
    // Full reload on purpose (same as logout): the session cookie is gone and cached route state must reset.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.setTimeout(() => window.location.assign("/"), 2500);
    return r;
  });
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <h3 className="font-semibold text-red-800">Excluir conta</h3>
      <p className="text-sm text-slate-700">
        Seus dados pessoais são anonimizados, seus arquivos apagados e fichas e plano perdidos. Assinaturas no cartão são
        canceladas. Registros financeiros são mantidos de forma anônima, como exige a lei. Não é possível desfazer.
      </p>
      <TextField id="del-password" name="password" type="password" label="Sua senha" required autoComplete="current-password" />
      <TextField id="del-confirm" name="confirm" label='Digite EXCLUIR para confirmar' required pattern="EXCLUIR" />
      {error && <Alert kind="error">{error}</Alert>}
      {result && <Alert kind="success">{result.message}</Alert>}
      <div>
        <Button type="submit" variant="danger" disabled={pending || !!result}>
          {pending ? "Excluindo…" : "Excluir minha conta"}
        </Button>
      </div>
    </form>
  );
}

export function AccountSettings() {
  return (
    <Card title="Configurações da conta">
      <div className="flex flex-col gap-8">
        <PasswordForm />
        <ExportData />
        <DeleteAccount />
      </div>
    </Card>
  );
}
