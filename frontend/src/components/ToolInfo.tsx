import { absolute, SITE_NAME } from "@/lib/site";

export type Faq = { q: string; a: string };

/** Server-rendered, tool-specific content (unique per page) + JSON-LD (WebApplication + FAQPage). */
export function ToolInfo({ path, name, description, sections, faq }: {
  path: string;
  name: string;
  description: string;
  sections: { title: string; body: string[] }[];
  faq: Faq[];
}) {
  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "WebApplication",
      name: `${name} — ${SITE_NAME}`,
      url: absolute(path),
      applicationCategory: "UtilitiesApplication",
      operatingSystem: "Web",
      inLanguage: "pt-BR",
      description,
    },
    {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      mainEntity: faq.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })),
    },
  ];
  return (
    <section className="mt-12 flex flex-col gap-8 border-t border-slate-200 pt-8 text-slate-800">
      {sections.map((s) => (
        <div key={s.title} className="flex max-w-3xl flex-col gap-2">
          <h2 className="text-xl font-semibold text-slate-900">{s.title}</h2>
          {s.body.map((p) => (
            <p key={p.slice(0, 40)} className="leading-relaxed">{p}</p>
          ))}
        </div>
      ))}
      <div className="flex max-w-3xl flex-col gap-3">
        <h2 className="text-xl font-semibold text-slate-900">Perguntas frequentes</h2>
        {faq.map((f) => (
          <details key={f.q} className="rounded-md border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer font-medium">{f.q}</summary>
            <p className="mt-2 text-slate-700">{f.a}</p>
          </details>
        ))}
      </div>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} />
    </section>
  );
}
