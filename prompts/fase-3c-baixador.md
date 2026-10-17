# FASE 3C — Ferramenta: Baixador de vídeos

Leia `CLAUDE.md`, `docs/PRD.md` (seção 6.1), `docs/CHECKLIST.md` e `docs/architecture/08-seguranca-modelo-de-ameacas.md`. Crie a branch `phase-3c-baixador`.

## Decisão de produto (já tomada)
O usuário cola uma URL de vídeo **de qualquer plataforma** e o sistema tenta oferecer o download, sem depender de API oficial e sem lista fixa de plataformas. O motor de extração (candidato: yt-dlp, open source) fica atrás de uma interface `VideoExtractor` substituível.

Limites inegociáveis: apenas conteúdo público acessível sem login; sem DRM, sem conteúdo privado, sem paywall; nunca receber senha ou cookie de conta do usuário; nunca fabricar opções de qualidade nem arquivos.

## Escopo
1. **Entrada única de URL** com validação no backend e identificação da plataforma quando possível (apenas informativa).
2. **Defesa SSRF completa** em todo acesso de rede originado por URL do usuário: esquema permitido (http/https), validação de host, resolução DNS e bloqueio de IPs privados/loopback/link-local/metadata, validação de cada redirect, proteção contra DNS rebinding (fixar o IP resolvido), limites de tempo e de tamanho, e restrição de saída de rede do worker. Isso vale também para URLs de mídia devolvidas pelo extrator.
3. **Fluxo:** validar → consultar opções reais (qualidade/formato disponíveis) → mostrar custo em fichas → exigir aceite do aviso de direitos (registrar) → job assíncrono → progresso real → link temporário assinado → política de fichas (cobra em sucesso, devolve em falha do sistema).
4. **Worker dedicado** com timeout, limite de tamanho/duração, disco temporário com cota e limpeza automática, execução do extrator sem shell e com argumentos controlados pelo servidor.
5. **Erros úteis e honestos:** vídeo privado, indisponível, bloqueio da plataforma ao IP do servidor, formato não suportado, vídeo grande demais. Nada de falso sucesso.
6. **Observabilidade do motor:** registrar taxa de sucesso/falha por domínio (sem dados pessoais) para saber quando o extrator quebra; documentar como atualizar o extrator.
7. **Frontend:** página `/baixar-videos` com campo único de URL, aceite do aviso, opções reais, custo, progresso, download, estados de erro.
8. **Testes executados de verdade:**
   - SSRF: `http://127.0.0.1`, `localhost`, `169.254.169.254`, IPv6 loopback, hostnames que resolvem para IP privado, redirect para IP interno, DNS rebinding simulado, esquemas `file://`/`ftp://`/`gopher://`, URL com credenciais embutidas, portas incomuns.
   - Limites de tamanho/duração/timeout.
   - Fichas: cobrança só em sucesso, devolução em falha, sem cobrança dupla.
   - Propriedade de download.
   - Um teste de integração real com uma URL pública estável escolhida por você (documente qual e por quê).

## Regras
- Registre no `docs/architecture/12-riscos-e-decisoes-abertas.md` o risco real: bloqueio de IP de datacenter, mudanças nas plataformas, termos de uso, impacto em AdSense/Mercado Pago/hospedagem. Seja direto.
- Atualize `docs/CHECKLIST.md`.

## Ao terminar
Relatório com resultados reais dos testes de SSRF e de integração, taxa de sucesso observada e limitações. **PARE e pergunte: "Posso seguir para a Fase 4 — Monetização?"**
