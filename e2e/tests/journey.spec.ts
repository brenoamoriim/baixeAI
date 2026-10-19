import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

// Two stages, separated by run.ps1 confirming the e-mail through the dev-only CLI
// (development e-mail goes to the API log; there is no web backdoor).
const STATE = path.join(__dirname, "..", ".state");
const EMAIL_FILE = path.join(STATE, "email.txt");
const PASSWORD = "senha-e2e-forte-123";

test("@signup visitor creates an account", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  await page.goto("/cadastrar");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(PASSWORD);
  await page.getByRole("button", { name: "Criar conta" }).click();
  await expect(page.getByRole("status")).toContainText("5 fichas diárias");
  mkdirSync(STATE, { recursive: true });
  writeFileSync(EMAIL_FILE, email);
});

test("@use verified user converts a file, downloads it and sees the balance", async ({ page }) => {
  const email = readFileSync(EMAIL_FILE, "utf8").trim();

  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(PASSWORD);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL("**/painel");
  const daily = page.getByRole("row", { name: /Diárias|diárias/ });
  await expect(daily.getByRole("cell").nth(1)).toHaveText("5");

  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(axe.violations.map((v) => v.id), "painel a11y").toEqual([]);

  await page.goto("/conversores");
  await page.getByLabel("Escolher arquivo para converter").setInputFiles(path.join(__dirname, "..", "fixtures", "sample.png"));
  await expect(page.getByRole("region", { name: "Arquivo analisado" })).toContainText("sample.png");
  await page.getByLabel("Converter para").selectOption("jpg");
  await page.getByRole("button", { name: /Confirmar e usar 1 ficha/ }).click();
  await expect(page.getByText("Concluído").first()).toBeVisible({ timeout: 90_000 });

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Baixar resultado" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.jpg$/);
  const file = readFileSync(await download.path());
  expect([...file.subarray(0, 3)]).toEqual([0xff, 0xd8, 0xff]); // real JPEG signature

  await page.goto("/painel");
  await expect(daily.getByRole("cell").nth(1)).toHaveText("4");
  await expect(page.getByRole("button", { name: /Baixar resultado de/ })).toBeVisible();
});
