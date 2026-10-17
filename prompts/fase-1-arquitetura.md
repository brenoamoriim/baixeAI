# FASE 1 — Arquitetura e plano (SEM código de aplicação)

Leia `CLAUDE.md` e `docs/PRD.md`. Você é arquiteto de software sênior, com foco em segurança, SaaS e custo zero.

## Objetivo
Produzir a documentação técnica que guiará as fases seguintes. **Não escreva código de aplicação nesta fase.** Só documentos em `docs/architecture/`, mais a estrutura básica do repositório (`.gitignore`, `.env.example` vazio de segredos, `README.md` inicial, `docs/CHECKLIST.md`).

## Antes de começar
1. Inspecione o repositório atual (`git status`, `git log`, arquivos existentes). Não apague nada.
2. Se o repositório estiver vazio, crie a branch `phase-1-arquitetura`.

## Pesquisa obrigatória (use WebSearch/WebFetch na documentação OFICIAL, registre fonte + data)
- **Mercado Pago (Brasil):** Pix, cartão crédito/débito, assinaturas recorrentes (incluindo Pix recorrente/automático), checkout transparente vs. Checkout Pro, verificação de assinatura de webhook, ambiente de testes, estornos, taxas, e **restrições para conta de pessoa física**. Diga exatamente o que cada fluxo do PRD (seção 5) suporta e o que não suporta, com a melhor alternativa.
- **Hospedagem gratuita:** compare (A) VPS/máquina própria com Docker, (B) PaaS com camadas gratuitas, (C) híbrido. Para cada: CPU/RAM/disco reais, suspensão por inatividade, suporte a workers longos, banda, backup. Use só dados verificados; o que não achar, marque "NÃO VERIFICADO".
- **Motores gratuitos:** licenças e requisitos de LibreOffice, Pandoc, FFmpeg (codecs realmente disponíveis na imagem Docker escolhida), libvips, rembg (e licença do modelo), LaMa ou alternativa para inpainting, yt-dlp. Foque no uso comercial.
- **Políticas:** resumo do que as políticas atuais do Google AdSense, Mercado Pago e do provedor de hospedagem dizem sobre sites de download de vídeo e de remoção de elementos de imagem. Apresente o risco com sinceridade; a decisão é dos sócios.

## Entregáveis (um arquivo por item em `docs/architecture/`)
1. `01-arquitetura.md` — visão geral, diagrama (Mermaid), responsabilidades, por que cada tecnologia, e o que foi deliberadamente deixado de fora no MVP.
2. `02-hospedagem-e-custos.md` — comparação A/B/C; versão revisada de `docs/CUSTOS-GRATIS-VS-PAGO.md` só com dados verificados; modelo de custo por nível de tráfego (hipóteses explícitas); margem após taxas do Mercado Pago para Pro, Premium, vitalício e avulsos; limites reais para vídeo e IA.
3. `03-estrutura-repositorio.md` — árvore proposta (frontend/, backend/app/{api,core,models,schemas,repositories,services,workers,tools,payments,storage,security}, infrastructure/, docs/, scripts/).
4. `04-banco-de-dados.md` — esquema completo (tabelas, colunas principais, chaves, índices, constraints), incluindo `users`, `plans`, `subscriptions`, `tool_definitions`, `tool_capabilities`, `credit_buckets` (diário/plano/avulso com validade e ferramenta), `credit_ledger` append-only, `payments`, `payment_events`, `processing_jobs`, `usage_records`, `audit_events`, `feature_flags`, `system_settings`, `guest_allowances`. Explique como o saldo é calculado e protegido contra concorrência.
5. `05-ciclo-de-fichas.md` — ciclo de vida completo: visitante, gratuita (reset diário), plano (ciclo), avulsas (90 dias), vitalício, ordem de consumo, reserva/confirmação/devolução, idempotência, expiração, estorno, falha de job, troca/cancelamento de plano. Inclua diagramas de estado e casos de borda.
6. `06-pagamentos-mercado-pago.md` — estratégia por fluxo (avulso, plano mensal por Pix/cartão/débito, vitalício), estados de pagamento, webhooks, reconciliação, estornos, plano B para o que não for suportado.
7. `07-formatos-e-ferramentas.md` — estratégia do registry de capacidades, tabela inicial de combinações candidatas a `available` (a partir do PRD, seção 6.2), e como cada combinação será testada.
8. `08-seguranca-modelo-de-ameacas.md` — ameaças, controles, riscos residuais (SSRF, uploads maliciosos, FFmpeg/LibreOffice/ImageMagick, bombas de descompressão, manipulação de fichas, webhooks falsos, abuso do visitante e do vitalício, DoS).
9. `09-testes.md` — estratégia de testes (unitário, integração, concorrência de fichas, segurança, e2e).
10. `10-deploy.md` — plano de deploy gratuito, HTTPS, segredos, backup, monitoramento, rollback.
11. `11-credenciais-e-servicos.md` — tudo que os sócios precisam criar/obter (contas, tokens, domínio, e-mail transacional), com passo a passo curto.
12. `12-riscos-e-decisoes-abertas.md` — riscos de negócio/legais/técnicos e as decisões do PRD (seção 11) com sua recomendação para cada uma.
13. `13-roadmap.md` — fases 2 a 6 refinadas, com critério de pronto mensurável por fase.

Crie também `docs/CHECKLIST.md` com todas as fases e itens, marcando a Fase 1 como concluída apenas ao final.

## Regras
- Não invente dados. Marque o que não foi verificado.
- Seja objetivo; tabelas e listas curtas. Sem enrolação.
- Faça commits pequenos na branch `phase-1-arquitetura`.

## Ao terminar
Entregue um relatório curto em português: o que foi feito, os 5 maiores riscos, o que precisa da decisão dos sócios e o que não conseguiu verificar. **PARE e pergunte: "Posso seguir para a Fase 2 — Fundação?"**
