const TOOLS = [
  { href: "/conversores", title: "Conversores de arquivos",
    words: "converter conversor pdf word docx doc odt rtf txt html xlsx xls csv planilha jpg jpeg png webp avif gif bmp tiff ico heic heif svg imagem foto mp3 wav ogg m4a aac flac opus audio mp4 webm mkv mov avi video extrair audio gif" },
  { href: "/removedor-de-fundo", title: "Removedor de fundo", words: "remover tirar fundo background recortar transparente png" },
  { href: "/remover-objeto", title: "Removedor de objetos", words: "remover apagar objeto pessoa mancha fio limpar foto editar" },
  { href: "/baixar-videos", title: "Baixador de vídeos", words: "baixar download video link url salvar mp4 mp3 audio" },
  { href: "/precos", title: "Planos e fichas", words: "preco precos plano planos fichas pro premium vitalicio comprar pagar pix" },
];

function normalize(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** Ranks tools by how many query words match their keywords (accent-insensitive). */
export function searchTools(query: string): { href: string; title: string }[] {
  const words = normalize(query).split(/[^a-z0-9]+/).filter((w) => w.length >= 2 && !["para", "de", "em", "um", "uma"].includes(w));
  if (!words.length) return [];
  return TOOLS.map((t) => {
    const haystack = normalize(`${t.title} ${t.words}`);
    return { t, score: words.filter((w) => haystack.includes(w)).length };
  })
    .filter((r) => r.score > 0)
    .sort((a, b) => b.score - a.score)
    .map(({ t }) => ({ href: t.href, title: t.title }));
}
