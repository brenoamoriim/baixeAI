"use client";

import { useEffect, useState } from "react";
import { BeforeAfter } from "@/components/BeforeAfter";
import { ImagePicker } from "@/components/ImagePicker";
import { ToolRunner } from "@/components/ToolRunner";
import { Alert, Card } from "@/components/ui";
import { api, type Job, type Tool } from "@/lib/api";
import { useEstimate } from "@/lib/useEstimate";
import { resultPreviewUrl, useUpload } from "@/lib/useUpload";

const OUTPUT_LABEL: Record<string, string> = { png: "PNG", webp: "WEBP", jpg: "JPG (sem transparência)" };

export default function BackgroundRemoverPage() {
  const [tool, setTool] = useState<Tool | null | undefined>(undefined);
  const { upload, busy, error, send } = useUpload();
  const [original, setOriginal] = useState<string | null>(null);
  const [mode, setMode] = useState<"transparent" | "color">("transparent");
  const [color, setColor] = useState("#ffffff");
  const [output, setOutput] = useState("png");
  const [preview, setPreview] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    api<{ tools: Tool[] }>("/tools")
      .then((d) => setTool(d.tools.find((t) => t.id === "background_remover" && t.status === "available") ?? null))
      .catch(() => setTool(null));
  }, []);

  const effectiveOutput = mode === "transparent" && output === "jpg" ? "png" : output;
  const outputs = tool && upload?.status === "ready"
    ? tool.capabilities.filter((c) => c.input === upload.format).map((c) => c.output)
    : [];
  const options = upload?.status === "ready"
    ? { upload_id: upload.id, background: mode === "transparent" ? "transparent" : color }
    : null;
  const { cost, error: costError } = useEstimate("background_remover", upload?.format ?? null,
                                                 outputs.includes(effectiveOutput) ? effectiveOutput : null, options);

  async function onFile(file: File) {
    setPreview(null);
    setOriginal(URL.createObjectURL(file));
    await send(file);
  }

  async function onCompleted(job: Job) {
    try {
      setPreview(await resultPreviewUrl(job.id));
    } catch {
      setPreviewError("O resultado está pronto, mas a prévia não carregou. Use o botão de download.");
    }
  }

  if (tool === undefined) return <p>Carregando…</p>;
  if (tool === null) return <Alert kind="info">O removedor de fundo está indisponível no momento.</Alert>;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">Removedor de fundo</h1>
        <p className="max-w-2xl text-slate-700">
          Recorte automático com um modelo de IA que roda nos nossos servidores (a imagem não vai para terceiros). O
          resultado depende da foto: contornos finos, como cabelo, podem ficar imperfeitos.
        </p>
      </header>

      <ImagePicker onFile={onFile} busy={busy} />
      {error && <Alert kind="error">{error}</Alert>}

      {upload?.status === "ready" && (
        <Card>
          <div className="flex flex-col gap-4">
            <fieldset className="flex flex-col gap-2">
              <legend className="text-sm font-medium">Fundo</legend>
              <label className="flex items-center gap-2 text-sm">
                <input type="radio" name="fundo" checked={mode === "transparent"} onChange={() => setMode("transparent")} />
                Transparente
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="radio" name="fundo" checked={mode === "color"} onChange={() => setMode("color")} />
                Cor sólida
                <input
                  type="color"
                  value={color}
                  onChange={(e) => {
                    setColor(e.target.value);
                    setMode("color");
                  }}
                  aria-label="Cor do fundo"
                />
              </label>
            </fieldset>
            <div className="flex flex-col gap-1">
              <label htmlFor="formato" className="text-sm font-medium">
                Formato do resultado
              </label>
              <select id="formato" value={effectiveOutput} onChange={(e) => setOutput(e.target.value)}
                      className="max-w-xs rounded-md border border-slate-300 bg-white px-3 py-2">
                {outputs.filter((o) => mode === "color" || o !== "jpg").map((o) => (
                  <option key={o} value={o}>{OUTPUT_LABEL[o] ?? o}</option>
                ))}
              </select>
            </div>
            {costError && <Alert kind="error">{costError}</Alert>}
            {cost !== null && options && (
              <ToolRunner
                key={`${upload.id}-${effectiveOutput}-${options.background}`}
                toolId="background_remover"
                inputFormat={upload.format}
                outputFormat={effectiveOutput}
                displayCost={cost}
                buildOptions={() => options}
                onCompleted={onCompleted}
              >
                {null}
              </ToolRunner>
            )}
          </div>
        </Card>
      )}

      {previewError && <Alert kind="info">{previewError}</Alert>}
      {original && preview && (
        <Card title="Antes e depois">
          <BeforeAfter before={original} after={preview} checkerboard />
        </Card>
      )}
    </div>
  );
}
