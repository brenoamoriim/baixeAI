import { describe, expect, it } from "vitest";
import { bucketLabel, formatBRL, formatDate, formatDateTime, pluralFichas, refundNote } from "./format";

describe("pt-BR formatting", () => {
  it("formats prices in reais", () => {
    expect(formatBRL(2490).replace(/\s/g, " ")).toBe("R$ 24,90");
    expect(formatBRL(12000).replace(/\s/g, " ")).toBe("R$ 120,00");
  });

  it("formats dates in America/Sao_Paulo", () => {
    // 02:59 UTC on the 18th is still 23:59 on the 17th in São Paulo
    expect(formatDateTime("2026-10-18T02:59:00Z")).toBe("17/10/2026, 23:59");
    expect(formatDate("2026-10-18T03:00:00Z")).toBe("18/10/2026");
  });

  it("pluralizes fichas", () => {
    expect(pluralFichas(1)).toBe("1 ficha");
    expect(pluralFichas(0)).toBe("0 fichas");
    expect(pluralFichas(5)).toBe("5 fichas");
  });

  it("labels buckets by origin", () => {
    expect(bucketLabel("daily", null)).toBe("Fichas diárias");
    expect(bucketLabel("package", "converter")).toBe("Fichas avulsas — Conversores");
  });

  it("explains refunds honestly", () => {
    expect(refundNote("system")).toMatch(/devolvida/);
    expect(refundNote("timeout")).toMatch(/devolvida/);
    expect(refundNote("user_input")).toMatch(/consumida/);
    expect(refundNote(null)).toBeNull();
  });
});
