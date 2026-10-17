# BaixeAI — Regras permanentes do projeto

Este arquivo é carregado em toda sessão. Leia também `docs/PRD.md` (regras de negócio) e `docs/CHECKLIST.md` (estado atual) antes de qualquer trabalho.

## Idioma
- Converse comigo em português do Brasil.
- Código, identificadores, nomes de tabelas, commits e documentação de API em inglês.
- Interface do usuário em português do Brasil. Preços em R$. Datas no padrão brasileiro. Fuso de referência: `America/Sao_Paulo`.

## Como trabalhar (fluxo obrigatório)
1. O projeto é dividido em fases (`prompts/`). Trabalhe SOMENTE na fase que eu colar.
2. Ao terminar uma fase: atualize `docs/CHECKLIST.md`, rode os testes, faça o relatório final e **PARE perguntando: "Posso seguir para a Fase X?"**. Nunca avance sem minha confirmação explícita.
3. Antes de modificar qualquer coisa: inspecione o que já existe. Não sobrescreva nem apague arquivos importantes sem pedir.
4. Trabalhe em passos pequenos e verificáveis. Commits pequenos, mensagem em inglês, uma branch por fase (`phase-N-nome`). Nunca faça push em `main` sem eu pedir.
5. Se uma decisão de negócio estiver em aberto no PRD, **pergunte** em vez de inventar.

## Honestidade (inegociável)
- Nunca finja funcionalidade. Botão sem backend real não entra.
- Nunca diga que um teste passou sem tê-lo executado. Cole o resultado real (comando + saída resumida).
- Nunca invente preços, limites de plano gratuito, taxas ou capacidades de provedores/APIs. Consulte a documentação oficial atual (WebSearch/WebFetch) e registre fonte e data. O que não foi verificado deve ser marcado **"NÃO VERIFICADO"**.
- Não diga que algo está "pronto para produção" sem testes e revisão de deploy.
- Relate honestamente: o que foi feito, o que falta, o que falhou, limitações conhecidas.

## Stack (restrição: orçamento ZERO, só ferramentas gratuitas/open source)
- Frontend: Next.js + React + TypeScript + Tailwind CSS.
- Backend: Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2, Alembic, PostgreSQL.
- Fila/cache/rate limit: Redis. Workers: Celery (ou equivalente mais simples se justificado na Fase 1).
- Armazenamento: interface `StorageProvider`. No MVP, disco local com limpeza automática; deve ser trocável por S3-compatível sem mudar a regra de negócio.
- Infra: Docker + Docker Compose. Uma máquina no início, mas web, banco, fila e workers logicamente separados.
- Sem Kubernetes, sem microserviços, sem GPU no MVP.
- Meu ambiente de desenvolvimento é **Windows 11 + VS Code + Docker Desktop**. Comandos devem funcionar em PowerShell (indique quando algo exigir WSL).

## Regras de negócio críticas (detalhes no PRD)
- Moeda do produto: **ficha**. Saldo, custo, limites e cotas são decididos SEMPRE no backend. Nunca confie em preço, saldo ou status de pagamento vindos do frontend.
- Livro-razão de fichas **append-only** (corrija com transação compensatória, nunca edite histórico).
- Crédito/plano só é concedido após confirmação autoritativa do pagamento via webhook verificado e idempotente. Nunca por redirecionamento do navegador.
- Toda operação cobrável é idempotente (chave de idempotência) e atômica (reserva → confirma → ou devolve).
- Ferramentas novas entram via registry de ferramentas/capacidades, sem reescrever auth, pagamentos, fichas ou dashboard.
- Combinação de formato só é exposta se estiver **Available** (implementada + testada). Estados: `available`, `planned`, `unsupported`.

## Segurança (resumo; defesa em profundidade)
- Todo arquivo, URL e resposta externa é não confiável.
- Nunca montar comando de shell com entrada do usuário. FFmpeg/ImageMagick/LibreOffice/yt-dlp só com templates de argumentos definidos no servidor, sem shell, com timeout e limite de recursos, em worker isolado sem acesso à rede interna.
- Defesas SSRF para toda URL fornecida pelo usuário: esquema, host, resolução DNS, bloqueio de IPs privados/loopback/link-local/metadata, validação de redirects, proteção contra DNS rebinding, timeouts e limite de tamanho.
- Validar conteúdo real do arquivo (assinatura), não só extensão. Nome de arquivo gerado no servidor.
- Argon2id para senhas. Cookies HttpOnly/Secure/SameSite. CSRF onde couber. Rate limit em auth e em endpoints caros.
- Segredos só em variáveis de ambiente (`.env` nunca versionado; manter `.env.example`).
- Nunca versionar: `.env`, `cookies.txt`, chaves, bancos locais, arquivos de usuário.
- Não prometa segurança absoluta: documente modelo de ameaças e riscos residuais.

## Qualidade
- Testes junto de cada funcionalidade relevante (unitário, integração, negativos/abuso). Concorrência de fichas deve ter teste real.
- Migrações Alembic para toda mudança de banco.
- Prefira a solução mais simples que seja mantível.
- Mantenha `docs/CHECKLIST.md` atualizado a cada entrega: é a memória do projeto entre janelas.
