# Validações que os sócios precisam fazer

> Lista do que **não dá para eu (Claude) verificar sozinho**: depende de credenciais, contas, decisão jurídica,
> hospedagem real ou do seu olhar humano. Organizada por fase, passo a passo. Marque `[x]` ao concluir.
> Comandos em **PowerShell**, na pasta do projeto, com o Docker Desktop aberto.
> Atualizada em 19/10/2026 (até a Fase 4). Será completada nas Fases 5 e 6.

## Antes de tudo (uma vez)

- [ ] 1. Atualize o código: `git checkout main` e `git pull`.
- [ ] 2. Suba tudo: `docker compose up --build` (a 1ª vez demora: baixa LibreOffice, FFmpeg e ~370 MB de modelos de IA).
- [ ] 3. Abra **http://localhost:8080** (não use a porta 3000 para testar).

## Fase 1 — Arquitetura e decisões

- [ ] 1. Leia `docs/PRD.md` e confirme que todas as decisões marcadas ✅ estão como vocês querem.
- [ ] 2. Leia `docs/architecture/12-riscos-e-decisoes-abertas.md` (principalmente §4, baixador de vídeos) e decidam conscientemente se o baixador entra no lançamento.
- [ ] 3. Confirme no **app do Mercado Pago** (Seu negócio → Custos) as taxas reais da conta de vocês (o plano usa Pix 0,99% e crédito 3,98–4,98%, que podem variar por conta).
- [ ] 4. Confira no app do Mercado Pago se há **limite de recebimento** para a conta de pessoa física.
- [ ] 5. Converse com um **contador** sobre tributação de vendas recorrentes em CPF e sobre abrir um MEI (o Pix Automático exige CNPJ).

## Fase 2 — Fundação (contas e fichas)

- [ ] 1. Em http://localhost:8080/cadastrar, crie uma conta com seu e-mail.
- [ ] 2. Pegue o link de confirmação no log: `docker compose logs api | Select-String "token="` e abra no navegador.
- [ ] 3. Entre e veja no painel: **5 fichas diárias**.
- [ ] 4. Use a ferramenta de teste em http://localhost:8080/ferramentas/eco e veja o saldo cair para 4.
- [ ] 5. Saia, use "Esqueci minha senha", redefina pelo link do log e entre com a senha nova.
- [ ] 6. Abra uma janela anônima (visitante) e use 1 ficha; na 2ª tentativa deve pedir cadastro.
- [ ] 7. Crie o admin: `docker compose exec api python -m app.cli create-admin --email SEU_EMAIL`.

## Fase 3A — Conversores

- [ ] 1. Em http://localhost:8080/conversores, converta arquivos **reais seus**: um DOCX→PDF, um PDF→DOCX (confira a perda de layout avisada), uma foto do celular HEIC→JPG, um MP3→OPUS e um vídeo curto MP4→WEBM.
- [ ] 2. Abra cada resultado nos programas que vocês usam (Word, leitor de PDF, galeria, player) e confirme que estão bons.
- [ ] 3. Tente enviar um arquivo acima do limite (ex.: vídeo > 95 MB) e confirme a mensagem de erro sem cobrar ficha.
- [ ] 4. Confirme que os limites (20 MB imagem, 25 MB documento, 50 MB áudio, 95 MB / 10 min vídeo) atendem vocês.

## Fase 3B — Removedor de fundo e de objetos

- [ ] 1. Em http://localhost:8080/removedor-de-fundo, teste com **fotos reais** (pessoa, produto, animal, cabelo). Os testes automáticos só usaram imagens sintéticas.
- [ ] 2. Em http://localhost:8080/remover-objeto, apague algo de uma foto real (pessoa ao fundo, fio, objeto). Avalie se a qualidade é aceitável para cobrar.
- [ ] 3. Teste com uma foto tirada **em pé no celular** (orientação EXIF) e confirme que o resultado sai na posição certa.
- [ ] 4. Leiam o texto de aceite de direitos e decidam se está adequado (vai para revisão jurídica na Fase 5).

## Fase 3C — Baixador de vídeos

- [ ] 1. Em http://localhost:8080/baixar-videos, teste com o link de domínio público usado nos testes: `https://commons.wikimedia.org/wiki/File:Apollo_15_launch.ogv` (MP4 e MP3).
- [ ] 2. Testem com links públicos das plataformas que vocês pretendem anunciar e anotem quais funcionam (de casa funciona mais que no servidor).
- [ ] 3. Como admin, veja a taxa de sucesso por domínio: `GET http://localhost:8080/api/v1/admin/download-stats` (logado como admin).
- [ ] 4. **Decisão consciente** sobre os riscos (termos das plataformas, AdSense, Mercado Pago, hospedagem) antes de lançar o baixador.

## Fase 4 — Pagamentos (Mercado Pago) — **pendente: precisa das credenciais de teste**

Sem esta etapa, os pagamentos ficam desligados (o site mostra "Pagamentos ainda não estão disponíveis").

- [ ] 1. No painel de desenvolvedores do Mercado Pago, crie a aplicação e copie as **credenciais de TESTE** (passo a passo em `docs/architecture/11-credenciais-e-servicos.md`, seção "Fase 4").
- [ ] 2. Copie `.env.example` para `.env` e preencha `MP_ACCESS_TOKEN`, `MP_PUBLIC_KEY`, `MP_WEBHOOK_SECRET`. **Nunca** cole isso no chat nem versione o `.env`.
- [ ] 3. Suba o túnel: `docker compose --profile tunnel up -d tunnel` e pegue o endereço: `docker compose logs tunnel | Select-String trycloudflare`.
- [ ] 4. Coloque esse endereço em `API_PUBLIC_URL` no `.env` e rode `docker compose up -d`.
- [ ] 5. No painel do Mercado Pago → Webhooks, cadastre `https://SEU-TUNEL/api/webhooks/mercadopago` com os tópicos Pagamentos, Planos e assinaturas e Chargebacks.
- [ ] 6. Rode: `docker compose exec api python -m app.payments.sandbox_check` e guarde a saída.
- [ ] 7. Em http://localhost:8080/precos, faça compras de teste com os cartões de teste do Mercado Pago (titular `APRO` = aprovado):
  - [ ] a. pacote avulso com **Pix** (teste);
  - [ ] b. pacote avulso com **cartão de crédito**;
  - [ ] c. pacote avulso com **cartão de débito**;
  - [ ] d. plano Pro **no cartão** (assinatura automática);
  - [ ] e. plano Pro **pagando 1 mês** (renovação manual);
  - [ ] f. vitalício;
  - [ ] g. um pagamento **recusado** (titular `OTHE`) e um **pendente** (titular `CONT`).
- [ ] 8. Depois de cada compra, confira no painel se as fichas/plano apareceram **só depois** da confirmação.
- [ ] 9. Como admin, faça um reembolso de teste: `POST /api/v1/admin/payments/{id}/refund` (botão no painel admin a partir da Fase 5).
- [ ] 10. Cancele a assinatura de teste pelo painel e confirme no Mercado Pago que ela foi cancelada.
- [ ] 11. Me envie a saída do passo 6 e os resultados (sem credenciais): eu confirmo os 2 pontos que a documentação não deixou claros.
