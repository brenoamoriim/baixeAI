import type { MetadataRoute } from "next";
import { absolute } from "@/lib/site";

const PUBLIC_PAGES = ["/", "/conversores", "/removedor-de-fundo", "/remover-objeto", "/baixar-videos", "/precos",
  "/termos", "/privacidade", "/reembolso", "/cookies", "/direitos-de-conteudo", "/contato"];

export default function sitemap(): MetadataRoute.Sitemap {
  return PUBLIC_PAGES.map((path) => ({
    url: absolute(path),
    changeFrequency: path === "/" ? "weekly" : "monthly",
    priority: path === "/" ? 1 : path.length < 20 ? 0.8 : 0.4,
  }));
}
