"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BillingPanel } from "@/components/BillingPanel";
import { Alert, Card } from "@/components/ui";
import { api, ApiError, type Credits, type Job } from "@/lib/api";
import { bucketLabel, formatDate, formatDateTime, jobStatusLabel, pluralFichas, toolName } from "@/lib/format";

export default function DashboardPage() {
  const [credits, setCredits] = useState<Credits | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<"auth" | "other" | null>(null);
  const [resent, setResent] = useState(false);

  useEffect(() => {
    Promise.all([api<Credits>("/me/credits"), api<{ jobs: Job[] }>("/jobs")])
      .then(([c, j]) => {
        setCredits(c);
        setJobs(j.jobs);
      })
      .catch((err) => setError(err instanceof ApiError && err.status === 401 ? "auth" : "other"));
  }, []);

  async function resend() {
    await api("/auth/resend-verification", { method: "POST" }).catch(() => undefined);
    setResent(true);
  }

  if (error === "auth")
    return (
      <Alert kind="info">
        <Link href="/entrar" className="font-semibold underline">
          Entre na sua conta
        </Link>{" "}
        para ver seu painel.
      </Alert>
    );
  if (error) return <Alert kind="error">Não foi possível carregar o painel.</Alert>;
  if (!credits) return <p>Carregando…</p>;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Meu painel</h1>

      {!credits.email_verified && !credits.lifetime && (
        <Alert kind="info">
          Confirme seu e-mail para liberar as 5 fichas diárias.{" "}
          {resent ? (
            "Enviamos um novo link."
          ) : (
            <button type="button" onClick={resend} className="font-semibold underline">
              Reenviar link
            </button>
          )}
        </Alert>
      )}

      <Card title="Suas fichas">
        {credits.lifetime ? (
          <p>Plano Vitalício: uso sem contagem de fichas, sujeito aos limites de uso justo.</p>
        ) : credits.buckets.length === 0 ? (
          <p className="text-slate-700">Você não tem fichas disponíveis no momento.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Fichas por origem</caption>
            <thead className="text-slate-600">
              <tr>
                <th scope="col" className="py-2">Origem</th>
                <th scope="col">Disponíveis</th>
                <th scope="col">Em uso</th>
                <th scope="col">Válidas até</th>
              </tr>
            </thead>
            <tbody>
              {credits.buckets.map((b) => (
                <tr key={`${b.kind}-${b.tool_id}-${b.expires_at}`} className="border-t border-slate-100">
                  <td className="py-2">{bucketLabel(b.kind, b.tool_id)}</td>
                  <td>{b.available}</td>
                  <td>{b.reserved}</td>
                  <td>{formatDateTime(b.expires_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {credits.subscription && (
          <p className="mt-4 text-sm text-slate-700">
            Plano {credits.subscription.plan_name} — ciclo até {formatDate(credits.subscription.period_end)}
            {credits.subscription.next_plan && ` · troca agendada para ${credits.subscription.next_plan}`}
          </p>
        )}
      </Card>

      <BillingPanel />

      <Card title="Processamentos recentes">
        {jobs.length === 0 ? (
          <p className="text-slate-700">Nenhum processamento ainda.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {jobs.map((job) => (
              <li key={job.id} className="flex flex-wrap justify-between gap-2 py-2">
                <span>{toolName(job.tool_id)}</span>
                <span>{jobStatusLabel(job.status)}</span>
                <span className="text-slate-600">
                  {job.charged_from === "lifetime" ? "vitalício" : pluralFichas(job.credit_cost)}
                </span>
                <span className="text-slate-600">{job.created_at ? formatDateTime(job.created_at) : ""}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div>
        <Link
          href="/"
          className="inline-flex rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-50"
        >
          Ver ferramentas
        </Link>
      </div>
    </div>
  );
}
