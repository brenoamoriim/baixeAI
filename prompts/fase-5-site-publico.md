# FASE 5 — Site público, dashboard, painel admin e conformidade

Leia `CLAUDE.md`, `docs/PRD.md`, `docs/CHECKLIST.md` e os documentos de arquitetura. Crie a branch `phase-5-site-publico`.

## Escopo
1. **Homepage compacta e profissional** (sem excesso de seções): cabeçalho, hero com busca universal de ferramentas, categorias, ferramentas em destaque, preços (Visitante/Gratuita/Pro/Premium/Vitalícia + fichas avulsas), FAQ, rodapé com links legais e suporte. Mobile-first, acessível, bom contraste, design system reutilizável.
2. **Páginas de ferramenta com SEO:** título, descrição, entradas/saídas suportadas (somente `available`), conteúdo útil e **único** (evitar páginas finas/duplicadas), metadados, canonical, dados estruturados quando apropriado.
3. **Dashboard do usuário:** fichas por origem (diária, plano, avulsas por ferramenta, com validade), plano e ciclo, vitalício, jobs recentes, downloads, histórico de pagamentos, gerenciamento da assinatura, configurações da conta.
4. **Painel admin (RBAC):** disponibilidade de ferramentas, formatos, custo em fichas, planos, catálogo de avulsas, limites de processamento, feature flags, uso agregado, falhas de processamento, pagamentos e assinaturas, eventos de auditoria, usuários conforme permissão. Ações sensíveis com confirmação reforçada. Sem backdoors.
5. **LGPD e legal:** política de privacidade, termos de uso (incluindo uso justo do vitalício, aviso de direitos sobre conteúdo, política de reembolso), política de retenção e arquivos temporários, exclusão de conta, exportação de dados, consentimento de cookies, canal de contato. Marque claramente o que **exige revisão por advogado**; não afirme conformidade legal só por existirem as páginas.
6. **AdSense e SEO técnico:** slots de anúncio configuráveis e responsivos que **não** ficam perto de botões de upload/download/pagamento, `ads.txt`, `robots.txt`, `sitemap.xml`, gerenciamento de consentimento, páginas privadas com `noindex`. Revise as políticas atuais do Google antes e não prometa aprovação.
7. **Core Web Vitals:** meça (Lighthouse) e registre números reais.
8. **Testes executados de verdade:** permissões do admin (usuário comum não acessa), IDOR no dashboard, exclusão de conta, exportação de dados, páginas privadas fora do índice, fluxo e2e (cadastro → usar ferramenta → ver saldo), acessibilidade básica automatizada.

## Regras
- Nenhum botão sem função real; o que não existe fica "em breve".
- Atualize `docs/CHECKLIST.md`.

## Ao terminar
Relatório com métricas de Lighthouse, testes reais, lista do que precisa de revisão jurídica e limitações. **PARE e pergunte: "Posso seguir para a Fase 6 — Segurança e deploy?"**
