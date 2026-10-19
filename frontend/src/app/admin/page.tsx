"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, TextField } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatBRL, formatDateTime, toolName } from "@/lib/format";
import { useMe } from "@/lib/useMe";

// The backend enforces admin role + password re-auth on every sensitive route; this UI only
// collects the password (kept in memory, never stored) and shows the server's answer.

type Notice = { kind: "success" | "error"; text: string } | null;
type Ctx = { password: string; run: (fn: () => Promise<{ message?: string } | unknown>) => Promise<boolean> };
const AdminCtx = createContext<Ctx>({ password: "", run: async () => false });

function useAdminData<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    api<T>(path)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar."));
  }, [path]);
  useEffect(reload, [reload]);
  return { data, error, reload };
}

function Loading({ error }: { error: string | null }) {
  return error ? <Alert kind="error">{error}</Alert> : <p>Carregando…</p>;
}

const th = "py-2 pr-3 font-medium";
const td = "py-2 pr-3 align-top";

// ---------------------------------------------------------------- sections

type Overview = {
  users: number;
  active_subscriptions: number;
  lifetime: number;
  revenue_30d_cents: number;
  pending_payments: number;
  jobs_24h: { tool_id: string; status: string; count: number }[];
  failures_24h: { tool_id: string; error_class: string | null; error_code: string | null; count: number }[];
};

