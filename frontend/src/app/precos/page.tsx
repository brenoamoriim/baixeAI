import type { Metadata } from "next";
import { ToolInfo } from "@/components/ToolInfo";
import Client from "./Client";

export const metadata: Metadata = {
  title: "Preços: planos Pro, Premium, Vitalício e fichas avulsas",
  description: "Conta gratuita com 5 fichas por dia, plano Pro (300 fichas), Premium (800 fichas), Vitalício e pacotes de 10 fichas por ferramenta. Pagamento via Mercado Pago.",
  alternates: { canonical: "/precos" },
  openGraph: { title: "Preços: planos Pro, Premium, Vitalício e fichas avulsas", description: "Conta gratuita com 5 fichas por dia, plano Pro (300 fichas), Premium (800 fichas), Vitalício e pacotes de 10 fichas por ferramenta. Pagamento via Mercado Pago.", url: "/precos", locale: "pt_BR", type: "website" },
};

export default function Page() {
  return (
    <>
      {/* min-h: the tool UI renders on the client; reserving the viewport keeps the info below from shifting */}
      <div className="min-h-screen">
        <Client />
      </div>
      <ToolInfo
        path="/precos"
        name="Preços"
        description="Conta gratuita com 5 fichas por dia, plano Pro (300 fichas), Premium (800 fichas), Vitalício e pacotes de 10 fichas por ferramenta. Pagamento via Mercado Pago."
        sections={[{"title": "Como as fichas funcionam", "body": ["Cada uso bem-sucedido de uma ferramenta consome fichas. As diárias da conta gratuita renovam à meia-noite (horário de Brasília) e não acumulam. As do plano valem pelo ciclo de 1 mês e também não acumulam; ao trocar de plano, as que sobraram são somadas ao novo.", "Fichas avulsas valem 90 dias e só na ferramenta comprada. O plano Vitalício não conta fichas, mas tem limites de uso justo."]}, {"title": "Pagamento e reembolso", "body": ["Pagamento pelo Mercado Pago com Pix, cartão de crédito ou débito. As fichas só são liberadas após a confirmação do Mercado Pago. Reembolso em até 7 dias da compra, proporcional às fichas não usadas, pelo suporte."]}]}
        faq={[{"q": "O plano renova sozinho?", "a": "No cartão de crédito, sim, até você cancelar. No Pix ou débito a renovação é manual e avisamos por e-mail antes do vencimento."}, {"q": "Posso cancelar?", "a": "Sim, quando quiser. Você mantém o plano até o fim do ciclo pago."}, {"q": "O que é uso justo do Vitalício?", "a": "Até 2 processamentos simultâneos e 50 por dia, com os mesmos limites de tamanho dos outros planos. Os limites podem ser revisados a cada 6 meses, com aviso."}]}
      />
    </>
  );
}
