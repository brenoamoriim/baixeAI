# 07 — Formatos, motores e registry de ferramentas

> Fase 1 · 17/10/2026. Nenhuma combinação abaixo está `available` ainda: todas são **candidatas**. Viram `available` só com teste de motor verde (Fases 3A–3C).

## 0. Resultado da Fase 3A (18/10/2026)

**174 combinações `available`**, todas aprovadas por conversão real nas imagens `worker-light` e `worker-media` (`backend/app/tools/converter/verified.json`, gerado por `python -m app.tools.converter.verify`). Nenhuma candidata ficou de fora; as combinações não listadas abaixo simplesmente não existem no catálogo de lançamento.

**Documentos** (12)

| Entrada | Saídas `available` |
|---|---|
| csv | xlsx |
| doc | docx, pdf |
| docx | pdf |
| html | pdf |
| odt | pdf |
| pdf | docx, txt |
| rtf | pdf |
| txt | pdf |
| xls | csv |
| xlsx | csv |

**Imagens** (72)

| Entrada | Saídas `available` |
|---|---|
| avif | bmp, gif, ico, jpg, png, tiff, webp |
| bmp | avif, gif, ico, jpg, png, tiff, webp |
| gif | avif, bmp, ico, jpg, png, tiff, webp |
| heic | avif, bmp, gif, ico, jpg, png, tiff, webp |
| ico | avif, bmp, gif, jpg, png, tiff, webp |
| jpg | avif, bmp, gif, ico, png, tiff, webp |
| png | avif, bmp, gif, ico, jpg, tiff, webp |
| svg | avif, bmp, gif, ico, jpg, png, tiff, webp |
| tiff | avif, bmp, gif, ico, jpg, png, webp |
| webp | avif, bmp, gif, ico, jpg, png, tiff |

**Áudio** (30)

| Entrada | Saídas `available` |
|---|---|
| flac | m4a, mp3, ogg, opus, wav |
| m4a | flac, mp3, ogg, opus, wav |
| mp3 | flac, m4a, ogg, opus, wav |
| ogg | flac, m4a, mp3, opus, wav |
| opus | flac, m4a, mp3, ogg, wav |
| wav | flac, m4a, mp3, ogg, opus |

**Vídeo** (60)

| Entrada | Saídas `available` |
|---|---|
| avi | avi, flac, gif, m4a, mkv, mov, mp3, mp4, ogg, opus, wav, webm |
| mkv | avi, flac, gif, m4a, mkv, mov, mp3, mp4, ogg, opus, wav, webm |
| mov | avi, flac, gif, m4a, mkv, mov, mp3, mp4, ogg, opus, wav, webm |
| mp4 | avi, flac, gif, m4a, mkv, mov, mp3, mp4, ogg, opus, wav, webm |
| webm | avi, flac, gif, m4a, mkv, mov, mp3, mp4, ogg, opus, wav, webm |

Como cada combinação é provada (mesmo código de produção, `ConverterHandler.execute`):
- arquivo de entrada gerado pelos próprios motores (HEIC: amostra versionada `fixtures/sample.heic`, pois a imagem não tem codificador HEVC);
- saída conferida pela assinatura real (`file_sniffing`), e mais: documentos → texto marcador presente; imagens → mesmas dimensões (ICO ≤ 256 px); áudio/vídeo → `ffprobe` com duração ± 0,35 s e faixas corretas; vídeo→GIF ≤ 480 px.
- os mesmos casos rodam como testes pytest parametrizados (`tests/engines/test_conversions.py`).

Mudanças em relação ao plano da Fase 1:
| Item | Mudança | Motivo |
|---|---|---|
| ImageMagick | libvips do Debian **inclui** o módulo `vips-magick`; todas as chamadas usam `VIPS_BLOCK_UNTRUSTED=1` (bloqueia magick, PDF, SVG, FITS, PPM, `.v` etc.) | Superfície de ataque (teste `test_imagemagick_and_untrusted_loaders_are_blocked`) |
| SVG | rasterizado por `rsvg-convert` (sandbox) após sanitização com `defusedxml` | o loader SVG do libvips é "untrusted" |
| Pandoc | **não usado** | LibreOffice cobre HTML/TXT→PDF; menos um motor |
| PDF → DOCX | LibreOffice (`writer_pdf_import`), com aviso de perda de layout (D9) | sem AGPL |
| Vídeo X → X | incluído (recodificar com resolução/qualidade/fps) | opções do PRD §6.2 só fazem sentido com recodificação |
| AVIF | `effort=2` | 12 MP: 46,8 s → 7,8 s com tamanho igual |
| MP4 só com áudio | reclassificado como M4A na inspeção (custo de áudio, 1 ficha) | conteúdo real manda |