function OverviewSection() {
  const { data, error } = useAdminData<Overview>("/admin/overview");
  if (!data) return <Loading error={error} />;
  const stats = [
    ["Usuários", data.users],
    ["Assinaturas ativas", data.active_subscriptions],
    ["Vitalícios", data.lifetime],
    ["Receita líquida (30 dias)", formatBRL(data.revenue_30d_cents)],
    ["Pagamentos pendentes", data.pending_payments],
  ];
  return (
    <div className="flex flex-col gap-4">
      <dl className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {stats.map(([k, v]) => (
          <div key={k} className="rounded-md border border-slate-200 p-3">
            <dt className="text-xs text-slate-600">{k}</dt>
            <dd className="text-xl font-semibold">{v}</dd>
          </div>
        ))}
      </dl>
      <h3 className="font-semibold">Processamentos (24 h)</h3>
      <table className="text-left text-sm">
        <thead><tr><th className={th}>Ferramenta</th><th className={th}>Situação</th><th className={th}>Qtd.</th></tr></thead>
        <tbody>
          {data.jobs_24h.map((j) => (
            <tr key={`${j.tool_id}-${j.status}`} className="border-t border-slate-100">
              <td className={td}>{toolName(j.tool_id)}</td><td className={td}>{j.status}</td><td className={td}>{j.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3 className="font-semibold">Principais falhas (24 h)</h3>
      {data.failures_24h.length === 0 ? <p className="text-sm">Nenhuma falha.</p> : (
        <table className="text-left text-sm">
          <thead><tr><th className={th}>Ferramenta</th><th className={th}>Classe</th><th className={th}>Código</th><th className={th}>Qtd.</th></tr></thead>
          <tbody>
            {data.failures_24h.map((f) => (
              <tr key={`${f.tool_id}-${f.error_class}-${f.error_code}`} className="border-t border-slate-100">
                <td className={td}>{toolName(f.tool_id)}</td><td className={td}>{f.error_class}</td>
                <td className={td}>{f.error_code}</td><td className={td}>{f.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

type AdminTool = { id: string; name: string; enabled: boolean; credit_cost: number; dev_only: boolean };

function ToolsSection() {
  const { run } = useContext(AdminCtx);
  const { data, error, reload } = useAdminData<{ tools: AdminTool[] }>("/admin/tools");
  const { password } = useContext(AdminCtx);
  if (!data) return <Loading error={error} />;
  async function patch(id: string, body: object) {
    if (await run(() => api(`/admin/tools/${id}`, { method: "PATCH", body: { ...body, confirm_password: password } }))) reload();
  }
  return (
    <table className="w-full text-left text-sm">
      <thead><tr><th className={th}>Ferramenta</th><th className={th}>Ativa</th><th className={th}>Custo (fichas)</th></tr></thead>
      <tbody>
        {data.tools.map((t) => (
          <tr key={t.id} className="border-t border-slate-100">
            <td className={td}>{t.name} {t.dev_only && <Badge>dev</Badge>}</td>
            <td className={td}>
              <Button variant="secondary" className="px-2 py-1" onClick={() => patch(t.id, { enabled: !t.enabled })}>
                {t.enabled ? "Ativa — desativar" : "Inativa — ativar"}
              </Button>
            </td>
            <td className={td}>
              <NumberEdit label={`Custo de ${t.name}`} value={t.credit_cost} min={1} max={100}
                onSave={(v) => patch(t.id, { credit_cost: v })} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function NumberEdit({ label, value, min, max, onSave }: {
  label: string; value: number; min: number; max: number; onSave: (v: number) => void;
}) {
  const [v, setV] = useState(String(value));
  return (
    <span className="inline-flex items-center gap-2">
      <input aria-label={label} type="number" min={min} max={max} value={v} onChange={(e) => setV(e.target.value)}
        className="w-28 rounded border border-slate-300 px-2 py-1" />
      <Button variant="secondary" className="px-2 py-1" disabled={String(value) === v} onClick={() => onSave(Number(v))}>
        Salvar
      </Button>
    </span>
  );
}

type AdminCapability = { id: string; category: string; input: string; output: string; status: string; engine: string | null };

function CapabilitiesSection() {
  const { run, password } = useContext(AdminCtx);
  const [tool, setTool] = useState("converter");
  const { data, error, reload } = useAdminData<{ capabilities: AdminCapability[] }>(`/admin/capabilities?tool_id=${tool}`);
  async function setStatus(id: string, status: string) {
    if (await run(() => api(`/admin/capabilities/${id}`, { method: "PATCH", body: { status, confirm_password: password } })))
      reload();
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-slate-700">
        Só é possível marcar como <strong>available</strong> combinações aprovadas na verificação automática (o servidor recusa as demais).
      </p>
      <label className="text-sm">
        Ferramenta{" "}
        <select value={tool} onChange={(e) => setTool(e.target.value)} className="rounded border border-slate-300 px-2 py-1">
          {["converter", "background_remover", "object_remover", "video_downloader"].map((t) => (
            <option key={t} value={t}>{toolName(t)}</option>
          ))}
        </select>
      </label>
      {!data ? <Loading error={error} /> : (
        <table className="w-full text-left text-sm">
          <thead><tr><th className={th}>Categoria</th><th className={th}>Entrada → saída</th><th className={th}>Motor</th><th className={th}>Estado</th></tr></thead>
          <tbody>
            {data.capabilities.map((c) => (
              <tr key={c.id} className="border-t border-slate-100">
                <td className={td}>{c.category}</td>
                <td className={td}>{c.input} → {c.output}</td>
                <td className={td}>{c.engine}</td>
                <td className={td}>
                  <select aria-label={`Estado de ${c.input} para ${c.output}`} value={c.status}
                    onChange={(e) => setStatus(c.id, e.target.value)} className="rounded border border-slate-300 px-1 py-0.5">
                    <option value="available">available</option>
                    <option value="planned">planned</option>
                    <option value="unsupported">unsupported</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

type CostRule = { id: string; tool_id: string; category: string | null; min_duration_seconds: number | null; cost: number; active: boolean };

function CostRulesSection() {
  const { run, password } = useContext(AdminCtx);
  const { data, error, reload } = useAdminData<{ rules: CostRule[] }>("/admin/cost-rules");
  if (!data) return <Loading error={error} />;
  async function patch(id: string, body: object) {
    if (await run(() => api(`/admin/cost-rules/${id}`, { method: "PATCH", body: { ...body, confirm_password: password } }))) reload();
  }
  return data.rules.length === 0 ? <p className="text-sm">Nenhuma regra.</p> : (
    <table className="w-full text-left text-sm">
      <thead><tr><th className={th}>Ferramenta</th><th className={th}>Condição</th><th className={th}>Custo</th><th className={th}>Ativa</th></tr></thead>
      <tbody>
        {data.rules.map((r) => (
          <tr key={r.id} className="border-t border-slate-100">
            <td className={td}>{toolName(r.tool_id)}</td>
            <td className={td}>
              {r.category ?? "qualquer"}{r.min_duration_seconds != null && `, duração ≥ ${r.min_duration_seconds}s`}
            </td>
            <td className={td}><NumberEdit label="Custo da regra" value={r.cost} min={1} max={100} onSave={(v) => patch(r.id, { cost: v })} /></td>
            <td className={td}>
              <Button variant="secondary" className="px-2 py-1" onClick={() => patch(r.id, { active: !r.active })}>
                {r.active ? "Ativa — desativar" : "Inativa — ativar"}
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

type Catalog = {
  plans: { code: string; name: string; kind: string; price_cents: number; credits_per_cycle: number | null; active: boolean }[];
  packages: { code: string; tool_id: string; credits: number; price_cents: number; validity_days: number; active: boolean }[];
};

function CatalogSection() {
  const { run, password } = useContext(AdminCtx);
  const { data, error, reload } = useAdminData<Catalog>("/admin/catalog");
  if (!data) return <Loading error={error} />;
  async function patch(path: string, body: object) {
    if (await run(() => api(path, { method: "PATCH", body: { ...body, confirm_password: password } }))) reload();
  }
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-slate-700">Preços em centavos (ex.: 1990 = R$ 19,90). Assinaturas no cartão existentes mantêm o valor contratado.</p>
      <table className="w-full text-left text-sm">
        <caption className="mb-1 text-left font-semibold">Planos</caption>
        <thead><tr><th className={th}>Plano</th><th className={th}>Preço</th><th className={th}>Fichas/ciclo</th><th className={th}>Venda</th></tr></thead>
        <tbody>
          {data.plans.map((p) => (
            <tr key={p.code} className="border-t border-slate-100">
              <td className={td}>{p.name} <span className="text-slate-500">({formatBRL(p.price_cents)})</span></td>
              <td className={td}><NumberEdit label={`Preço de ${p.name}`} value={p.price_cents} min={100} max={1000000}
                onSave={(v) => patch(`/admin/plans/${p.code}`, { price_cents: v })} /></td>
              <td className={td}>{p.credits_per_cycle == null ? "—" : (
                <NumberEdit label={`Fichas de ${p.name}`} value={p.credits_per_cycle} min={1} max={100000}
                  onSave={(v) => patch(`/admin/plans/${p.code}`, { credits_per_cycle: v })} />)}</td>
              <td className={td}><Button variant="secondary" className="px-2 py-1"
                onClick={() => patch(`/admin/plans/${p.code}`, { active: !p.active })}>{p.active ? "À venda — pausar" : "Pausado — vender"}</Button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <table className="w-full text-left text-sm">
        <caption className="mb-1 text-left font-semibold">Pacotes avulsos</caption>
        <thead><tr><th className={th}>Pacote</th><th className={th}>Preço</th><th className={th}>Venda</th></tr></thead>
        <tbody>
          {data.packages.map((p) => (
            <tr key={p.code} className="border-t border-slate-100">
              <td className={td}>{toolName(p.tool_id)} — {p.credits} fichas, {p.validity_days} dias <span className="text-slate-500">({formatBRL(p.price_cents)})</span></td>
              <td className={td}><NumberEdit label={`Preço do pacote ${p.code}`} value={p.price_cents} min={100} max={1000000}
                onSave={(v) => patch(`/admin/packages/${p.code}`, { price_cents: v })} /></td>
              <td className={td}><Button variant="secondary" className="px-2 py-1"
                onClick={() => patch(`/admin/packages/${p.code}`, { active: !p.active })}>{p.active ? "À venda — pausar" : "Pausado — vender"}</Button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type Setting = { key: string; value: unknown; description: string | null; editable: boolean };

function SettingRow({ s, onSaved }: { s: Setting; onSaved: () => void }) {
  const { run } = useContext(AdminCtx);
  const [text, setText] = useState(JSON.stringify(s.value));
  const [invalid, setInvalid] = useState(false);
  async function save() {
    let value: unknown;
    try {
      value = JSON.parse(text);
    } catch {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    if (await run(() => api(`/admin/settings/${s.key}`, { method: "PATCH", body: { value } }))) onSaved();
  }
  return (
    <tr className="border-t border-slate-100">
      <td className={td}><code>{s.key}</code><div className="text-xs text-slate-600">{s.description}</div></td>
      <td className={td}>
        {s.editable ? (
          <span className="flex flex-wrap items-center gap-2">
            <input aria-label={`Valor de ${s.key}`} value={text} onChange={(e) => setText(e.target.value)}
              className="min-w-64 flex-1 rounded border border-slate-300 px-2 py-1 font-mono text-xs" />
            <Button variant="secondary" className="px-2 py-1" onClick={save}>Salvar</Button>
            {invalid && <span className="text-xs text-red-700">JSON inválido (texto vai entre aspas).</span>}
          </span>
        ) : <code className="text-xs">{JSON.stringify(s.value)}</code>}
      </td>
    </tr>
  );
}

function SettingsSection() {
  const { run } = useContext(AdminCtx);
  const settings = useAdminData<{ settings: Setting[] }>("/admin/settings");
  const flags = useAdminData<{ flags: { key: string; enabled: boolean; description: string | null }[] }>("/admin/flags");
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h3 className="mb-2 font-semibold">Flags</h3>
        {!flags.data ? <Loading error={flags.error} /> : (
          <ul className="flex flex-col gap-2 text-sm">
            {flags.data.flags.map((f) => (
              <li key={f.key} className="flex flex-wrap items-center gap-3">
                <code>{f.key}</code> <Badge tone={f.enabled ? "ok" : "neutral"}>{f.enabled ? "ligada" : "desligada"}</Badge>
                <Button variant="secondary" className="px-2 py-1"
                  onClick={async () => { if (await run(() => api(`/admin/flags/${f.key}`, { method: "PATCH", body: { enabled: !f.enabled } }))) flags.reload(); }}>
                  {f.enabled ? "Desligar" : "Ligar"}
                </Button>
                <span className="text-xs text-slate-600">{f.description}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h3 className="mb-2 font-semibold">Configurações</h3>
        <p className="mb-2 text-xs text-slate-600">Valores em JSON. O servidor valida cada chave (ex.: limites de arquivo até 95 MB; AdSense começa com ca-pub-).</p>
        {!settings.data ? <Loading error={settings.error} /> : (
          <table className="w-full text-left text-sm">
            <tbody>{settings.data.settings.map((s) => <SettingRow key={`${s.key}-${JSON.stringify(s.value)}`} s={s} onSaved={settings.reload} />)}</tbody>
          </table>
        )}
      </div>
    </div>
  );
}

type AdminPayment = {
  id: string; email: string; purpose: string; amount_cents: number; status: string; method: string | null;
  created_at: string; approved_at: string | null; fulfilled: boolean; refunded_amount_cents: number;
};

function PaymentsSection() {
  const { run, password } = useContext(AdminCtx);
  const [status, setStatus] = useState("");
  const { data, error, reload } = useAdminData<{ payments: AdminPayment[] }>(`/admin/payments${status ? `?status=${status}` : ""}`);
  async function refund(p: AdminPayment) {
    if (!window.confirm(`Reembolsar o pagamento de ${p.email} (${formatBRL(p.amount_cents)})? O valor é proporcional às fichas não usadas.`)) return;
    if (await run(() => api(`/admin/payments/${p.id}/refund`, { method: "POST", body: { confirm_password: password } }))) reload();
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm">Situação{" "}
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded border border-slate-300 px-2 py-1">
            {["", "created", "pending", "approved", "rejected", "cancelled", "expired", "refunded", "charged_back", "in_mediation"].map((s) => <option key={s} value={s}>{s || "todas"}</option>)}
          </select>
        </label>
        <Button variant="secondary" className="px-2 py-1"
          onClick={async () => { if (await run(() => api("/admin/payments/reconcile", { method: "POST" }))) reload(); }}>
          Reconciliar com o Mercado Pago agora
        </Button>
      </div>
      {!data ? <Loading error={error} /> : (
        <table className="w-full text-left text-sm">
          <thead><tr><th className={th}>Data</th><th className={th}>Usuário</th><th className={th}>Compra</th><th className={th}>Valor</th><th className={th}>Situação</th><th className={th}></th></tr></thead>
          <tbody>
            {data.payments.map((p) => (
              <tr key={p.id} className="border-t border-slate-100">
                <td className={td}>{formatDateTime(p.created_at)}</td>
                <td className={td}>{p.email}</td>
                <td className={td}>{p.purpose}{p.method && ` · ${p.method}`}</td>
                <td className={td}>{formatBRL(p.amount_cents)}{p.refunded_amount_cents > 0 && ` (reemb. ${formatBRL(p.refunded_amount_cents)})`}</td>
                <td className={td}>{p.status}{p.fulfilled && " · liberado"}</td>
                <td className={td}>{p.status === "approved" && (
                  <Button variant="secondary" className="px-2 py-1" onClick={() => refund(p)}>Reembolsar</Button>)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function SubscriptionsSection() {
  const { data, error } = useAdminData<{ subscriptions: {
    id: string; email: string; plan: string; kind: string; status: string; renewal_mode: string | null;
    cancel_at_period_end: boolean; period_end: string | null; }[] }>("/admin/subscriptions");
  if (!data) return <Loading error={error} />;
  return (
    <table className="w-full text-left text-sm">
      <thead><tr><th className={th}>Usuário</th><th className={th}>Plano</th><th className={th}>Situação</th><th className={th}>Renovação</th><th className={th}>Fim do ciclo</th></tr></thead>
      <tbody>
        {data.subscriptions.map((s) => (
          <tr key={s.id} className="border-t border-slate-100">
            <td className={td}>{s.email}</td><td className={td}>{s.plan}</td>
            <td className={td}>{s.status}{s.cancel_at_period_end && " · cancela no fim"}</td>
            <td className={td}>{s.renewal_mode ?? "—"}</td>
            <td className={td}>{s.period_end ? formatDateTime(s.period_end) : "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function UsersSection() {
  const { run, password } = useContext(AdminCtx);
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const { data, error, reload } = useAdminData<{ users: {
    id: string; email: string; role: string; status: string; email_verified: boolean; created_at: string; }[] }>(
    `/admin/users?q=${encodeURIComponent(query)}`);
  async function toggle(id: string, suspended: boolean) {
    if (await run(() => api(`/admin/users/${id}/suspend`, { method: "POST", body: { suspended, confirm_password: password } }))) reload();
  }
  return (
    <div className="flex flex-col gap-3">
      <form onSubmit={(e) => { e.preventDefault(); setQuery(q); }} className="flex items-end gap-2">
        <TextField id="user-q" label="Buscar por e-mail" value={q} onChange={(e) => setQ(e.target.value)} />
        <Button type="submit" variant="secondary">Buscar</Button>
      </form>
      {!data ? <Loading error={error} /> : (
        <table className="w-full text-left text-sm">
          <thead><tr><th className={th}>E-mail</th><th className={th}>Papel</th><th className={th}>Situação</th><th className={th}>Cadastro</th><th className={th}></th></tr></thead>
          <tbody>
            {data.users.map((u) => (
              <tr key={u.id} className="border-t border-slate-100">
                <td className={td}>{u.email}{!u.email_verified && <span className="text-xs text-slate-500"> (não confirmado)</span>}</td>
                <td className={td}>{u.role}</td><td className={td}>{u.status}</td>
                <td className={td}>{formatDateTime(u.created_at)}</td>
                <td className={td}>{u.status !== "deleted" && u.role !== "admin" && (
                  <Button variant="secondary" className="px-2 py-1" onClick={() => toggle(u.id, u.status !== "suspended")}>
                    {u.status === "suspended" ? "Reativar" : "Suspender"}
                  </Button>)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function AuditSection() {
  const { data, error } = useAdminData<{ events: {
    id: number; actor_type: string; actor_id: string | null; action: string; target_type: string | null;
    target_id: string | null; metadata: unknown; created_at: string; }[] }>("/admin/audit");
  if (!data) return <Loading error={error} />;
  return (
    <table className="w-full text-left text-sm">
      <thead><tr><th className={th}>Quando</th><th className={th}>Quem</th><th className={th}>Ação</th><th className={th}>Alvo</th><th className={th}>Detalhes</th></tr></thead>
      <tbody>
        {data.events.map((e) => (
          <tr key={e.id} className="border-t border-slate-100">
            <td className={td}>{formatDateTime(e.created_at)}</td>
            <td className={td}>{e.actor_type}</td>
            <td className={td}><code>{e.action}</code></td>
            <td className={td}>{e.target_type} {e.target_id && <span className="text-xs text-slate-500">{e.target_id.slice(0, 12)}</span>}</td>
            <td className={td}><code className="break-all text-xs">{JSON.stringify(e.metadata)}</code></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------- page

const TABS = [
  ["overview", "Visão geral", OverviewSection],
  ["tools", "Ferramentas", ToolsSection],
  ["capabilities", "Combinações", CapabilitiesSection],
  ["costs", "Regras de custo", CostRulesSection],
  ["catalog", "Planos e pacotes", CatalogSection],
  ["settings", "Configurações e flags", SettingsSection],
  ["payments", "Pagamentos", PaymentsSection],
  ["subscriptions", "Assinaturas", SubscriptionsSection],
  ["users", "Usuários", UsersSection],
  ["audit", "Auditoria", AuditSection],
] as const;

export default function AdminPage() {
  const { me } = useMe();
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("overview");
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState<Notice>(null);

  const run = useCallback(async (fn: () => Promise<unknown>) => {
    setNotice(null);
    try {
      const result = (await fn()) as { message?: string } | undefined;
      setNotice({ kind: "success", text: result?.message ?? "Feito." });
      return true;
    } catch (e) {
      setNotice({ kind: "error", text: e instanceof ApiError ? e.message : "Falha na operação." });
      return false;
    }
  }, []);

  if (me === undefined) return <p>Carregando…</p>;
  if (!me || me.role !== "admin") return <Alert kind="error">Acesso restrito a administradores.</Alert>;

  const Section = TABS.find(([key]) => key === tab)![2];
  return (
    <AdminCtx.Provider value={{ password, run }}>
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-bold">Administração</h1>
        <Card>
          <TextField id="admin-reauth" type="password" label="Sua senha (confirma ações sensíveis)" autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)}
            hint="Exigida para mudar ferramentas, preços, combinações, reembolsar e suspender. Fica só nesta aba e não é salva." />
        </Card>
        <nav aria-label="Seções da administração" className="flex flex-wrap gap-2">
          {TABS.map(([key, label]) => (
            <button key={key} type="button" onClick={() => { setTab(key); setNotice(null); }} aria-current={tab === key ? "page" : undefined}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${tab === key ? "bg-blue-700 text-white" : "border border-slate-300 bg-white text-slate-900 hover:bg-slate-50"}`}>
              {label}
            </button>
          ))}
        </nav>
        {notice && <Alert kind={notice.kind}>{notice.text}</Alert>}
        <Card><Section /></Card>
      </div>
    </AdminCtx.Provider>
  );
}
