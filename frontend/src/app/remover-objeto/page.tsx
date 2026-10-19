import type { Metadata } from "next";
import { AdSlot } from "@/components/AdSlot";
import { ToolInfo } from "@/components/ToolInfo";
import Client from "./Client";

export const metadata: Metadata = {
  title: "Removedor de objetos em fotos online",
  description: "Pinte sobre o que quer tirar da foto — uma pessoa ao fundo, um fio, uma mancha — e a IA preenche a área.",
  alternates: { canonical: "/remover-objeto" },
  openGraph: { title: "Removedor de objetos em fotos online", description: "Pinte sobre o que quer tirar da foto — uma pessoa ao fundo, um fio, uma mancha — e a IA preenche a área.", url: "/remover-objeto", locale: "pt_BR", type: "website" },
};

export default function Page() {
  return (
    <>
      {/* min-h: the tool UI renders on the client; reserving the viewport keeps the info below from shifting */}
      <div className="min-h-screen">
        <Client />
      </div>
      <ToolInfo
        path="/remover-objeto"
        name="Removedor de objetos"
        description="Pinte sobre o que quer tirar da foto — uma pessoa ao fundo, um fio, uma mancha — e a IA preenche a área."
        sections={[{"title": "Como usar", "body": ["Envie a foto, pinte com o pincel sobre o objeto que quer remover (com uma pequena folga ao redor) e confirme. O restante da imagem não é alterado: só a área pintada é preenchida.", "Use apenas em imagens suas ou que você tem autorização para editar. A ferramenta não deve ser usada para remover autoria, marcas de licença ou créditos de terceiros."]}, {"title": "Limitações", "body": ["O preenchimento é estimado pela IA a partir do entorno. Objetos grandes ou em áreas com muitos detalhes podem deixar marcas; o resultado não é perfeito em todos os casos."]}]}
        faq={[{"q": "Preciso declarar algo?", "a": "Sim. Antes de processar, você confirma que tem direito de editar a imagem. A confirmação fica registrada."}, {"q": "Quanto custa?", "a": "1 ficha por imagem processada com sucesso. Falhas nossas devolvem a ficha."}, {"q": "Funciona no celular?", "a": "Sim, o pincel funciona com toque. A rotação das fotos do celular é respeitada."}]}
      />
      <AdSlot slot="tool_bottom" />
    </>
  );
}