Limitações exibidas ao usuário: PDF→DOCX perde layout; PDF escaneado não tem texto (sem OCR); XLS/XLSX→CSV só a 1ª planilha; HTML sem recursos externos; GIF animado → 1º quadro; vídeo→GIF ≤ 15 s, 480 px, 10 fps.

`planned` (não oferecidos): saída em HEVC/AV1/XviD como codecs, HEIC como saída, ImageMagick, OCR.

## 1. Registry de capacidades

- `tool_definitions` (ferramenta, custo em fichas, fila) + `tool_capabilities` (entrada → saída, `status`, motor, `options_schema`).
- Código: `backend/app/tools/registry.py` mapeia `(tool_id, input, output)` → handler. Na inicialização, a API **cruza** banco × código: capacidade `available` sem handler registrado é rebaixada para `planned` e gera alerta (impede expor algo não implementado).
- O frontend lista apenas o que a API devolve como `available`. `planned` pode aparecer como "em breve" (decisão de UI da Fase 5); `unsupported` nunca aparece.
- `options_schema` (JSON Schema) define opções permitidas (bitrate, resolução, fps…) com enums/limites fechados; o handler traduz para argumentos de template. Nenhum valor do usuário vira argumento livre.

## 2. Motores — verificação em 17/10/2026

Verificação empírica: `docker run python:3.12-slim` (Debian 13 "trixie") + `apt-get install` dos pacotes, amd64 (ARM64 em `§2.1`).

