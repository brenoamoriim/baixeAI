"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatBRL, formatDate, formatDateTime } from "@/lib/format";
import { Alert, Button, Card } from "./ui";

type Subscription = {
  plan: string;
  plan_name: string;
  status: "active" | "past_due";
  renewal_mode: "card_auto" | "manual" | "admin";
  period_end: string | null;
  cancel_at_period_end: boolean;
  next_plan: string | null;
};
type PaymentRow = {
  id: string;
  purpose: string;
  amount_cents: number;
  status: string;
  method: string | null;
  created_at: string;
  fulfilled: boolean;
  refunded_amount_cents: number;
};

const PURPOSE: Record<string, string> = { package: "Fichas avulsas", plan_cycle: "Plano mensal", lifetime: "Vitalício" };
const STATUS: Record<string, string> = {
  pending: "Aguardando confirmação", approved: "Aprovado", rejected: "Recusado", cancelled: "Cancelado",
  expired: "Expirado", refunded: "Reembolsado", charged_back: "Contestado (chargeback)", in_mediation: "Em disputa",
};
const METHOD: Record<string, string> = { bank_transfer: "Pix", credit_card: "Crédito", debit_card: "Débito", account_money: "Saldo MP" };

function fetchBilling() {
  return Promise.all([
    api<{ subscription: Subscription | null; lifetime: boolean }>("/subscription"),
    api<{ payments: PaymentRow[] }>("/payments"),
  ]);
}

export function BillingPanel() {
  const [sub, setSub] = useState<{ subscription: Subscription | null; lifetime: boolean } | null>(null);
  const [payments, setPayments] = useState<PaymentRow[]>([]);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const [s, p] = await fetchBilling();
    setSub(s);
    setPayments(p.payments);
  }

  useEffect(() => {
    let active = true;
    fetchBilling()
      .then(([s, p]) => {
        if (!active) return;
        setSub(s);
        setPayments(p.payments);
      })
      .catch(() => active && setMessage({ kind: "error", text: "Não foi possível carregar a assinatura." }));
    return () => {
      active = false;
    };
  }, []);

  async function act(path: string, body?: unknown, confirmText?: string) {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusy(true);
    setMessage(null);
    try {
      const res = await api<{ message?: string; redirect_url?: string }>(path, { method: "POST", body });
      if (res.redirect_url) {
        window.location.assign(res.redirect_url);
        return;
      }
      setMessage({ kind: "success", text: res.message ?? "Feito." });
      await load();
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "Falha. Tente novamente." });
    } finally {
      setBusy(false);
    }
  }

  const s = sub?.subscription;
  const other = s?.plan === "pro" ? "premium" : "pro";

  return (
    <>
      <Card title="Assinatura">
        {message && <div className="mb-3"><Alert kind={message.kind}>{message.text}</Alert></div>}
        {!sub ? (
          <p>Carregando…</p>
        ) : sub.lifetime ? (
          <p>Você tem o plano Vitalício.</p>
        ) : !s ? (
          <p className="text-slate-700">
            Você está no plano gratuito. <Link href="/precos" className="font-semibold text-blue-700 underline">Ver planos</Link>
          </p>
        ) : (
          <div className="flex flex-col gap-3 text-sm">
            <p>
              Plano <strong>{s.plan_name}</strong> —{" "}
              {s.status === "past_due"
                ? "pagamento da renovação pendente (tolerância de 3 dias)"
                : s.cancel_at_period_end
                  ? `cancelado; vale até ${s.period_end ? formatDate(s.period_end) : "o fim do ciclo"}`
                  : `${s.renewal_mode === "card_auto" ? "renova no cartão" : "renovação manual"} em ${s.period_end ? formatDate(s.period_end) : "—"}`}
            </p>
            {s.next_plan && <p>Troca agendada para o plano {s.next_plan} no próximo ciclo (as fichas que sobrarem são somadas).</p>}
            <div className="flex flex-wrap gap-2">
              {s.renewal_mode === "manual" && !s.cancel_at_period_end && (
                <Button type="button" disabled={busy} onClick={() => act("/subscription/renew")}>Renovar agora</Button>
              )}
              {!s.cancel_at_period_end && (
                <Button type="button" variant="secondary" disabled={busy} onClick={() => act("/subscription/change", { plan: other })}>
                  Trocar para {other === "pro" ? "Pro" : "Premium"} no próximo ciclo
                </Button>
              )}
              {!s.cancel_at_period_end && (
                <Button type="button" variant="secondary" disabled={busy}
                        onClick={() => act("/subscription/cancel", undefined, "Cancelar a assinatura? Você mantém o plano até o fim do ciclo pago.")}>
                  Cancelar assinatura
                </Button>
              )}
            </div>
          </div>
        )}
      </Card>

      <Card title="Histórico de compras">
        {payments.length === 0 ? (
          <p className="text-slate-700">Nenhuma compra ainda.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Compras</caption>
            <thead className="text-slate-600">
              <tr><th scope="col" className="py-2">Data</th><th scope="col">Item</th><th scope="col">Valor</th><th scope="col">Forma</th><th scope="col">Situação</th></tr>
            </thead>
            <tbody>
              {payments.map((p) => (
                <tr key={p.id} className="border-t border-slate-100">
                  <td className="py-2">{formatDateTime(p.created_at)}</td>
                  <td>{PURPOSE[p.purpose] ?? p.purpose}</td>
                  <td>{formatBRL(p.amount_cents)}{p.refunded_amount_cents ? ` (reembolsado ${formatBRL(p.refunded_amount_cents)})` : ""}</td>
                  <td>{p.method ? (METHOD[p.method] ?? p.method) : "—"}</td>
                  <td>{STATUS[p.status] ?? p.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="mt-3 text-xs text-slate-600">
          Reembolso: em até 7 dias da compra, proporcional às fichas não usadas. Peça pelo suporte.
        </p>
      </Card>
    </>
  );
}
