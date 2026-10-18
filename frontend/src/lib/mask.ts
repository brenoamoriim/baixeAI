export type Point = { x: number; y: number };
export type Stroke = { size: number; points: Point[] };

/** Convert a pointer position on the displayed (scaled) canvas to original-image pixels. */
export function toNatural(clientX: number, clientY: number, rect: { left: number; top: number; width: number; height: number },
                          naturalWidth: number, naturalHeight: number): Point {
  const x = ((clientX - rect.left) / rect.width) * naturalWidth;
  const y = ((clientY - rect.top) / rect.height) * naturalHeight;
  return { x: Math.min(Math.max(x, 0), naturalWidth), y: Math.min(Math.max(y, 0), naturalHeight) };
}

/** Brush size picked on screen, expressed in original-image pixels. */
export function naturalBrush(screenSize: number, displayWidth: number, naturalWidth: number): number {
  return Math.max(1, Math.round((screenSize * naturalWidth) / Math.max(displayWidth, 1)));
}

export function drawStrokes(ctx: CanvasRenderingContext2D, strokes: Stroke[], color: string, scale = 1): void {
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (const stroke of strokes) {
    ctx.lineWidth = stroke.size * scale;
    if (stroke.points.length === 1) {
      const p = stroke.points[0];
      ctx.beginPath();
      ctx.arc(p.x * scale, p.y * scale, (stroke.size * scale) / 2, 0, Math.PI * 2);
      ctx.fill();
      continue;
    }
    ctx.beginPath();
    stroke.points.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x * scale, p.y * scale) : ctx.lineTo(p.x * scale, p.y * scale)));
    ctx.stroke();
  }
}
