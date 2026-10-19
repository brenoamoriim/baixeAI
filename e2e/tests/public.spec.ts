import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PUBLIC = ["/", "/conversores", "/removedor-de-fundo", "/remover-objeto", "/baixar-videos", "/precos",
  "/termos", "/privacidade", "/reembolso", "/cookies", "/direitos-de-conteudo", "/contato", "/entrar", "/cadastrar"];
const NOINDEX = ["/painel", "/admin", "/entrar", "/cadastrar", "/pagamento/retorno"];

for (const path of PUBLIC) {
  test(`@public ${path} renders and has no WCAG A/AA violations`, async ({ page }) => {
    const adRequests: string[] = [];
    page.on("request", (r) => { if (/googlesyndication|doubleclick|adsbygoogle/.test(r.url())) adRequests.push(r.url()); });
    await page.goto(path);
    await expect(page.locator("h1").first()).toBeVisible();
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const summary = results.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
    expect(summary, summary.join("\n")).toEqual([]);
    // no ad network is contacted without config + consent (ads are off in this environment)
    expect(adRequests).toEqual([]);
  });
}

test("@public tool pages expose title, canonical and structured data", async ({ page }) => {
  await page.goto("/conversores");
  await expect(page).toHaveTitle(/Conversor/);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", /\/conversores$/);
  expect(await page.locator('script[type="application/ld+json"]').count()).toBeGreaterThan(0);
});

for (const path of NOINDEX) {
  test(`@public ${path} is noindex`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  });
}

test("@public robots and sitemap", async ({ request }) => {
  const robots = await (await request.get("/robots.txt")).text();
  expect(robots).toContain("Disallow: /painel");
  expect(robots).toContain("Disallow: /admin");
  const sitemap = await (await request.get("/sitemap.xml")).text();
  expect(sitemap).toContain("/conversores");
  expect(sitemap).not.toContain("/painel");
});

test("@public tool search on the home page", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("searchbox").first().fill("pdf para word");
  await expect(page.getByRole("link", { name: /Conversores de arquivos/ }).first()).toBeVisible();
});
