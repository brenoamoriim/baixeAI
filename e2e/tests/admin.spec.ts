import { expect, test } from "@playwright/test";

// Admin account created by run.ps1 through the CLI (create-admin); credentials only exist in this dev run.
const EMAIL = process.env.E2E_ADMIN_EMAIL ?? "";
const PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "";

test("@admin sensitive change needs the password again and is audited", async ({ page }) => {
  test.skip(!EMAIL || !PASSWORD, "admin credentials not provided");
  await page.goto("/entrar");
  await page.getByLabel("E-mail").fill(EMAIL);
  await page.getByLabel("Senha").fill(PASSWORD);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL("**/painel");

  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Administração" })).toBeVisible();
  await expect(page.getByText("Receita líquida (30 dias)")).toBeVisible(); // overview loaded

  await page.getByRole("button", { name: "Ferramentas" }).click();
  const cost = page.getByLabel(/^Custo de Conv/);
  const original = await cost.inputValue();
  const changed = original === "2" ? "3" : "2";
  const row = page.getByRole("row").filter({ has: cost });

  // wrong password -> refused by the server
  await page.getByLabel(/Sua senha/).fill("senha-errada-123");
  await cost.fill(changed);
  await row.getByRole("button", { name: "Salvar" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Confirme sua senha" })).toBeVisible();

  // right password -> saved; then restore the original value
  await page.getByLabel(/Sua senha/).fill(PASSWORD);
  await row.getByRole("button", { name: "Salvar" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Ferramenta atualizada" })).toBeVisible();
  await expect(cost).toHaveValue(changed);
  await cost.fill(original);
  await row.getByRole("button", { name: "Salvar" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Ferramenta atualizada" })).toBeVisible();

  await page.getByRole("button", { name: "Auditoria" }).click();
  await expect(page.getByRole("cell", { name: /tool/ }).first()).toBeVisible();
});
