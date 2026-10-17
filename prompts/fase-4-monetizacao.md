# FASE 4 — Monetização com Mercado Pago

Leia `CLAUDE.md`, `docs/PRD.md` (seções 3, 4 e 5), `docs/CHECKLIST.md`, `docs/architecture/05-ciclo-de-fichas.md` e `docs/architecture/06-pagamentos-mercado-pago.md`. Crie a branch `phase-4-monetizacao`.

## Antes de codar
Releia a documentação **oficial atual** do Mercado Pago para os fluxos abaixo e confirme com os sócios o que for ambíguo ou depender de credenciais. Se algum método não suportar um fluxo (ex.: Pix recorrente), implemente a melhor alternativa documentada na Fase 1 e avise com clareza.

## Escopo
1. **Camada de pagamentos isolada** (`backend/app/payments/`): interface `PaymentProvider` + implementação Mercado Pago. Regra de negócio não conhece o SDK.
2. **Produtos e catálogo (editáveis pelo admin):** Pro, Premium, Vitalício e os 4 pacotes avulsos de 10 fichas, com preços em `R$` vindos do banco (nunca do frontend).
3. **Métodos:** Pix, cartão de crédito e cartão de débito, para planos e avulsas. Planos mensais com recorrência (inclusive Pix quando suportado). Vitalício como pagamento único.
4. **Checkout:** tokenização/checkout hospedado do provedor; **nunca** armazenar número de cartão ou CVV. Credenciais só no backend.
5. **Fluxo:** produto validado no backend → pagamento/assinatura criado → usuário paga → webhook recebido e **autenticidade verificada** → estado atualizado → fichas/plano concedidos **exatamente uma vez** → dashboard reflete. O frontend nunca decide se pagou.
6. **Webhooks:** verificação de assinatura, idempotência por `payment_events`, proteção contra replay e duplicidade, tratamento dos estados pendente/aprovado/recusado/cancelado/expirado/estornado.
7. **Assinaturas:** ativação, renovação (zerar e conceder fichas do novo ciclo), falha de cobrança (período de tolerância definido no PRD ou proposto), cancelamento (acesso até o fim do ciclo), troca de plano (regra do PRD).
8. **Vitalício:** concede `lifetime` sem ledger de fichas; estorno revoga.
9. **Estornos e compensações:** estorno de pagamento reverte fichas via transação compensatória (nunca editar histórico); tratar fichas já consumidas.
10. **Reconciliação:** rotina que compara pagamentos do provedor com o banco e reporta divergências; logs de auditoria.
11. **Frontend:** páginas de preços e checkout, histórico de compras, gestão da assinatura, estados pendente/erro. Sem sucesso falso.
12. **Testes executados de verdade (credenciais de teste/sandbox):** cada método de pagamento disponível, webhook válido, webhook com assinatura inválida, webhook duplicado, replay, pagamento pendente que depois aprova, estorno, renovação, cancelamento, concessão exatamente uma vez sob concorrência, preço adulterado no frontend ignorado.

## Pré-requisitos externos
Liste o que preciso fornecer (credenciais de teste, URL pública para webhook em dev, etc.) e como obter. Sem credenciais, implemente contra o sandbox e deixe marcado o que não pôde ser validado de ponta a ponta.

## Ao terminar
Relatório com testes reais, o que ficou validado só em sandbox, o que depende de credenciais de produção e limitações do Mercado Pago encontradas. **PARE e pergunte: "Posso seguir para a Fase 5 — Site público, painel e conformidade?"**
