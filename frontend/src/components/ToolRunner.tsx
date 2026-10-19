"use client";

import { type ReactNode, useRef, useState } from "react";
import { api, ApiError, type Job, newIdempotencyKey } from "@/lib/api";
import { jobStatusLabel, pluralFichas, refundNote } from "@/lib/format";
import { Alert, Button } from "./ui";

type Props = {
  toolId: string;
  inputFormat: string;
  outputFormat: string;
  /** Cost shown before confirming. The backend recomputes and charges; this is display only. */
  displayCost: number;
  buildOptions: () => Record<string, unknown> | null;
  /** Called once when the job finishes successfully (e.g. to show a preview). */
  onCompleted?: (job: Job) => void;
  children: ReactNode;
};

const POLL_MS = 1000;

/** Generic tool flow: confirm cost → create job (idempotent) → poll real status → download. */
export function ToolRunner({ toolId, inputFormat, outputFormat, displayCost, buildOptions, onCompleted, children }: Props) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // One key per user intention: retries of the same click reuse it, so nothing is charged twice.
  const keyRef = useRef<string | null>(null);

  async function poll(id: string) {
    for (;;) {
      const current = await api<Job>(`/jobs/${id}`);
      setJob(current);
      if (current.status === "completed") onCompleted?.(current);
      if (current.status !== "queued" && current.status !== "processing") return;
      await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    }
  }

  async function start() {
    const options = buildOptions();
    if (!options) return;
    setBusy(true);
    setError(null);
    try {
      keyRef.current ??= newIdempotencyKey();
      const created = await api<Job>("/jobs", {
        method: "POST",
        headers: { "Idempotency-Key": keyRef.current },
        body: { tool_id: toolId, input_format: inputFormat, output_format: outputFormat, options },
      });
      setJob(created);
      keyRef.current = null; // the next click is a new intention
      await poll(created.id);
    } catch (err) {
      if (err instanceof ApiError && err.status < 500) keyRef.current = null;
      setError(err instanceof ApiError ? err.message : "Falha de conexão. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    if (!job) return;
    try {
      const { url } = await api<{ url: string }>(`/jobs/${job.id}/download-link`, { method: "POST" });
      window.location.assign(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível baixar.");
    }
  }

  const note = job?.status === "failed" ? refundNote(job.error_class) : null;

  return (
    <div className="flex flex-col gap-4">
      {children}
      <p className="text-sm text-slate-700">
        Custo desta operação: <strong>{pluralFichas(displayCost)}</strong>. A ficha só é consumida se o
        processamento começar; falhas nossas devolvem a ficha.
      </p>
      <div>
        <Button type="button" onClick={start} disabled={busy}>
          {busy ? "Processando…" : `Confirmar e usar ${pluralFichas(displayCost)}`}
        </Button>
      </div>
      {error && <Alert kind="error">{error}</Alert>}
      {job && (
        <div aria-live="polite" className="flex flex-col gap-2">
          <p className="text-sm">
            Status: <strong>{jobStatusLabel(job.status)}</strong>
          </p>
          {job.status === "processing" && (
            <progress className="w-full" max={100} value={job.progress} aria-label="Progresso" />
          )}
          {job.status === "completed" && job.has_output && (
            <div>
              <Button type="button" variant="secondary" onClick={download}>
                Baixar resultado
              </Button>
            </div>
          )}
          {note && <Alert kind="info">{note}</Alert>}
        </div>
      )}
    </div>
  );
}
