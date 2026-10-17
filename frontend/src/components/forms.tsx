"use client";

import { type FormEvent, useState } from "react";
import { ApiError } from "@/lib/api";

/** Shared submit/loading/error handling for the auth forms. */
export function useSubmit<T>(action: (form: FormData) => Promise<T>) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<T | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      setResult(await action(new FormData(event.currentTarget)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Algo deu errado. Tente novamente.");
    } finally {
      setPending(false);
    }
  }

  return { onSubmit, pending, error, result };
}
