// Thin typed client for the BaixeAI API. The backend is the only authority on prices,
// balances and payment status: nothing here computes or trusts those values.

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

const CSRF_COOKIE = "baixeai_csrf";

export function readCookie(name: string, cookieString: string): string | null {
  for (const part of cookieString.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

async function csrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE, document.cookie);
  if (existing) return existing;
  const response = await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
  const body = (await response.json()) as { csrf_token: string };
  return body.csrf_token;
}

export async function parseError(response: Response): Promise<ApiError> {
  let code = "unknown_error";
  let message = "Algo deu errado. Tente novamente.";
  try {
    const body = await response.json();
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
    }
  } catch {
    // non-JSON error body: keep the generic message
  }
  return new ApiError(response.status, code, message);
}

type Method = "GET" | "POST" | "PATCH";

export async function api<T>(
  path: string,
  options: { method?: Method; body?: unknown; headers?: Record<string, string> } = {},
): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  if (method !== "GET") {
    headers["X-CSRF-Token"] = await csrfToken();
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`/api/v1${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as T;
}

/** Multipart upload (the browser sets the boundary; the backend sniffs the real format). */
export async function uploadFile(file: File): Promise<Upload> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/v1/uploads", {
    method: "POST",
    headers: { "X-CSRF-Token": await csrfToken(), Accept: "application/json" },
    credentials: "same-origin",
    body: form,
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as Upload;
}

/** 128 random bits as hex. getRandomValues (unlike randomUUID) also works outside secure contexts. */
export function newIdempotencyKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

// ---- response types (mirror backend/app/api/v1) ----

export type Me = { id: string; email: string; email_verified: boolean; role: "user" | "admin" };

export type Bucket = {
  kind: "daily" | "plan" | "package" | "compensation";
  tool_id: string | null;
  available: number;
  reserved: number;
  expires_at: string;
};

export type Credits = {
  lifetime: boolean;
  email_verified: boolean;
  subscription: {
    plan: string;
    plan_name: string;
    period_end: string;
    cancel_at_period_end: boolean;
    next_plan: string | null;
  } | null;
  total_general: number;
  buckets: Bucket[];
};

export type Capability = { category: string; input: string; output: string; note: string | null };

export type Tool = {
  id: string;
  name: string;
  base_cost: number;
  status: "available" | "coming_soon";
  capabilities: Capability[];
  info?: {
    options?: Record<string, Record<string, string[]>>;
    limits_bytes?: Record<string, number>;
    video_max_seconds?: number;
  };
};

export type Upload = {
  id: string;
  status: "probing" | "ready" | "rejected";
  format: string;
  category: "document" | "image" | "audio" | "video";
  size_bytes: number;
  original_name: string;
  error_code: string | null;
  error_message: string | null;
  expires_at: string;
  info: { width?: number; height?: number; pages?: number; duration_seconds?: number; has_audio?: boolean; has_video?: boolean };
};

export type Job = {
  id: string;
  tool_id: string;
  status: "queued" | "processing" | "completed" | "failed" | "expired";
  progress: number;
  credit_cost: number;
  charged_from: "credits" | "lifetime" | "guest";
  error_code: string | null;
  error_class: "user_input" | "system" | "timeout" | null;
  created_at: string | null;
  finished_at: string | null;
  output_expires_at: string | null;
  has_output: boolean;
};
