"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "./api";

/** Exact cost from the backend (the value it will charge). Null while unknown. */
export function useEstimate(toolId: string, inputFormat: string | null, outputFormat: string | null,
                            options: Record<string, unknown> | null) {
  const [cost, setCost] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = JSON.stringify([toolId, inputFormat, outputFormat, options]);

  useEffect(() => {
    if (!inputFormat || !outputFormat || !options) return;
    let active = true;
    api<{ cost: number }>("/jobs/estimate", {
      method: "POST",
      body: { tool_id: toolId, input_format: inputFormat, output_format: outputFormat, options },
    })
      .then((r) => {
        if (active) {
          setCost(r.cost);
          setError(null);
        }
      })
      .catch((err) => active && setError(err instanceof ApiError ? err.message : "Não foi possível calcular o custo."));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` captures all inputs
  }, [key]);

  return { cost, error };
}
