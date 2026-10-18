"use client";

import { useState } from "react";

/** Before/after comparison with an accessible range slider. */
export function BeforeAfter({ before, after, checkerboard = false }: { before: string; after: string; checkerboard?: boolean }) {
  const [position, setPosition] = useState(50);
  return (
    <div className="flex flex-col gap-2">
      <div
        className="relative overflow-hidden rounded-md border border-slate-200"
        style={
          checkerboard
            ? { backgroundImage: "repeating-conic-gradient(#e2e8f0 0% 25%, #ffffff 0% 50%)", backgroundSize: "20px 20px" }
            : undefined
        }
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- local blob URLs, not optimizable */}
        <img src={after} alt="Depois" className="block h-auto w-full" />
        <div className="absolute inset-0 overflow-hidden" style={{ width: `${position}%` }}>
          {/* eslint-disable-next-line @next/next/no-img-element -- local blob URLs, not optimizable */}
          <img src={before} alt="Antes" className="block h-full max-w-none object-cover object-left" style={{ width: `${10000 / Math.max(position, 1)}%` }} />
        </div>
        <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-blue-600" style={{ left: `${position}%` }} />
      </div>
      <label className="flex items-center gap-3 text-sm">
        <span>Antes</span>
        <input
          type="range"
          min={0}
          max={100}
          value={position}
          onChange={(e) => setPosition(Number(e.target.value))}
          aria-label="Comparar antes e depois"
          className="flex-1"
        />
        <span>Depois</span>
      </label>
    </div>
  );
}
