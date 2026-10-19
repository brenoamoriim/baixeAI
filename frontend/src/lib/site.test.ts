import { describe, expect, it } from "vitest";
import { NO_ADS_PATHS, PRIVATE_PATHS } from "./site";
import { adsAllowed, type SiteConfig } from "./siteConfig";
import { searchTools } from "./toolSearch";

const on: SiteConfig = { ads: { enabled: true, client: "ca-pub-123", slots: { tool_bottom: "1" } }, support_email: null };

describe("adsAllowed", () => {
  it("needs flag, client id and explicit ad consent", () => {
    expect(adsAllowed("/conversores", on, "ads", NO_ADS_PATHS)).toBe(true);
    expect(adsAllowed("/conversores", on, "essential", NO_ADS_PATHS)).toBe(false);
    expect(adsAllowed("/conversores", on, null, NO_ADS_PATHS)).toBe(false);
    expect(adsAllowed("/conversores", null, "ads", NO_ADS_PATHS)).toBe(false);
    expect(adsAllowed("/conversores", { ...on, ads: { ...on.ads, enabled: false } }, "ads", NO_ADS_PATHS)).toBe(false);
    expect(adsAllowed("/conversores", { ...on, ads: { ...on.ads, client: null } }, "ads", NO_ADS_PATHS)).toBe(false);
  });

  it("never shows ads on the downloader, account, admin, auth or payment pages (D13)", () => {
    for (const path of ["/baixar-videos", "/baixar-videos/", "/painel", "/admin", "/entrar", "/cadastrar",
      "/pagamento/retorno", "/precos", "/ferramentas/eco", "/verificar-email"]) {
      expect(adsAllowed(path, on, "ads", NO_ADS_PATHS), path).toBe(false);
    }
  });

  it("allows the public content pages", () => {
    for (const path of ["/", "/removedor-de-fundo", "/remover-objeto", "/termos"]) {
      expect(adsAllowed(path, on, "ads", NO_ADS_PATHS), path).toBe(true);
    }
  });

  it("private pages are also ad-free", () => {
    for (const path of PRIVATE_PATHS.filter((p) => !p.startsWith("/api"))) {
      expect(adsAllowed(path, on, "ads", NO_ADS_PATHS), path).toBe(false);
    }
  });
});

describe("searchTools", () => {
  it("finds tools by format and intent, ignoring accents and case", () => {
    expect(searchTools("PDF para Word")[0].href).toBe("/conversores");
    expect(searchTools("tirar fundo da foto")[0].href).toBe("/removedor-de-fundo");
    expect(searchTools("apagar pessoa")[0].href).toBe("/remover-objeto");
    expect(searchTools("baixar vídeo")[0].href).toBe("/baixar-videos");
    expect(searchTools("preço vitalício")[0].href).toBe("/precos");
  });

  it("returns nothing for empty or stop-word-only queries", () => {
    expect(searchTools("")).toEqual([]);
    expect(searchTools("  de para ")).toEqual([]);
    expect(searchTools("xyzzy")).toEqual([]);
  });
});
