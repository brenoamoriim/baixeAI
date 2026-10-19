"use client";

import { useEffect, useRef, useState } from "react";
import { BeforeAfter } from "@/components/BeforeAfter";
import { ImagePicker } from "@/components/ImagePicker";
import { MaskEditor, type MaskEditorHandle } from "@/components/MaskEditor";
import { Alert, Button, Card } from "@/components/ui";
import { api, ApiError, type Job, newIdempotencyKey, type Tool, uploadFile } from "@/lib/api";
import { jobStatusLabel, pluralFichas, refundNote } from "@/lib/format";
import { useEstimate } from "@/lib/useEstimate";
import { resultPreviewUrl, useUpload } from "@/lib/useUpload";

const EXPAND_LABEL: Record<string, string> = { "0": "Exata", "8": "Pequena (recomendado)", "16": "Média", "32": "Grande" };

export default function ObjectRemoverPage() {
  const [tool, setTool] = useState<Tool | null | undefined>(undefined);
  const { upload, busy, error, send } = useUpload();
  const [original, setOriginal] = useState<string | null>(null);
  const [hasMask, setHasMask] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [expand, setExpand] = useState("8");
  const [output, setOutput] = useState("png");
  const [running, setRunning] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const editor = useRef<MaskEditorHandle>(null);
  const keyRef = useRef<string | null>(null);

  useEffect(() => {
    api<{ tools: Tool[] }>("/tools")
      .then((d) => setTool(d.tools.find((t) => t.id === "object_remover" && t.status === "available") ?? null))
      .catch(() => setTool(null));
  }, []);

  const ready = upload?.status === "ready";
  const outputs = tool && ready ? tool.capabilities.filter((c) => c.input === upload.format).map((c) => c.output) : [];
  const { cost } = useEstimate("object_remover", ready ? upload.format : null, outputs.includes(output) ? output : null,
                               ready ? { upload_id: upload.id } : null);

  async function onFile(file: File) {
    setPreview(null);
    setJob(null);
    setHasMask(false);
    setOriginal(URL.createObjectURL(file));
    const up = await send(file);
    if (up) setOutput(up.format === "jpg" ? "jpg" : "png");
  }

  async function run() {
    if (!upload || !editor.current?.hasMask()) return;
    setRunning(true);
    setRunError(null);
    setPreview(null);
    try {
      keyRef.current ??= newIdempotencyKey();
      const maskFile = new File([await editor.current.maskBlob()], "mascara.png", { type: "image/png" });
      let mask = await uploadFile(maskFile);
      for (let i = 0; mask.status === "probing" && i < 60; i++) {
        await new Promise((r) => setTimeout(r, 1000));
        mask = await api(`/uploads/${mask.id}`);
      }
      if (mask.status !== "ready") throw new ApiError(400, "invalid_mask", mask.error_message ?? "Máscara inválida.");
      let current = await api<Job>("/jobs", {
        method: "POST",
        headers: { "Idempotency-Key": keyRef.current },
        body: {
          tool_id: "object_remover", input_format: upload.format, output_format: output,
          options: { upload_id: upload.id, mask_upload_id: mask.id, accept_rights: accepted, mask_expand: expand },
        },
      });
      keyRef.current = null;
      setJob(current);
      while (current.status === "queued" || current.status === "processing") {
        await new Promise((r) => setTimeout(r, 1000));
        current = await api<Job>(`/jobs/${current.id}`);
        setJob(current);
      }
      if (current.status === "completed") setPreview(await resultPreviewUrl(current.id));
    } catch (err) {
      if (err instanceof ApiError && err.status < 500) keyRef.current = null;
      setRunError(err instanceof ApiError ? err.message : "Falha de conexão. Tente novamente.");
    } finally {
      setRunning(false);
    }
  }

  async function download() {
    if (!job) return;
    const { url } = await api<{ url: string }>(`/jobs/${job.id}/download-link`, { method: "POST" });
    window.location.assign(url);
  }

  if (tool === undefined) return <p>Carregando…</p>;
  if (tool === null) return <Alert kind="info">O removedor de objetos está indisponível no momento.</Alert>;

  const note = job?.status === "failed" ? refundNote(job.error_class) : null;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">Removedor de objetos</h1>
        <p className="max-w-2xl text-slate-700">
          Pinte o que você quer tirar da foto (uma pessoa ao fundo, um fio, uma mancha) e a IA preenche a área. O
          resultado depende da imagem e não é perfeito em todos os casos. Use apenas em imagens suas ou que você tem
          autorização para editar.
        </p>
      </header>

      <ImagePicker onFile={onFile} busy={busy} />
      {error && <Alert kind="error">{error}</Alert>}

      {ready && original && (
        <Card>
          <div className="flex flex-col gap-4">
            <MaskEditor key={upload.id} ref={editor} imageUrl={original} onChange={setHasMask} />

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1">
                <label htmlFor="expandir" className="text-sm font-medium">Margem ao redor da marcação</label>
                <select id="expandir" value={expand} onChange={(e) => setExpand(e.target.value)}
                        className="rounded-md border border-slate-300 bg-white px-3 py-2">
                  {Object.entries(EXPAND_LABEL).map(([v, label]) => <option key={v} value={v}>{label}</option>)}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="saida" className="text-sm font-medium">Formato do resultado</label>
                <select id="saida" value={output} onChange={(e) => setOutput(e.target.value)}
                        className="rounded-md border border-slate-300 bg-white px-3 py-2">
                  {outputs.map((o) => <option key={o} value={o}>{o.toUpperCase()}</option>)}
                </select>
              </div>
            </div>

            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} className="mt-1" />
              <span>
                Declaro que tenho direito de editar esta imagem e que não vou usar o resultado para remover autoria,
                marcas de licença ou créditos de terceiros.
              </span>
            </label>

            {cost !== null && (
              <p className="text-sm text-slate-700">
                Custo desta operação: <strong>{pluralFichas(cost)}</strong>. Falhas nossas devolvem a ficha.
              </p>
            )}
            <div>
              <Button type="button" onClick={run} disabled={running || !hasMask || !accepted || cost === null}>
                {running ? "Processando…" : cost !== null ? `Remover e usar ${pluralFichas(cost)}` : "Remover"}
              </Button>
            </div>
            {!hasMask && <p className="text-xs text-slate-600">Pinte a área a remover para continuar.</p>}
            {runError && <Alert kind="error">{runError}</Alert>}
            {job && (
              <p className="text-sm" aria-live="polite">Status: <strong>{jobStatusLabel(job.status)}</strong></p>
            )}
            {note && <Alert kind="info">{note}</Alert>}
          </div>
        </Card>
      )}

      {original && preview && (
        <Card title="Antes e depois">
          <div className="flex flex-col gap-3">
            <BeforeAfter before={original} after={preview} />
            <div>
              <Button type="button" variant="secondary" onClick={download}>Baixar resultado</Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
