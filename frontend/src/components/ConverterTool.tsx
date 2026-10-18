"use client";

import { type DragEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, type Tool, type Upload, uploadFile } from "@/lib/api";
import {
  CATEGORY_LABEL,
  formatBytes,
  formatDuration,
  formatLabel,
  OPTION_DEFAULT,
  optionName,
  optionValueLabel,
  outputsFor,
  relevantOptions,
} from "@/lib/converter";
import { ToolRunner } from "./ToolRunner";
import { Alert, Button } from "./ui";

const PROBE_POLL_MS = 1000;
const PROBE_MAX_TRIES = 90;

export function ConverterTool({ tool }: { tool: Tool }) {
  const [upload, setUpload] = useState<Upload | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [output, setOutput] = useState<string>("");
  const [options, setOptions] = useState<Record<string, string>>({});
  const [cost, setCost] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = useMemo(
    () => [...new Set(tool.capabilities.map((c) => c.input))].map((f) => (f === "jpg" ? ".jpg,.jpeg" : `.${f}`)).join(","),
    [tool.capabilities],
  );
  const outputs = upload?.status === "ready" ? outputsFor(tool.capabilities, upload.format) : [];
  const capability = outputs.find((c) => c.output === output) ?? null;
  const optionSets = capability ? (tool.info?.options?.[capability.category] ?? {}) : {};
  const shownOptions = capability ? relevantOptions(capability.category, capability.output, optionSets) : [];

  async function handleFile(file: File) {
    setError(null);
    setUpload(null);
    setOutput("");
    setOptions({});
    setCost(null);
    setUploading(true);
    try {
      let current = await uploadFile(file);
      for (let i = 0; current.status === "probing" && i < PROBE_MAX_TRIES; i++) {
        setUpload(current);
        await new Promise((resolve) => setTimeout(resolve, PROBE_POLL_MS));
        current = await api<Upload>(`/uploads/${current.id}`);
      }
      setUpload(current);
      if (current.status === "rejected") setError(current.error_message ?? "Arquivo recusado.");
      else if (current.status === "probing") setError("A análise do arquivo está demorando. Tente novamente em instantes.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha no envio. Verifique sua conexão.");
    } finally {
      setUploading(false);
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void handleFile(file);
  }

  // Exact price from the backend whenever the selection changes (the backend charges this value).
  useEffect(() => {
    if (!upload || !capability) return;
    let active = true;
    api<{ cost: number }>("/jobs/estimate", {
      method: "POST",
      body: { tool_id: "converter", input_format: upload.format, output_format: capability.output,
              options: { upload_id: upload.id, ...options } },
    })
      .then((r) => active && setCost(r.cost))
      .catch((err) => active && setError(err instanceof ApiError ? err.message : "Não foi possível calcular o custo."));
    return () => {
      active = false;
    };
  }, [upload, capability, options]);

  const limits = tool.info?.limits_bytes;

  return (
    <div className="flex flex-col gap-5">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex flex-col items-center gap-3 rounded-lg border-2 border-dashed p-8 text-center ${
          dragging ? "border-blue-600 bg-blue-50" : "border-slate-300 bg-white"
        }`}
      >
        <p className="text-slate-700">Arraste um arquivo para cá ou</p>
        <Button type="button" variant="secondary" onClick={() => inputRef.current?.click()} disabled={uploading}>
          {uploading ? "Enviando e analisando…" : "Escolher arquivo"}
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="sr-only"
          aria-label="Escolher arquivo para converter"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleFile(file);
            e.target.value = "";
          }}
        />
        {limits && (
          <p className="text-xs text-slate-600">
            Limites: documentos {formatBytes(limits.document)}, imagens {formatBytes(limits.image)}, áudio{" "}
            {formatBytes(limits.audio)}, vídeo {formatBytes(limits.video)}
            {tool.info?.video_max_seconds ? ` e ${formatDuration(tool.info.video_max_seconds)} min` : ""}. Arquivos são
            apagados automaticamente após algumas horas.
          </p>
        )}
      </div>

      {error && <Alert kind="error">{error}</Alert>}

      {upload?.status === "ready" && (
        <section aria-label="Arquivo analisado" className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-800">
            <strong>{upload.original_name}</strong> — {formatLabel(upload.format)} ({CATEGORY_LABEL[upload.category]},{" "}
            {formatBytes(upload.size_bytes)}
            {upload.info.width ? `, ${upload.info.width}×${upload.info.height}` : ""}
            {upload.info.pages ? `, ${upload.info.pages} página(s)` : ""}
            {upload.info.duration_seconds ? `, ${formatDuration(upload.info.duration_seconds)}` : ""})
          </p>

          {outputs.length === 0 ? (
            <Alert kind="info">Ainda não há conversões disponíveis para este formato.</Alert>
          ) : (
            <div className="flex flex-col gap-1">
              <label htmlFor="saida" className="text-sm font-medium">
                Converter para
              </label>
              <select
                id="saida"
                value={output}
                onChange={(e) => {
                  setOutput(e.target.value);
                  setOptions({});
                  setCost(null);
                  setError(null);
                }}
                className="rounded-md border border-slate-300 bg-white px-3 py-2"
              >
                <option value="">Escolha o formato de saída</option>
                {outputs.map((c) => (
                  <option key={c.output} value={c.output}>
                    {c.category === "video" && ["mp3", "m4a", "wav", "ogg", "opus", "flac"].includes(c.output)
                      ? `${formatLabel(c.output)} (extrair áudio)`
                      : c.output === upload.format
                        ? `${formatLabel(c.output)} (recodificar)`
                        : formatLabel(c.output)}
                  </option>
                ))}
              </select>
            </div>
          )}

          {capability?.note && <Alert kind="info">{capability.note}</Alert>}

          {shownOptions.length > 0 && (
            <fieldset className="grid gap-3 sm:grid-cols-2">
              <legend className="mb-2 text-sm font-medium">Opções</legend>
              {shownOptions.map((key) => (
                <div key={key} className="flex flex-col gap-1">
                  <label htmlFor={`opt-${key}`} className="text-sm">
                    {optionName(key)}
                  </label>
                  <select
                    id={`opt-${key}`}
                    value={options[key] ?? OPTION_DEFAULT[key]}
                    onChange={(e) => setOptions((prev) => ({ ...prev, [key]: e.target.value }))}
                    className="rounded-md border border-slate-300 bg-white px-3 py-2"
                  >
                    {optionSets[key].map((value) => (
                      <option key={value} value={value}>
                        {optionValueLabel(key, value)}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </fieldset>
          )}

          {capability && cost !== null && (
            <ToolRunner
              key={`${upload.id}-${capability.output}`}
              toolId="converter"
              inputFormat={upload.format}
              outputFormat={capability.output}
              displayCost={cost}
              buildOptions={() => ({ upload_id: upload.id, ...options })}
            >
              {null}
            </ToolRunner>
          )}
        </section>
      )}
    </div>
  );
}
