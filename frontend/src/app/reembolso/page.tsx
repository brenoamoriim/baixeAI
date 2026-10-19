import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = { title: "Política de reembolso", alternates: { canonical: "/reembolso" } };

export default function Page() {
  return <LegalPage title="Política de reembolso" updated="19/10/2026" sections={[{"title": "Prazo e valor", "body": ["Você pode pedir reembolso em até 7 dias da compra. O valor devolvido é proporcional às fichas não usadas da compra (por exemplo, se sobraram 6 de 10 fichas, devolvemos 60% do valor)."]}, {"title": "Como pedir", "body": ["Peça pela página de Contato informando o e-mail da conta. O reembolso é feito pelo Mercado Pago, na mesma forma de pagamento; as fichas não usadas daquela compra são removidas."]}, {"title": "Plano Vitalício", "body": ["Em até 7 dias da compra, o reembolso do Vitalício é integral e o acesso vitalício é encerrado. Esta regra está pendente de revisão jurídica."]}, {"title": "Contestações (chargeback)", "body": ["Se um pagamento for contestado junto ao banco ou ao Mercado Pago, as fichas restantes daquela compra são removidas e a conta pode ser analisada."]}]} />;
}
