// Public site identity used for canonical URLs, sitemap and structured data.
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:8080").replace(/\/$/, "");
export const SITE_NAME = "BaixeAI";

export function absolute(path: string): string {
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

/** Routes that must never be indexed (also listed in robots.txt). */
export const PRIVATE_PATHS = ["/painel", "/admin", "/entrar", "/cadastrar", "/recuperar-senha", "/redefinir-senha",
  "/verificar-email", "/pagamento", "/ferramentas/eco", "/api/"];

/** Pages where ads are never shown (D13: none on the downloader; none near accounts/payments). */
export const NO_ADS_PATHS = ["/baixar-videos", "/painel", "/admin", "/entrar", "/cadastrar", "/recuperar-senha",
  "/redefinir-senha", "/verificar-email", "/pagamento", "/precos", "/ferramentas"];
