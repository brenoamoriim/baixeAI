# FASE 6 — Revisão de segurança e deploy

Leia `CLAUDE.md`, `docs/PRD.md`, `docs/CHECKLIST.md`, `docs/architecture/08-seguranca-modelo-de-ameacas.md` e `10-deploy.md`. Crie a branch `phase-6-seguranca-deploy`.

## Parte A — Revisão de segurança (antes de qualquer deploy)
1. Rode toda a suíte de testes e mostre o resultado real.
2. Revise autorização em **cada** endpoint protegido (IDOR, escalonamento de privilégio, admin).
3. Teste abusos: manipulação de fichas, concorrência, corrida de webhooks, replay, preço adulterado, uploads maliciosos (bombas de descompressão, SVG/DOCX maliciosos, nomes com path traversal), SSRF, limites de taxa, enumeração de usuários, brute force.
4. Valide o isolamento dos workers: sem acesso à rede interna/metadata, sem acesso ao banco, usuário sem privilégios, limites de CPU/memória/disco/tempo.
5. Varredura de dependências e de imagens de contêiner com ferramentas gratuitas (ex.: pip-audit, npm audit, Trivy). Registre achados e correções.
6. Confirme: segredos fora do repositório (varra o histórico git), `.env` e `cookies.txt` ignorados, nenhum debug ligado, mensagens de erro genéricas em produção, headers/CSP.
7. Atualize o modelo de ameaças com riscos residuais honestos.

## Parte B — Deploy
1. Configure o ambiente de produção conforme `10-deploy.md` e a hospedagem escolhida (gratuita, com os limites reais conhecidos).
2. HTTPS, proxy reverso, segredos de produção, CORS restrito, domínio.
3. Backup automático do banco **e teste de restauração** (backup sem restauração testada não conta).
4. Monitoramento: health checks, logs estruturados, alerta de erro, e acompanhamento de uso de CPU/RAM/disco dos workers.
5. Pipeline de CI (testes + varreduras) e instruções de CD/rollback.
6. Webhook do Mercado Pago apontando para a URL pública, testado com pagamento de teste e depois com um pagamento real de valor mínimo combinado comigo.
7. Documentação de operação: subir, atualizar, reverter, rotacionar segredos, atualizar o extrator de vídeos, responder a incidentes.

## Regras
- Não declare "pronto para produção" sem listar o que foi testado e os riscos residuais.
- Nenhum teste é reportado como aprovado sem execução real.
- Atualize `docs/CHECKLIST.md`.

## Ao terminar
Relatório final: o que passou, o que falhou, riscos residuais, custos reais observados e próximos passos recomendados (pós-MVP: lote, mais formatos, mais ferramentas).
