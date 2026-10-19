import { Alert } from "./ui";

export function LegalPage({ title, updated, sections }: {
  title: string;
  updated: string;
  sections: { title: string; body: string[] }[];
}) {
  return (
    <article className="mx-auto flex max-w-3xl flex-col gap-6 text-slate-800">
      <h1 className="text-3xl font-bold text-slate-900">{title}</h1>
      <Alert kind="info">
        <strong>Rascunho sem revisão jurídica.</strong> Este texto ainda precisa ser revisado por um advogado antes do
        lançamento e pode mudar. Última atualização: {updated}.
      </Alert>
      {sections.map((s) => (
        <section key={s.title} className="flex flex-col gap-2">
          <h2 className="text-xl font-semibold text-slate-900">{s.title}</h2>
          {s.body.map((p) => (
            <p key={p.slice(0, 50)} className="leading-relaxed">{p}</p>
          ))}
        </section>
      ))}
    </article>
  );
}
