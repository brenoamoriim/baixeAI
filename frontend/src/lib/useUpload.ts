"use client";

import { useState } from "react";
import { api, ApiError, type Upload, uploadFile } from "./api";

const POLL_MS = 1000;
const MAX_TRIES = 90;

/** Upload a file and wait for the server-side inspection (done before any credit is charged). */
export function useUpload() {
  const [upload, setUpload] = useState<Upload | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(file: File): Promise<Upload | null> {
    setBusy(true);
    setError(null);
    setUpload(null);
    try {
      let current = await uploadFile(file);
      for (let i = 0; current.status === "probing" && i < MAX_TRIES; i++) {
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
        current = await api<Upload>(`/uploads/${current.id}`);
      }
      setUpload(current);
      if (current.status === "rejected") {
        setError(current.error_message ?? "Arquivo recusado.");
        return null;
      }
      if (current.status === "probing") {
        setError("A análise do arquivo está demorando. Tente novamente em instantes.");
        return null;
      }
      return current;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha no envio. Verifique sua conexão.");
      return null;
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setUpload(null);
    setError(null);
  }

  return { upload, busy, error, send, reset };
}

/** Fetch a finished job's file as a blob URL for on-page preview (same signed link + owner check). */
export async function resultPreviewUrl(jobId: string): Promise<string> {
  const { url } = await api<{ url: string }>(`/jobs/${jobId}/download-link`, { method: "POST" });
  const response = await fetch(url, { credentials: "same-origin" });
  if (!response.ok) throw new ApiError(response.status, "preview_failed", "Não foi possível carregar a prévia.");
  return URL.createObjectURL(await response.blob());
}
