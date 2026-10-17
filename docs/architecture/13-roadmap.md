# 13 — Roadmap (Fases 2 a 6)

> Fase 1 · 17/10/2026. Cada fase tem branch própria (`phase-N-nome`), termina com relatório + saída real dos testes e **para** aguardando aprovação. "Pronto" = todos os critérios abaixo verificados e colados no relatório.

## Fase 2 — Fundação (`phase-2-fundacao`)
Entrega: Compose (api, um `worker` genérico, postgres, redis, frontend, beat), auth completa, papéis, registry, núcleo de fichas, jobs com ferramenta "eco" (só em dev/test), `StorageProvider` local, segurança base, shell do frontend. Os workers especializados (`light/media/ai/download`) nascem como alvos de build nas Fases 3A–3C.

Pronto quando:
- [ ] `docker compose up` sobe tudo no Windows/Docker Desktop com um comando documentado no README.
- [ ] `alembic upgrade head` em banco vazio cria todas as tabelas de `04`; `downgrade`/`upgrade` funcionam.
- [ ] Trigger append-only: teste prova que `UPDATE`/`DELETE` em `credit_ledger` falham.
- [ ] Testes de concorrência de `09` §2 (1 a 6) verdes, com saída colada.
- [ ] Testes de auth, IDOR, visitante, diária (reset 00:00 SP com relógio simulado), expiração de plano/avulsa, ordem de consumo, devolução, idempotência e propriedade de download verdes.
- [ ] Primeiro admin criado por CLI documentado; nenhuma credencial embutida.

## Fase 3A — Conversores (`phase-3a-conversores`)
Pronto quando:
- [ ] Matriz gerada a partir de `ffmpeg -encoders/-decoders` e filtros do LibreOffice **na imagem real** (amd64 e arm64).
- [ ] Cada combinação `available` tem 1 teste de conversão real verde (gerado do registry); as demais ficam `planned`/`unsupported` com motivo.
- [ ] Negativos de `08` (T2–T7) verdes: extensão falsa, corrompido, bomba de pixels/ZIP, SVG hostil, DOCX com macro, limite, timeout, injeção em opções.
- [ ] Tempo e memória medidos por categoria na máquina de dev **e** documentados (substituem H1–H3 de `02`).
- [ ] UI `/conversores` mostra só `available`, com custo antes de confirmar.

## Fase 3B — IA de imagem (`phase-3b-ia-imagem`)
Pronto quando:
- [ ] Licenças de código **e pesos** confirmadas e registradas (sem BRIA).
- [ ] Latência p50/p95 e pico de memória medidos em CPU (máquina descrita), e limite de concorrência derivado da medição.
- [ ] Testes reais: PNG com alfa, dimensões preservadas, região fora da máscara inalterada.
- [ ] `onnxruntime` funcionando em arm64 (ou alternativa documentada).
- [ ] Aceite "Declaro que tenho direito de editar esta imagem" registrado em `terms_acceptances`.

## Fase 3C — Baixador (`phase-3c-baixador`)
Pronto quando:
- [ ] Bateria SSRF de `08` T1 verde (127.0.0.1, localhost, 169.254.169.254, `[::1]`, DNS → privado, redirect → interno, rebinding simulado, `file/ftp/gopher`, credenciais na URL, portas incomuns).
- [ ] Teste de rede: de dentro do `worker-download`, conexão a Postgres/Redis-admin/metadata **falha**.
- [ ] Teste com fixture local (allowlist só em `test`) + 1 teste com URL pública estável documentada.
- [ ] Métrica de sucesso/falha por domínio registrada; procedimento de atualização do yt-dlp documentado.
- [ ] Aviso de direitos com aceite registrado.

## Fase 4 — Monetização (`phase-4-monetizacao`)
Pré-requisito: credenciais de **teste** do MP (`11`) e URL pública de webhook em dev (túnel).

Pronto quando:
- [ ] Checkout Pro (Pix, crédito, débito) para avulsas, vitalício e ciclo manual; `/preapproval` com cartão para recorrência automática.
- [ ] Webhook: válido, assinatura inválida, duplicado, replay (ts antigo), pendente→aprovado, estorno — todos testados.
- [ ] Concessão exatamente uma vez sob 5 webhooks paralelos.
- [ ] Preço adulterado no frontend ignorado (teste).
- [ ] Itens de `06` §7 respondidos no sandbox (ou marcados como não validados).
- [ ] Reconciliação roda e reporta divergência simulada.

## Fase 5 — Site público e conformidade (`phase-5-site-publico`)
Pronto quando:
- [ ] Lighthouse medido (números reais) nas páginas principais.
- [ ] Dashboard mostra fichas por origem com validade; histórico de compras e jobs.
- [ ] Admin com RBAC testado (usuário comum recebe 403 em todas as rotas admin).
- [ ] Exclusão e exportação de conta (LGPD) testadas.
- [ ] Termos/Privacidade/Reembolso/Uso justo publicados e **marcados para revisão jurídica**.
- [ ] Decisão D13 (AdSense) aplicada; anúncios longe de upload/download/pagamento.

## Fase 6 — Segurança e deploy (`phase-6-seguranca-deploy`)
Pronto quando:
- [ ] Suíte completa verde; `pip-audit`, `npm audit`, Trivy sem achado crítico aberto.
- [ ] Varredura do histórico Git sem segredos.
- [ ] VM Oracle provisionada; HTTPS Full (strict); só 80/443 abertos.
- [ ] Isolamento dos workers verificado **em produção**.
- [ ] Backup diário criptografado no R2 e **restauração testada**.
- [ ] Webhook de produção testado com pagamento real de valor mínimo combinado com os sócios.
- [ ] Runbook: subir, atualizar, reverter, rotacionar segredos, atualizar yt-dlp, incidentes.
- [ ] Limites de tamanho reavaliados com medições da VM real.
