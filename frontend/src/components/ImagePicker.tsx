"use client";

import { type DragEvent, useRef, useState } from "react";
import { Button } from "./ui";

/** Drag-and-drop or button file picker for images (JPG/PNG/WEBP). */
export function ImagePicker({ onFile, busy }: { onFile: (file: File) => void; busy: boolean }) {
  const ref = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) onFile(file);
  }

  return (
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
      <p className="text-slate-700">Arraste uma imagem (JPG, PNG ou WEBP, até 20 MB) ou</p>
      <Button type="button" variant="secondary" onClick={() => ref.current?.click()} disabled={busy}>
        {busy ? "Enviando e analisando…" : "Escolher imagem"}
      </Button>
      <input
        ref={ref}
        type="file"
        accept=".jpg,.jpeg,.png,.webp"
        className="sr-only"
        aria-label="Escolher imagem"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}
