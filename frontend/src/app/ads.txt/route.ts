// ads.txt is generated from the AdSense publisher id configured by an admin (even with ads off). Without it -> 404.
// "f08c47fec0942fa0" is Google's certification authority id used in AdSense ads.txt lines;
// confirm the exact line shown in your AdSense panel before going live (docs/VALIDACOES-DOS-SOCIOS.md).
const API = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export async function GET(): Promise<Response> {
  try {
    const res = await fetch(`${API}/api/v1/site-config`, { cache: "no-store" });
    const config = (await res.json()) as { ads_txt_client: string | null };
    // independent of the ads_enabled flag: AdSense checks ads.txt before approving the site
    const client = config.ads_txt_client;
    if (!client?.startsWith("ca-pub-")) return new Response("Not found", { status: 404 });
    const publisher = client.replace(/^ca-/, "");
    return new Response(`google.com, ${publisher}, DIRECT, f08c47fec0942fa0\n`, {
      headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=3600" },
    });
  } catch {
    return new Response("Not found", { status: 404 });
  }
}
