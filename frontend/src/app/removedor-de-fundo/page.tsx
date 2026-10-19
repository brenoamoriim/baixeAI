import type { Metadata } from "next";
import { AdSlot } from "@/components/AdSlot";
import { ToolInfo } from "@/components/ToolInfo";
import Client from "./Client";

export const metadata: Metadata = {
  title: "Remover fundo de imagem online — PNG transparente",
  description: "Remova o fundo de fotos JPG, PNG e WEBP com inteligência artificial e baixe em PNG transparente ou com fundo de cor sólida.",
  alternates: { canonical: "/removedor-de-fundo" },
  openGraph: { title: "Remover fundo de imagem online — PNG transparente", description: "Remova o fundo de fotos JPG, PNG e WEBP com inteligência artificial e baixe em PNG transparente ou com fundo de cor sólida.", url: "/removedor-de-fundo", locale: "pt_BR", type: "website" },
};

export default function Page() {
  return (
    <>
      {/* min-h: the tool UI renders on the client; reserving the viewport keeps the info below from shifting */}
      <div className="min-h-screen">
        <Client />
      </div>
      <ToolInfo
        path="/removedor-de-fundo"
        name="Removedor de fundo"
        description="Remova o fundo de fotos JPG, PNG e WEBP com inteligência artificial e baixe em PNG transparente ou com fundo de cor sólida."
        sections={[{"title": "Como funciona", "body": ["Envie a foto, escolha fundo transparente ou uma cor sólida e baixe o resultado em PNG, WEBP ou JPG. Uma comparação de antes e depois aparece na própria página.", "O recorte é feito por um modelo de IA que roda nos nossos servidores: a imagem não é enviada para serviços de terceiros."]}, {"title": "Quando o resultado é melhor", "body": ["Fotos com o assunto bem separado do fundo (produto sobre mesa, pessoa contra parede) dão os melhores recortes. Cabelos finos, transparências e fundos parecidos com o assunto podem ficar imperfeitos."]}]}
        faq={[{"q": "Qual formato baixar?", "a": "PNG ou WEBP mantêm a transparência. JPG não suporta transparência, então o fundo vira a cor escolhida (branco por padrão)."}, {"q": "Quanto custa?", "a": "1 ficha por imagem processada com sucesso."}, {"q": "A foto perde qualidade?", "a": "A resolução original é mantida. Os metadados da foto (como GPS) são removidos."}]}
      />
      <AdSlot slot="tool_bottom" />
    </>
  );
}
