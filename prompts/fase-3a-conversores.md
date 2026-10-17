# FASE 3A — Ferramenta: Conversores

Leia `CLAUDE.md`, `docs/PRD.md` (seção 6.2), `docs/CHECKLIST.md` e `docs/architecture/07-formatos-e-ferramentas.md`. Crie a branch `phase-3a-conversores`.

## Objetivo
Entregar a ferramenta **Conversores** funcionando de ponta a ponta (upload → job → fichas → download), cobrindo documento, imagem, áudio e vídeo, **somente com combinações testadas**.

## Escopo
1. **Registry de capacidades:** popular com os formatos do PRD 6.2. Cada entrada: nome, extensões, MIME, operações de entrada/saída, engine, requisitos, limitações, status, custo. Descubra os codecs/encoders **realmente instalados** na imagem Docker (FFmpeg: `-encoders/-decoders`; LibreOffice: filtros) e gere a matriz de combinações candidatas. Só marque `available` após teste automatizado com arquivo real.
2. **Engines (em worker isolado):**
   - Documentos: LibreOffice headless + Pandoc. Macros desativadas, sem referências externas, perfil temporário por job, timeout.
   - Imagens: libvips/Pillow. Limites de pixels e dimensões (bomba de descompressão), SVG sanitizado e rasterizado em ambiente restrito, comportamento de GIF animado e metadados definido.
   - Áudio e vídeo: FFmpeg **somente via templates de argumentos fixos no servidor**, sem shell, com `-nostdin`, timeout e limite de recursos. Opções expostas apenas as validadas (resolução, bitrate/qualidade, fps, taxa de amostragem, canais, extrair áudio, vídeo→GIF).
3. **Validação de upload:** assinatura/conteúdo real (não só extensão), limites por tipo do PRD, nome aleatório no servidor, mensagens de erro úteis para arquivo corrompido, não suportado ou grande demais.
4. **API:** listar formatos/combinações disponíveis (somente `available`), criar job, status, download.
5. **Frontend:** página `/conversores` com catálogo pesquisável, arrastar-e-soltar, escolha origem→destino (só combinações disponíveis), opções, custo em fichas visível antes de confirmar, progresso real, download, estados de erro. Acessível e responsivo.
6. **Testes executados de verdade:**
   - Um teste de conversão real por combinação `available`, gerado automaticamente a partir do registry.
   - Negativos: arquivo corrompido, extensão falsa, bomba de descompressão, SVG com script/recurso externo, DOCX com macro, arquivo acima do limite, timeout, tentativa de injeção em parâmetros.
   - Fichas: cobrança só em sucesso, devolução em falha, sem cobrança dupla em retry.
   - Download de arquivo de outro usuário deve ser negado.

## Regras
- Combinação sem teste verde = não aparece na interface.
- Documente limitações conhecidas (ex.: PDF→DOCX perde layout) e exiba aviso ao usuário.
- Atualize `docs/CHECKLIST.md` e `docs/architecture/07-formatos-e-ferramentas.md` com o que ficou `available`, `planned` e `unsupported`.

## Ao terminar
Relatório com tabela de combinações `available` + resultado real dos testes + limitações. **PARE e pergunte: "Posso seguir para a Fase 3B — Ferramentas de imagem com IA?"**
