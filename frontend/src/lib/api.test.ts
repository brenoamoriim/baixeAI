import { describe, expect, it } from "vitest";
import { ApiError, newIdempotencyKey, parseError, readCookie } from "./api";

describe("api helpers", () => {
  it("reads a cookie by exact name", () => {
    const jar = "baixeai_csrf_old=x; baixeai_csrf=abc%3D123; other=1";
    expect(readCookie("baixeai_csrf", jar)).toBe("abc=123");
    expect(readCookie("missing", jar)).toBeNull();
  });

  it("maps backend error envelopes to ApiError", async () => {
    const response = new Response(
      JSON.stringify({ error: { code: "insufficient_credits", message: "Sem fichas." } }),
      { status: 402 },
    );
    const error = await parseError(response);
    expect(error).toBeInstanceOf(ApiError);
    expect([error.status, error.code, error.message]).toEqual([402, "insufficient_credits", "Sem fichas."]);
  });

  it("falls back to a generic message for non-JSON errors", async () => {
    const error = await parseError(new Response("<html>bad gateway</html>", { status: 502 }));
    expect(error.code).toBe("unknown_error");
    expect(error.message).toMatch(/Tente novamente/);
  });

  it("generates idempotency keys the backend accepts", () => {
    const key = newIdempotencyKey();
    expect(key).toMatch(/^[A-Za-z0-9_-]{8,80}$/);
    expect(newIdempotencyKey()).not.toBe(key);
  });
});
