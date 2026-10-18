import { describe, expect, it } from "vitest";
import { naturalBrush, toNatural } from "./mask";

describe("mask coordinates", () => {
  const rect = { left: 100, top: 50, width: 450, height: 300 }; // displayed at 50% of 900x600

  it("maps screen points to original pixels", () => {
    expect(toNatural(100, 50, rect, 900, 600)).toEqual({ x: 0, y: 0 });
    expect(toNatural(325, 200, rect, 900, 600)).toEqual({ x: 450, y: 300 });
    expect(toNatural(550, 350, rect, 900, 600)).toEqual({ x: 900, y: 600 });
  });

  it("clamps points outside the image", () => {
    expect(toNatural(0, 0, rect, 900, 600)).toEqual({ x: 0, y: 0 });
    expect(toNatural(9999, 9999, rect, 900, 600)).toEqual({ x: 900, y: 600 });
  });

  it("scales the brush to original pixels", () => {
    expect(naturalBrush(30, 450, 900)).toBe(60);
    expect(naturalBrush(30, 900, 900)).toBe(30);
    expect(naturalBrush(1, 4000, 100)).toBe(1);
  });
});
