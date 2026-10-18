"use client";

import { type FormEvent, useEffect, useState } from "react";
import { ToolRunner } from "@/components/ToolRunner";
import { Alert, Button, Card, TextField } from "@/components/ui";
import { api, ApiError, type Tool } from "@/lib/api";
import { formatDuration } from "@/lib/converter";
import { useEstimate } from "@/lib/useEstimate";

type Inspection = {
  id: string;
  status: "probing" | "ready" | "rejected";
  domain: string;
  error_code: string | null;
  error_message: string | null;
  title: string | null;
  duration_seconds: number | null;
  heights: number[];
  has_audio: boolean | null;
  has_video: boolean | null;
};

const OUTPUT_LABEL: Record<string, string> = { mp4: "Vídeo (MP4)", m4a: "Somente áudio (M4A)", mp3: "Somente áudio (MP3)" };

export default function VideoDownloaderPage() {
  const [tool, setTool] = useState<Tool | null | undefined>(undefined);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [output, setOutput] = useState("mp4");
  const [quality, setQuality] = useState("best");
  const [accepted, setAccepted] = useState(false);

  useEffect(() => {
    api<{ tools: Tool[] }>("/tools")
      .then((d) => setTool(d.tools.find((t) => t.id === "video_downloader" && t.status === "available") ?? null))
      .catch(() => setTool(null));
  }, []);

  async function inspect(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setInspection(null);
    setAccepted(false);
    try {
      let current = await api<Inspection>("/downloads/inspect", { method: "POST", body: { url } });
      for (let i = 0; current.status === "probing" && i < 90; i++) {
        await new Promise((r) => setTimeout(r, 1000));
        current = await api<Inspection>(`/downloads/inspections/${current.id}`);
      }
      setInspection(current);
      if (current.status === "rejected") setError(current.error_message ?? "Não foi possível usar este link.");
      if (current.status === "probing") setError("A consulta está demorando. Tente novamente em instantes.");
      if (current.status === "ready") {
        setOutput(current.has_video ? "mp4" : "m4a");
        setQuality("best");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha de conexão. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  const ready = inspection?.status === "ready";
  const outputs = tool && ready
    ? tool.capabilities.map((c) => c.output).filter((o) => (o === "mp4" ? inspection.has_video : inspection.has_audio))
    : [];
  const options = ready ? { inspection_id: inspection.id, ...(output === "mp4" ? { quality } : {}) } : null;
  const { cost } = useEstimate("video_downloader", ready ? "url" : null, outputs.includes(output) ? output : null, options);

  if (tool === undefined) return <p>Carregando…</p>;
  if (tool === null) return <Alert kind="info">O baixador de vídeos está indisponível no momento.</Alert>;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">Baixador de vídeos</h1>
        <p className="max-w-2xl text-slate-700">
          Cole o link de um vídeo <strong>público</strong>. Não pedimos login, senha ou cookies de redes sociais e não
          baixamos conteúdo privado, pago ou protegido (DRM). As plataformas mudam com frequência e podem bloquear o
          acesso a partir dos nossos servidores; quando isso acontecer, a ficha é devolvida.
        </p>
      </header>

      <Card>
        <form onSubmit={inspect} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <TextField label="Link do vídeo" id="url" type="url" inputMode="url" placeholder="https://…" value={url}
                       onChange={(e) => setUrl(e.target.value)} required maxLength={2048} />
          </div>
          <Button type="submit" disabled={busy || url.trim().length < 8}>
            {busy ? "Consultando…" : "Consultar"}
          </Button>
        </form>
        <p className="mt-2 text-xs text-slate-600">A consulta é gratuita: mostramos as opções reais antes de cobrar.</p>
      </Card>

      {error && <Alert kind="error">{error}</Alert>}

      {ready && (
        <Card title={inspection.title ?? "Vídeo encontrado"}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-slate-700">
              {inspection.domain}
              {inspection.duration_seconds ? ` · ${formatDuration(inspection.duration_seconds)}` : ""}
              {inspection.heights.length ? ` · até ${Math.max(...inspection.heights)}p` : ""}
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1">
                <label htmlFor="saida" className="text-sm font-medium">Formato</label>
                <select id="saida" value={output} onChange={(e) => setOutput(e.target.value)}
                        className="rounded-md border border-slate-300 bg-white px-3 py-2">
                  {outputs.map((o) => <option key={o} value={o}>{OUTPUT_LABEL[o] ?? o}</option>)}
                </select>
              </div>
              {output === "mp4" && (
                <div className="flex flex-col gap-1">
                  <label htmlFor="qualidade" className="text-sm font-medium">Qualidade</label>
                  <select id="qualidade" value={quality} onChange={(e) => setQuality(e.target.value)}
                          className="rounded-md border border-slate-300 bg-white px-3 py-2">
                    <option value="best">Melhor disponível</option>
                    {[...inspection.heights].reverse().map((h) => <option key={h} value={String(h)}>{h}p</option>)}
                  </select>
                </div>
              )}
            </div>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} className="mt-1" />
              <span>
                Declaro que tenho direito de baixar este conteúdo (por exemplo, é meu, está em domínio público ou tenho
                autorização do titular) e assumo a responsabilidade pelo uso que fizer dele.
              </span>
            </label>
            {cost !== null && options && accepted && (
              <ToolRunner
                key={`${inspection.id}-${output}-${quality}`}
                toolId="video_downloader"
                inputFormat="url"
                outputFormat={output}
                displayCost={cost}
                buildOptions={() => ({ ...options, accept_rights: true })}
              >
                {null}
              </ToolRunner>
            )}
            {!accepted && <p className="text-xs text-slate-600">Marque a declaração acima para continuar.</p>}
          </div>
        </Card>
      )}
    </div>
  );
}
