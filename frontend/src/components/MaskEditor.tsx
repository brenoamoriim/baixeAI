"use client";

import { type PointerEvent, type Ref, useEffect, useImperativeHandle, useRef, useState } from "react";
import { drawStrokes, naturalBrush, type Stroke, toNatural } from "@/lib/mask";
import { Button } from "./ui";

export type MaskEditorHandle = { maskBlob: () => Promise<Blob>; hasMask: () => boolean };

type Props = {
  imageUrl: string;
  onChange: (hasMask: boolean) => void;
  ref?: Ref<MaskEditorHandle>;
};

const DISPLAY_MAX = 900;

/** Brush editor: paint over what should be removed. Strokes are kept in original-image pixels, so
 * the exported mask (white = remove) has exactly the image's size, as the backend requires. */
export function MaskEditor({ imageUrl, onChange, ref }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [brush, setBrush] = useState(30);
  // Dimensions as decoded by the browser (EXIF rotation applied), which is what the user sees.
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  const drawing = useRef(false);
  const naturalWidth = natural?.w ?? 1;
  const naturalHeight = natural?.h ?? 1;
  const scale = Math.min(1, DISPLAY_MAX / naturalWidth);

  useEffect(() => {
    const image = new Image();
    image.onload = () => {
      imageRef.current = image;
      setNatural({ w: image.naturalWidth, h: image.naturalHeight });
    };
    image.src = imageUrl;
  }, [imageUrl]);

  useEffect(() => {
    redraw(strokes);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- redraw once the canvas has its final size
  }, [natural]);

  function redraw(current: Stroke[]) {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || !imageRef.current) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(imageRef.current, 0, 0, canvas.width, canvas.height);
    drawStrokes(ctx, current, "rgba(220, 38, 38, 0.55)", scale);
  }

  function point(event: PointerEvent<HTMLCanvasElement>) {
    return toNatural(event.clientX, event.clientY, event.currentTarget.getBoundingClientRect(), naturalWidth, naturalHeight);
  }

  function onDown(event: PointerEvent<HTMLCanvasElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    drawing.current = true;
    const rect = event.currentTarget.getBoundingClientRect();
    const next = [...strokes, { size: naturalBrush(brush, rect.width, naturalWidth), points: [point(event)] }];
    setStrokes(next);
    redraw(next);
  }

  function onMove(event: PointerEvent<HTMLCanvasElement>) {
    if (!drawing.current) return;
    const next = strokes.slice();
    const last = next[next.length - 1];
    next[next.length - 1] = { ...last, points: [...last.points, point(event)] };
    setStrokes(next);
    redraw(next);
  }

  function onUp() {
    if (!drawing.current) return;
    drawing.current = false;
    onChange(strokes.length > 0);
  }

  function clear() {
    setStrokes([]);
    redraw([]);
    onChange(false);
  }

  function undo() {
    const next = strokes.slice(0, -1);
    setStrokes(next);
    redraw(next);
    onChange(next.length > 0);
  }

  useImperativeHandle(ref, () => ({
    hasMask: () => strokes.length > 0,
    maskBlob: () =>
      new Promise<Blob>((resolve, reject) => {
        const canvas = document.createElement("canvas");
        canvas.width = naturalWidth;
        canvas.height = naturalHeight;
        const ctx = canvas.getContext("2d");
        if (!ctx) return reject(new Error("canvas"));
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, naturalWidth, naturalHeight);
        drawStrokes(ctx, strokes, "#fff");
        canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("mask"))), "image/png");
      }),
  }));

  if (!natural) return <p className="text-sm text-slate-600">Carregando imagem…</p>;

  return (
    <div className="flex flex-col gap-3">
      <canvas
        ref={canvasRef}
        width={Math.round(naturalWidth * scale)}
        height={Math.round(naturalHeight * scale)}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerLeave={onUp}
        className="h-auto max-w-full cursor-crosshair touch-none rounded-md border border-slate-200"
        aria-label="Imagem: pinte sobre o que deseja remover"
        role="img"
      />
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          Tamanho do pincel
          <input type="range" min={5} max={120} value={brush} onChange={(e) => setBrush(Number(e.target.value))} />
        </label>
        <Button type="button" variant="secondary" onClick={undo} disabled={strokes.length === 0}>
          Desfazer
        </Button>
        <Button type="button" variant="secondary" onClick={clear} disabled={strokes.length === 0}>
          Limpar
        </Button>
      </div>
      <p className="text-xs text-slate-600">
        Edição por pincel requer mouse, toque ou caneta. Pinte com folga ao redor do objeto.
      </p>
    </div>
  );
}
