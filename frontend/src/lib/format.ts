// pt-BR presentation helpers. Reference time zone: America/Sao_Paulo.

const TIME_ZONE = "America/Sao_Paulo";

export function formatBRL(cents: number): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(cents / 100);
}

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: TIME_ZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: TIME_ZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(iso));
}

export function pluralFichas(n: number): string {
  return `${n} ${n === 1 ? "ficha" : "fichas"}`;
}

const TOOL_NAMES: Record<string, string> = {
  video_downloader: "Baixador de vídeos",
  converter: "Conversores",
  background_remover: "Removedor de fundo",
  object_remover: "Removedor de objetos",
  echo: "Eco (teste)",
};

export function toolName(toolId: string | null): string {
  return toolId ? (TOOL_NAMES[toolId] ?? toolId) : "Qualquer ferramenta";
}

const BUCKET_LABELS: Record<string, string> = {
  daily: "Fichas diárias",
  plan: "Fichas do plano",
  package: "Fichas avulsas",
  compensation: "Fichas devolvidas",
};

export function bucketLabel(kind: string, toolId: string | null): string {
  const base = BUCKET_LABELS[kind] ?? kind;
  return kind === "package" ? `${base} — ${toolName(toolId)}` : base;
}

const JOB_STATUS: Record<string, string> = {
  queued: "Na fila",
  processing: "Processando",
  completed: "Concluído",
  failed: "Falhou",
  expired: "Arquivo expirado",
};

export function jobStatusLabel(status: string): string {
  return JOB_STATUS[status] ?? status;
}

export function refundNote(errorClass: string | null): string | null {
  if (errorClass === "system" || errorClass === "timeout") {
    return "Falha nossa: a ficha foi devolvida.";
  }
  if (errorClass === "user_input") {
    return "O conteúdo enviado não pôde ser processado. A ficha foi consumida.";
  }
  return null;
}
