# FASE 2 — Fundação da plataforma (código)

Leia `CLAUDE.md`, `docs/PRD.md`, `docs/CHECKLIST.md` e os documentos de `docs/architecture/` aprovados na Fase 1. Siga o que foi decidido lá. Se algo mudou, avise antes.

## Objetivo
Construir a base compartilhada sobre a qual as ferramentas e os pagamentos serão acoplados. **Sem ferramentas finais ainda** (apenas uma ferramenta "eco" de teste, que não aparece em produção, para validar o fluxo de job + fichas).

Crie a branch `phase-2-fundacao`.

## Escopo
1. **Monorepo e ambiente:** `frontend/` (Next.js + TS + Tailwind), `backend/` (FastAPI), `docker-compose.yml` (api, worker, postgres, redis, frontend), `.env.example`. Tudo deve subir com um comando no Windows + Docker Desktop. Documente no `README.md`.
2. **Banco e migrações:** modelos SQLAlchemy 2 e migrações Alembic conforme `04-banco-de-dados.md`.
3. **Autenticação:** cadastro, login, logout, verificação de e-mail, recuperação de senha, sessões por cookie HttpOnly/Secure/SameSite, Argon2id, rate limit nos endpoints de auth, CSRF onde necessário. Em desenvolvimento, e-mails vão para console/arquivo (provedor real fica para depois).
4. **Papéis e permissões:** `user` e `admin` (sem credencial mestre escondida; primeiro admin criado por comando de CLI documentado).
5. **Registry de ferramentas e capacidades:** `tool_definitions`, `tool_capabilities`, estados `available/planned/unsupported`, custo em fichas configurável por ferramenta.
6. **Sistema de fichas (núcleo):**
   - Livro-razão append-only e `credit_buckets` conforme `05-ciclo-de-fichas.md`.
   - Visitante: 1 ficha única (controle server-side, anti-abuso sem fingerprinting invasivo).
   - Gratuita: 5 fichas/dia, reset 00:00 America/Sao_Paulo, sem acúmulo.
   - Plano (Pro 300 / Premium 800): ciclo, zerar ao fim, sem acúmulo. Neste momento, a concessão será por função de serviço/CLI de admin (o pagamento real é Fase 4).
   - Avulsas por ferramenta com validade de 90 dias.
   - Vitalício: sem contabilização.
   - Reserva atômica → confirmação → devolução em falha. Idempotência por chave. Ordem de consumo definida no PRD.
   - Rotina de expiração (tarefa periódica).
7. **Jobs:** modelo `processing_jobs` com estados `queued, processing, completed, failed, canceled, expired`; endpoint de criação (idempotente), de status (com checagem de dono) e de cancelamento; fila Celery (ou equivalente decidido) com worker de exemplo.
8. **Armazenamento:** interface `StorageProvider` + implementação em disco local, nomes gerados no servidor, links de download temporários assinados com checagem de dono, limpeza automática de expirados.
9. **Segurança base:** headers de segurança, CORS restrito, tratamento de erro genérico em produção, logging estruturado, health checks, validação de entrada.
10. **Frontend shell:** layout, navegação, páginas de login/cadastro/recuperação, dashboard mínimo (saldo de fichas por origem), componente de ferramenta genérico, em pt-BR e acessível.
11. **Testes (executados de verdade):** autenticação, autorização/IDOR, limites do visitante e do plano gratuito, reset diário, expiração de plano e de avulsas, ordem de consumo, devolução em falha, idempotência, **concorrência** (várias requisições simultâneas tentando gastar a última ficha: nunca saldo negativo, nunca cobrança dupla), propriedade de download.

## Regras
- Commits pequenos, testes junto do código. Rode a suíte e mostre o resultado real.
- Nada de funcionalidade fingida. O que ainda não existe aparece como "em breve", não como botão ativo.
- Atualize `docs/CHECKLIST.md`.

## Ao terminar
Relatório: o que funciona (com saída dos testes), o que falta, limitações conhecidas, como rodar tudo. **PARE e pergunte: "Posso seguir para a Fase 3A — Conversores?"**
