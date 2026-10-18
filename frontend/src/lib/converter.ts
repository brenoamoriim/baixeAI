import type { Capability } from "./api";

export const CATEGORY_LABEL: Record<string, string> = {
  document: "Documentos",
  image: "Imagens",
  audio: "Áudio",
  video: "Vídeo",
};

const FORMAT_LABEL: Record<string, string> = {
  jpg: "JPG", png: "PNG", webp: "WEBP", avif: "AVIF", gif: "GIF", bmp: "BMP", tiff: "TIFF", ico: "ICO",
  heic: "HEIC", svg: "SVG", pdf: "PDF", docx: "DOCX (Word)", doc: "DOC (Word 97)", odt: "ODT", rtf: "RTF",
  txt: "TXT", html: "HTML", xlsx: "XLSX (Excel)", xls: "XLS (Excel 97)", csv: "CSV", mp3: "MP3", wav: "WAV",
  ogg: "OGG", m4a: "M4A (AAC)", flac: "FLAC", opus: "OPUS", mp4: "MP4", webm: "WEBM", mkv: "MKV", mov: "MOV",
  avi: "AVI",
};

export function formatLabel(fmt: string): string {
  return FORMAT_LABEL[fmt] ?? fmt.toUpperCase();
}

const OPTION_NAME: Record<string, string> = {
  quality: "Qualidade",
  bitrate: "Taxa de bits do áudio",
  sample_rate: "Taxa de amostragem",
  channels: "Canais",
  resolution: "Resolução (altura)",
  fps: "Quadros por segundo",
};

export function optionName(key: string): string {
  return OPTION_NAME[key] ?? key;
}

export function optionValueLabel(key: string, value: string): string {
  if (value === "original") return "Original";
  if (key === "quality") return { alta: "Alta", media: "Média", baixa: "Baixa (arquivo menor)" }[value] ?? value;
  if (key === "bitrate") return `${value.replace("k", "")} kbps`;
  if (key === "sample_rate") return `${(Number(value) / 1000).toLocaleString("pt-BR")} kHz`;
  if (key === "channels") return value === "1" ? "Mono" : "Estéreo";
  if (key === "resolution") return `${value}p`;
  return value;
}

/** Same defaults the backend applies when an option is omitted. */
export const OPTION_DEFAULT: Record<string, string> = {
  quality: "media", bitrate: "192k", sample_rate: "original", channels: "original", resolution: "original", fps: "original",
};

/** Options that make sense for a given output (audio options only when the output has audio, etc.). */
export function relevantOptions(category: string, output: string, all: Record<string, string[]>): string[] {
  const audioOut = ["mp3", "wav", "ogg", "m4a", "flac", "opus"].includes(output);
  const lossless = output === "wav" || output === "flac";
  return Object.keys(all).filter((key) => {
    if (category === "video" && output === "gif") return false;
    if (category === "video" && audioOut) return ["bitrate", "sample_rate", "channels"].includes(key);
    if (category === "video") return ["resolution", "quality", "fps"].includes(key);
    if (key === "bitrate" && lossless) return false;
    if (key === "quality" && category === "image") return ["jpg", "webp", "avif"].includes(output);
    return true;
  });
}

export function outputsFor(capabilities: Capability[], input: string): Capability[] {
  return capabilities.filter((c) => c.input === input).sort((a, b) => a.output.localeCompare(b.output));
}

/** Catalog: input formats grouped by category, filtered by a free-text query (input or output). */
export function catalog(capabilities: Capability[], query: string): Record<string, { input: string; outputs: string[] }[]> {
  const q = query.trim().toLowerCase();
  const byInput = new Map<string, { category: string; outputs: Set<string> }>();
  for (const c of capabilities) {
    const entry = byInput.get(c.input) ?? { category: c.category, outputs: new Set<string>() };
    entry.outputs.add(c.output);
    byInput.set(c.input, entry);
  }
  const groups: Record<string, { input: string; outputs: string[] }[]> = {};
  for (const [input, { category, outputs }] of byInput) {
    const outs = [...outputs].sort();
    const haystack = [input, formatLabel(input), ...outs].join(" ").toLowerCase();
    if (q && !haystack.includes(q)) continue;
    (groups[category] ??= []).push({ input, outputs: outs });
  }
  for (const list of Object.values(groups)) list.sort((a, b) => a.input.localeCompare(b.input));
  return groups;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} KB`;
  return `${(bytes / 1024 / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`;
}

export function formatDuration(seconds: number): string {
  const total = Math.round(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
