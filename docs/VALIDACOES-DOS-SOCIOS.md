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
- [ ] 9. Como admin, faça um reembolso de teste: `POST /api/v1/admin/payments/{id}/refund` (ou pelo botão **Reembolsar** em Admin → Pagamentos).
- [ ] 10. Cancele a assinatura de teste pelo painel e confirme no Mercado Pago que ela foi cancelada.
- [ ] 11. Me envie a saída do passo 6 e os resultados (sem credenciais): eu confirmo os 2 pontos que a documentação não deixou claros.

## Fase 5 — Site público, painel, admin e páginas legais

Preparação: `docker compose up -d --build`. Se uma mudança no frontend não aparecer, rode `docker compose restart frontend` (limitação do Docker Desktop no Windows).

- [ ] 1. Navegue como visitante por http://localhost:8080: home (teste a busca com "pdf para word", "tirar fundo", "mp3"), cada ferramenta, preços. Anote textos estranhos ou confusos.
- [ ] 2. Abra no celular (mesma rede: `http://IP-DO-PC:8080`, ou pelo modo celular do navegador, F12) e veja se tudo cabe na tela.
- [ ] 3. **Páginas legais — revisão por advogado (obrigatório antes de lançar):** `/termos`, `/privacidade`, `/reembolso`, `/cookies`, `/direitos-de-conteudo`. Pontos que dependem de vocês/advogado: foro e legislação, bases legais da LGPD e encarregado (DPO), procedimento de notificação de direitos, reembolso do vitalício, razão social/CNPJ quando existir. O aviso "Rascunho sem revisão jurídica" só sai depois disso (me peçam).
- [ ] 4. No painel (logado): baixe um resultado recente, altere a senha, exporte seus dados (abra o JSON e confira) e, com uma conta de teste, **exclua a conta** e confirme que não dá mais para entrar.
- [ ] 5. Crie o admin, se ainda não existir: `docker compose exec api python -m app.cli create-admin --email SEU-EMAIL --password "UMA-SENHA-FORTE"`. Entre e abra http://localhost:8080/admin.
- [ ] 6. No admin, com a sua senha no campo do topo: mude o custo de uma ferramenta e volte ao valor original; pause e reative um pacote; suspenda e reative um usuário de teste; veja tudo registrado em **Auditoria**. Tente marcar como `available` uma combinação `planned` e confirme que o servidor recusa.
- [ ] 7. Em Admin → Configurações, preencha `support_email` (entre aspas, ex.: `"suporte@seudominio.com.br"`) quando tiverem o e-mail, e veja em `/contato`.
- [ ] 8. **AdSense (quando quiserem anúncios):**
  - [ ] a. Criem a conta no Google AdSense com o domínio próprio (o AdSense não aprova subdomínio gratuito; confirmem a regra atual no AdSense, **NÃO VERIFICADO** por mim).
  - [ ] b. Em Admin → Configurações, preencham `adsense_client_id` (ex.: `"ca-pub-1234..."`). Abram `/ads.txt` e comparem a linha com a que o AdSense mostra em "Sites → ads.txt". Se for diferente, me avisem.
  - [ ] c. Depois da aprovação, criem os blocos de anúncio e preencham `adsense_slots`, ex.: `{"home_bottom": "111", "tool_bottom": "222"}`.
  - [ ] d. Liguem a flag `ads_enabled`. Confiram: o banner de consentimento aparece; com "Só essenciais" nenhum anúncio carrega; **nunca** aparece anúncio em `/baixar-videos`, painel, login ou pagamento.
  - [ ] e. Verifiquem as regras do AdSense sobre CMP/consentimento para o Brasil e a União Europeia (o banner atual é simples; a Google pode exigir uma CMP certificada para tráfego europeu, **NÃO VERIFICADO**).
- [ ] 9. Opcional (técnico): rodem os testes de ponta a ponta: `powershell -ExecutionPolicy Bypass -File .\e2e\run.ps1` (leva ~5 min; precisa do Docker rodando).

## Fase 6 — Colocar no ar (servidor, HTTPS, e-mail, backups)

Passo a passo técnico completo em `docs/OPERACAO.md`. Tudo aqui é gratuito; os limites dos planos gratuitos devem ser conferidos no dia (podem mudar).

- [ ] 1. **Oracle Cloud:** criem a conta escolhendo **São Paulo** como região de origem (não dá para trocar depois). Criem uma VM *Ampere A1* (ARM) com Ubuntu 24.04. Se aparecer "out of capacity", tentem em outro horário.
- [ ] 2. No console da Oracle, na *Security List* da rede, liberem as portas **80 e 443**.
- [ ] 3. **DuckDNS:** entrem em duckdns.org, criem um subdomínio (ex.: `baixeai.duckdns.org`) e apontem para o IP público da VM.
- [ ] 4. **E-mail transacional:** escolham um provedor com SMTP gratuito (anotem o limite de envios por dia do plano grátis e a data em que conferiram). Configurem o remetente conforme o provedor pedir.
- [ ] 5. **Chave dos backups:** num computador de vocês, gerem a chave (`age-keygen -o baixeai-backup.key`) e guardem o arquivo num gerenciador de senhas. **Sem essa chave os backups não podem ser lidos** — nem por mim, nem pela Oracle.
- [ ] 6. (Opcional, recomendado) **Cloudflare R2** para guardar cópias dos backups fora da VM.
- [ ] 7. Sigam `docs/OPERACAO.md` §1 para preparar a VM e fazer o primeiro deploy. Preencham o `.env` **direto na VM** — nunca me mandem as senhas.
- [ ] 8. Abram `https://SEU-SUBDOMINIO` e confiram o cadeado (HTTPS). Cadastrem-se e confirmem que o **e-mail de confirmação chega**.
- [ ] 9. Rodem a conferência de isolamento na VM (`docs/OPERACAO.md` §6) e me mandem a saída.
- [ ] 10. Cadastrem um monitor de uptime gratuito para `https://SEU-SUBDOMINIO/healthz` com alerta no e-mail de vocês.
- [ ] 11. Preencham `ALERT_EMAIL` no `.env` e confirmem que chegam alertas (ex.: deixem o disco de teste passar de 80% — ou me peçam um teste controlado).
- [ ] 12. Depois de 1 dia, confiram que o backup rodou (`docker compose ... logs backup`) e façam **um teste de restauração** no computador de vocês (`scripts/restore-test.sh`). Repitam todo mês.
- [ ] 13. **Mercado Pago em produção** (só depois da validação no sandbox da Fase 4): cadastrem o webhook `https://SEU-SUBDOMINIO/api/webhooks/mercadopago`, façam um pagamento de teste e depois **um pagamento real de valor mínimo combinado comigo**, conferindo fichas e reembolso.
- [ ] 14. Acompanhem a memória da VM nas primeiras semanas (Admin → Visão geral e `docker stats`): a Oracle pode recuperar VMs gratuitas muito ociosas (ver relatório da Fase 6).
- [ ] 15. Antes de divulgar: revisão jurídica concluída (Fase 5), e-mail de suporte configurado, decisão consciente sobre os riscos do baixador (Fase 3C).