| Motor | Versão verificada | Licença | Uso comercial em SaaS | Observação |
|---|---|---|---|---|
| FFmpeg (pacote Debian) | 7.1.5 | build `--enable-gpl` → **GPL** como um todo ([ffmpeg.org/legal](https://ffmpeg.org/legal.html)) | Executado como programa separado no servidor, sem distribuição: obrigações de distribuição da GPL não são acionadas — **interpretação, não parecer jurídico** | Encoders presentes: `libx264`, `libx265`, `libvpx-vp9`, `libvpx`, `libaom-av1`, `libsvtav1`, `aac`, `libmp3lame`, `libopus`, `libvorbis`, `flac`, `alac`, `pcm_s16le`, `gif`, `mpeg4`. Decoders: h264, hevc, vp9, av1 (`libdav1d`). **Patentes** de H.264/HEVC/AAC: risco jurídico não avaliado (**NÃO VERIFICADO**) |
| LibreOffice (headless, `-nogui`) | 25.2.3.2 | MPL-2.0 | Sim | Writer + Calc são suficientes |
| Pandoc | 3.1.11.1 | GPL-2.0+ | Sim (programa separado) | Uso secundário (HTML/TXT) |
| libvips (`libvips-tools`) | 8.16.1 | LGPL-2.1+ | Sim | Testado: salvar AVIF, WEBP, TIFF, GIF, JPG; ler AVIF; **ler HEIC** com `libheif-plugin-libde265` (LGPL). Salvar HEIC **não** (sem encoder HEVC — e não é necessário: HEIC é só entrada) |
| Pillow | — | MIT-CMU (HPND) | Sim | Para ICO/BMP (saída). **Não testado nesta fase** |
| poppler-utils (`pdftotext`) | 25.03.0 | GPL-2.0+ | Sim (programa separado) | PDF → TXT |
| rembg | — | MIT ([GitHub](https://github.com/danielgatis/rembg)) — exige Python ≥ 3.11, < 3.14 | Sim (código) | Pesos têm licença própria (abaixo) |
| Modelos de fundo | U²-Net / `isnet-general-use`: **Apache-2.0** (LICENSE dos repositórios xuebinqin/U-2-Net e xuebinqin/DIS); BiRefNet: **MIT** (repo e HF `ZhengPeng7/BiRefNet`); **BRIA RMBG**: licença própria, **exige acordo pago para uso comercial** → **proibido** | | Usar `isnet-general-use` ou `birefnet-general-lite` (decidir por qualidade × CPU na Fase 3B) | |
| LaMa (inpainting) | — | código **Apache-2.0** (advimman/lama); pesos `smartywu/big-lama` e `Carve/LaMa-ONNX` marcados **apache-2.0** no Hugging Face | Sim pela licença dos pesos | ⚠️ O modelo foi treinado no dataset Places2, cujos termos de uso do dataset **não foram verificados**. Risco residual baixo, mas registrado. Alternativa de execução: ONNX em CPU |
| yt-dlp | — | **Unlicense** (domínio público); binários PyInstaller são GPLv3+ (usaremos via pip, não o binário) | Sim | Python ≥ 3.10; YouTube completo exige `yt-dlp-ejs` + runtime JS (deno recomendado); FFmpeg para juntar áudio/vídeo |
| pdf2docx (PDF → DOCX) | — | MIT, **mas depende de PyMuPDF (AGPL-3.0)** | ⚠️ AGPL em serviço de rede pode obrigar a oferecer o código-fonte do sistema que o incorpora | Ver decisão em `12` |
| ImageMagick | — | — | — | **Fora do MVP** (libvips + Pillow cobrem) |

### 2.1 ARM64 (hospedagem Oracle Ampere)

Teste emulado (QEMU, `docker run --platform linux/arm64 python:3.12-slim`, `uname -m` = `aarch64`) em 17/10/2026:

| Teste | amd64 | arm64 |
|---|---|---|
| libvips salvar AVIF / WEBP / TIFF / GIF / JPG | OK | OK |
| libvips ler AVIF | OK | OK |
| libvips ler HEIC (`libheif-plugin-libde265`) | OK | **não testado** |
| FFmpeg H.264 + AAC (MP4) | OK | OK |
| FFmpeg VP9 + Opus (WEBM) | OK | OK |
| LibreOffice, Pandoc, pdftotext | instalam e rodam | **não testado** |
| `onnxruntime` (wheels aarch64) | — | **NÃO VERIFICADO** (Fase 3B) |

Emulação comprova disponibilidade e funcionamento, **não desempenho**: tempos só valem medidos em ARM real (Fase 6).

## 3. Combinações candidatas (lançamento, PRD §6.2)

Legenda de status inicial após a Fase 1: todas `planned`. Coluna "Prova" = como o teste da Fase 3 comprova a combinação.

### Documentos (`worker-light`, limite 25 MB)
| Entrada → Saída | Motor | Prova |
|---|---|---|
| DOCX, DOC, ODT, RTF, TXT, HTML → PDF | LibreOffice | saída começa com `%PDF`, `pdfinfo` lê nº de páginas ≥ 1, texto extraído contém marcador do arquivo de teste |
| DOC → DOCX | LibreOffice | ZIP válido com `word/document.xml`; texto marcador preservado |
| PDF → TXT | `pdftotext` | texto marcador presente (aviso: PDF escaneado não tem texto — OCR fora do MVP) |
| PDF → DOCX | ✅ LibreOffice (`writer_pdf_import`; decisão D9 — sem AGPL) | ZIP válido com `word/document.xml` e texto marcador; **aviso obrigatório de perda de layout** na UI |
| XLSX, XLS → CSV | LibreOffice Calc | CSV com as células do teste (UTF-8, separador definido) |
| CSV → XLSX | LibreOffice Calc | abre no Calc com as mesmas células |

HTML de entrada: renderizado sem acesso à rede (worker isolado); imagens remotas não carregam — documentar.

### Imagens (`worker-light`, limite 20 MB + teto de pixels)
| Entrada | Saída | Motor | Prova |
|---|---|---|---|
| JPG, PNG, WEBP, AVIF, GIF, BMP, TIFF, HEIC/HEIF, SVG | JPG, PNG, WEBP, AVIF, GIF, TIFF | libvips | saída reabre no libvips com mesmas dimensões (ou redimensionadas conforme opção) |
| idem | BMP, ICO | Pillow | reabre no Pillow; ICO com tamanhos padrão (16–256) |
| ICO | (entrada) | Pillow | — |

GIF animado → formatos estáticos usa o 1º quadro (avisar). SVG: sanitizado e rasterizado (`08` T6).

### Áudio (`worker-media`, limite 50 MB)
| Entrada | Saída | Encoder | Prova |
|---|---|---|---|
| MP3, WAV, OGG, M4A/AAC, FLAC, OPUS | MP3 | `libmp3lame` | `ffprobe`: codec, duração ± 0,1 s, canais/taxa pedidos |
| idem | WAV | `pcm_s16le` | idem |
| idem | OGG | `libvorbis` | idem |
| idem | M4A (AAC) | `aac` (nativo) | idem |
| idem | FLAC | `flac` | idem |
| idem | OPUS | `libopus` | idem |

Opções: bitrate (lista fechada), taxa de amostragem (8000–48000 em lista), canais (1/2).

### Vídeo (`worker-media`, limite ✅ 95 MB e 10 min — D10; custo 2 fichas — D1)
| Entrada | Saída | Codecs | Prova |
|---|---|---|---|
| MP4, WEBM, MKV, MOV, AVI | MP4 | H.264 (`libx264`) + AAC | `ffprobe` codec/resolução/duração |
| idem | WEBM | VP9 (`libvpx-vp9`) + Opus | idem (VP9 é lento em CPU: medir) |
| idem | MKV | H.264 + AAC (ou cópia de streams quando compatível) | idem |
| idem | MOV | H.264 + AAC | idem |
| idem | AVI | MPEG-4 Part 2 (`mpeg4`) + MP3 | idem |
| vídeo → áudio | MP3/M4A/WAV/OGG/OPUS/FLAC | como Áudio | idem |
| vídeo → GIF | GIF | `palettegen`/`paletteuse` | limite de duração (ex.: 15 s) e fps ≤ 15 |

Opções: resolução (lista: 360p/480p/720p/1080p, nunca acima da original), qualidade (CRF em lista fechada), fps (lista). Preset de encoder fixo (`veryfast`) para caber na CPU.

HEVC, AV1, XviD/DivX como **codecs de saída**: `planned` (o FFmpeg verificado tem `libx265`, `libsvtav1`, `mpeg4`, mas custo de CPU e patentes não foram avaliados).

### IA (`worker-ai`)
| Ferramenta | Entrada | Saída | Prova |
|---|---|---|---|
| `background_remover` | JPG, PNG, WEBP | PNG transparente; opcional fundo sólido (JPG/PNG) | PNG com canal alfa; máscara não vazia em imagem de teste sintética |
| `object_remover` | JPG, PNG, WEBP + máscara do pincel | mesmo formato | região mascarada alterada, restante idêntico (diferença fora da máscara ≈ 0) |

### Baixador (`worker-download`)
| Entrada | Saída | Prova |
|---|---|---|
| URL pública (qualquer site suportado pelo yt-dlp) | MP4 (vídeo) / M4A ou MP3 (áudio) conforme opções **reais** retornadas | teste com servidor HTTP de fixture servindo um MP4 gerado (não depende de plataformas externas no CI); como o SSRF bloqueia IPs privados, o fixture usa uma allowlist que **só existe com `APP_ENV=test`** e há teste garantindo que ela é ignorada em `production`; teste manual com plataformas reais documentado |

## 4. Ferramentas de IA (Fase 3B, 18/10/2026)

| Item | Escolha | Licença (verificada 18/10/2026) | Fonte |
|---|---|---|---|
| Runtime | ONNX Runtime 1.31.0 (CPU) | MIT | LICENSE do repositório microsoft/onnxruntime; wheels oficiais cp312 **x86_64 e aarch64** no PyPI (fecha a pendência ARM da Fase 1) |
| Removedor de fundo | IS-Net general-use (`isnet-general-use.onnx`, 170 MB) | pesos Apache-2.0 (LICENSE de xuebinqin/DIS) | arquivo do release oficial do rembg (MIT); **MD5 confere com o publicado pelo rembg** (`fc16ebd8…`); SHA-256 fixado no build |
| Removedor de objetos | LaMa big-lama, porte ONNX `lama_fp32.onnx` (198 MB, entrada fixa 512×512) | Apache-2.0 (card Carve/LaMa-ONNX; código advimman/lama Apache-2.0) | Hugging Face Carve/LaMa-ONNX; sem checksum publicado → SHA-256 medido e fixado no build |
| Implementação | camada própria sobre onnxruntime (pré/pós-processamento do IS-Net igual ao `DisSession` do rembg) | — | evita dependências pesadas do rembg (scikit-image, scipy, pymatting) |
| Descartado | BRIA RMBG | exige acordo pago para uso comercial | — |

Risco residual: termos do dataset de treino do LaMa (Places2) **NÃO VERIFICADO**.

Combinações `available` (todas verificadas por `python -m app.tools.ai.verify` dentro do `worker-ai`, 18/18):

| Ferramenta | Entradas | Saídas |
|---|---|---|
| `background_remover` | JPG, PNG, WEBP | PNG e WEBP (transparente ou cor sólida), JPG (cor sólida; padrão branco) |
| `object_remover` | JPG, PNG, WEBP + máscara PNG | PNG, WEBP, JPG |

Como cada uma é provada (imagens sintéticas de geometria conhecida): fundo → alfa alto no disco e baixo nos cantos, cor sólida aplicada; objeto → pixels fora da máscara **idênticos em PNG** (JPG/WEBP com perda: tolerância de 40 níveis), área marcada deixa de parecer o objeto.

Comportamento:
- o modelo é carregado uma vez por processo do worker (`lru_cache`) e reutilizado;
- o removedor de objetos processa um recorte ao redor da máscara (preserva detalhe em fotos grandes) e só cola pixels **dentro** da máscara;
- rotação EXIF aplicada; **metadados (EXIF/GPS) removidos** da saída (teste);
- máscara: segundo upload do mesmo dono, PNG, mesmo tamanho da imagem (ou h×w para fotos com EXIF girado);
- aceite "tenho direito de editar esta imagem" obrigatório na criação do job e gravado em `terms_acceptances` na mesma transação da cobrança. A estimativa de custo não exige o aceite (o custo aparece antes).

## 5. Baixador de vídeos (Fase 3C, 18/10/2026)

| Item | Escolha | Licença |
|---|---|---|
| Extrator | yt-dlp 2026.8.19 (`[default,deno]`) atrás de `VideoExtractor` | Unlicense |
| JS runtime (YouTube) | deno 2.9.7 + yt-dlp-ejs 0.8.0 | MIT / Unlicense+MIT+ISC |
| Junção/extração | FFmpeg (mesma build do `worker-media`) | GPL (programa separado) |
| Metadados de áudio | mutagen 1.48.1 (dependência do yt-dlp) | GPL-2.0+ (ver `08` §3.4) |

Capacidades `available` (verificação real `python -m app.tools.downloader.verify`, pela internet via proxy de egresso, 3/3):

| Entrada | Saída | Prova |
|---|---|---|
| URL pública | MP4 (qualidade escolhida entre as alturas **reais** listadas) | NASA/JWST no Wikimedia Commons: alturas 240/360/480/1080 oferecidas; pedido 480 → recebido 480 |
| URL pública | M4A, MP3 (somente áudio) | NASA/Apollo 15 no Wikimedia Commons: faixa de áudio presente na saída |

URLs escolhidas: **domínio público (NASA)**, servidas pelo Wikimedia Commons — públicas, sem login, sem DRM, acervo estável, e baixá-las não viola termos de nenhuma plataforma. Nenhum teste automatizado depende de YouTube/Instagram/TikTok.

Regras:
- consulta gratuita primeiro (opções reais); a cobrança só acontece no job;
- links diretos de arquivo (sem metadados no extrator) são **medidos com ffprobe** pelo proxy; sem duração mensurável → recusado antes de cobrar (não inventamos preço);
- custo D1: 1 ficha; 2 fichas se a duração real > 2 min;
- limites (configuráveis): 20 min e 300 MB (padrão adotado; PRD não definia);
- erros: privado/login/DRM/indisponível/ao vivo/playlist → consulta recusada (sem custo); bloqueio da plataforma, arquivo maior que o previsto, vídeo sem áudio quando se pediu áudio → erro do sistema (ficha devolvida); redirect para endereço proibido → erro do usuário.
