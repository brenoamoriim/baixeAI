# 11 — Credenciais e serviços que os sócios precisam obter

> Fase 1 · 17/10/2026. **Nunca cole segredos no chat.** Tudo vai no `.env` local (não versionado). Limites citados foram verificados nas fontes de `02`; o que não foi está marcado.

| # | Item | Quando | Custo | Obrigatório? |
|---|---|---|---|---|
| 1 | Credenciais de **teste** do Mercado Pago | antes da Fase 4 | grátis | Sim |
| 2 | Credenciais de **produção** + assinatura secreta do webhook | Fase 6 | taxa por venda | Sim |
| 3 | Domínio `.com.br` | antes da Fase 6 | **R$ 40/ano** no Registro.br (valor de fontes 2026; confirmar no site) | Sim |
| 4 | Conta Cloudflare (DNS + proxy + R2) | Fase 6 | grátis (R2 exige cartão cadastrado — **NÃO VERIFICADO**) | Recomendado |
| 5 | Conta Oracle Cloud (Always Free) | Fase 6 (pode criar antes para garantir capacidade A1) | grátis (exige cartão para verificação) | Recomendado |
| 6 | E-mail transacional (Resend) | Fase 2 (dev usa `console`), produção na Fase 6 | grátis: 3.000/mês, 100/dia | Sim |
| 7 | E-mail de suporte (ex.: `suporte@dominio`) | Fase 5 | Cloudflare Email Routing (encaminhamento) — grátis, limites **NÃO VERIFICADO** | Sim |
| 8 | GitHub (repositório + Actions + GHCR) | já existe | grátis | Sim |
| 9 | Sentry (opcional) | Fase 6 | grátis (5 mil erros) | Não |
| 10 | Google AdSense (opcional) | após o lançamento | grátis; aprovação não garantida (ver `12`) | Não |
| 11 | Contador / CNPJ (MEI ou ME) | antes de escalar vendas | custo variável **NÃO VERIFICADO** | Recomendado (Pix Automático exige CNPJ) |

## Passo a passo curto

**1. Mercado Pago — teste (Fase 4)**
1. Entre em [mercadopago.com.br/developers](https://www.mercadopago.com.br/developers) com a conta PF.
2. "Suas integrações" → **Criar aplicação** → produto "Checkout Pro" (pagamentos online) e também "Assinaturas".
3. Em **Credenciais de teste**, copie `Public Key` e `Access Token` para o `.env` (`MP_PUBLIC_KEY`, `MP_ACCESS_TOKEN`).
4. Em **Webhooks**, cadastre a URL (na Fase 4 usaremos um túnel para o localhost) e marque os tópicos *Pagamentos*, *Planos e assinaturas* e *Chargebacks*. Copie a **assinatura secreta** para `MP_WEBHOOK_SECRET`.
5. Crie contas de teste (comprador/vendedor) no painel, se pedido pela Fase 4.

**2. Mercado Pago — produção (Fase 6):** mesmo painel, aba **Credenciais de produção** (pode exigir dados do negócio e site publicado). Cadastre chave Pix na conta (exigida para receber Pix).

**3. Domínio:** [registro.br](https://registro.br) → pesquisar → registrar com CPF/CNPJ → depois apontar os *nameservers* para a Cloudflare.

**4. Cloudflare:** criar conta → "Add site" → plano **Free** → trocar nameservers no Registro.br → ativar R2 (bucket privado `baixeai-backups`) e gerar um token de API com acesso só a esse bucket.

**5. Oracle Cloud:** criar conta Free Tier → **home region: Brazil East (São Paulo)** (não muda depois) → criar instância *VM.Standard.A1.Flex* com 2 OCPU / 12 GB, Ubuntu LTS → baixar a chave SSH e guardar em local seguro (nunca no repositório).

**6. Resend:** criar conta → adicionar o domínio → criar os registros DNS (SPF/DKIM) na Cloudflare → gerar API key → `RESEND_API_KEY`.

**7. E-mail de suporte:** Cloudflare → Email Routing → encaminhar `suporte@` para o Gmail dos sócios.

## Fase 4 — validar no sandbox do Mercado Pago (quando tiver as credenciais de teste)

1. Copie `.env.example` para `.env` (o `.env` não é versionado) e preencha **só com credenciais de TESTE**:
   `MP_ACCESS_TOKEN`, `MP_PUBLIC_KEY`, `MP_WEBHOOK_SECRET`.
2. Suba o túnel público de desenvolvimento e pegue o endereço:
   ```powershell
   docker compose --profile tunnel up -d tunnel
   docker compose logs tunnel | Select-String trycloudflare
   ```
   Coloque o endereço em `API_PUBLIC_URL` no `.env` (ele muda a cada vez que o túnel sobe).
3. No painel do Mercado Pago (Suas integrações → Webhooks), cadastre `https://<túnel>/api/webhooks/mercadopago` com os tópicos **Pagamentos**, **Planos e assinaturas** e **Chargebacks**.
4. `docker compose up -d` e rode `docker compose exec api python -m app.payments.sandbox_check`.
5. Compre pelo site (http://localhost:8080/precos) usando os cartões de teste (titular `APRO` = aprovado, `OTHE` = recusado, `CONT` = pendente).
6. Me avise: eu confiro os eventos recebidos (`payment_events`) e marco o que ficou validado.

Nunca cole credenciais no chat.
