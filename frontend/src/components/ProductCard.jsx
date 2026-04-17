import React from "react";
import {
    Copy,
    ArrowSquareOut,
    Sparkle,
    Star,
    Lightning,
} from "@phosphor-icons/react";
import { toast } from "sonner";

export default function ProductCard({ product, countryCode, index = 0 }) {
    const isFallback = product.is_fallback;
    const isMyAffiliation = product.is_my_affiliation;
    const hasLink =
        product.affiliate_link &&
        ["generated", "cached", "manual"].includes(product.affiliate_status);

    // Keyword to search on Hotmart marketplace — use the first matched pain point
    // or fall back to the product title. This gives the user REAL products to affiliate to.
    const searchKeyword =
        (product.matched_pain_points && product.matched_pain_points[0]) ||
        product.title ||
        "";
    const marketLocale = countryCode === "BR" ? "pt-br" : "es";
    const marketplaceSearchUrl = `https://hotmart.com/${marketLocale}/marketplace/productos?q=${encodeURIComponent(searchKeyword)}`;

    // "Ver producto" URL:
    //  - Real scraped product → use its real product_url
    //  - IA/synthetic product (ai_/det_/hm_ prefix) → use marketplace search (avoids dead placeholder URLs)
    const viewProductUrl =
        isFallback || /^(ai_|det_|hm_)/.test(String(product.hotmart_id))
            ? marketplaceSearchUrl
            : product.product_url || marketplaceSearchUrl;

    const handleCopy = async () => {
        if (!product.affiliate_link) return;
        try {
            await navigator.clipboard.writeText(product.affiliate_link);
            toast.success("Hotlink copiado al portapapeles");
        } catch {
            toast.error("No se pudo copiar");
        }
    };

    const scoreColor = (s) =>
        s >= 80 ? "#DC2626" : s >= 60 ? "#D97706" : "#2563EB";

    return (
        <article
            data-testid={`product-card-${product.hotmart_id}`}
            style={{ animationDelay: `${index * 40}ms` }}
            className="widget-enter hard-border surface p-5 flex flex-col gap-4"
        >
            <header className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                    <div className="overline mb-1">{product.category}</div>
                    <h4
                        className="font-display text-base font-semibold tracking-tight leading-snug"
                        data-testid={`product-title-${product.hotmart_id}`}
                    >
                        {product.title}
                    </h4>
                    <div className="text-xs text-[#52525B] mt-1">
                        por {product.creator_name}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {isMyAffiliation && (
                        <span
                            data-testid={`my-affiliation-badge-${product.hotmart_id}`}
                            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-mono font-semibold tracking-widest"
                            style={{
                                background: "#DCFCE7",
                                color: "#166534",
                                border: "1px solid #86EFAC",
                            }}
                            title="Ya estás afiliado a este producto"
                        >
                            <Lightning size={9} weight="fill" />
                            Mi afiliación
                        </span>
                    )}
                    {isFallback && (
                        <span
                            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-mono font-semibold tracking-widest"
                            style={{
                                background: "#DBEAFE",
                                color: "#1E40AF",
                                border: "1px solid #93C5FD",
                            }}
                            title="Sugerido por IA (Claude Sonnet 4.5)"
                        >
                            <Sparkle size={9} weight="fill" />
                            IA
                        </span>
                    )}
                </div>
            </header>

            <div className="grid grid-cols-3 gap-3 hard-border-t pt-3">
                <div>
                    <div className="overline">Comisión</div>
                    <div className="mono text-lg font-semibold mt-0.5">
                        {Math.round(product.commission_percent)}%
                    </div>
                </div>
                <div>
                    <div className="overline">Rating</div>
                    <div className="mono text-lg font-semibold mt-0.5 flex items-center gap-1">
                        <Star size={12} weight="fill" />
                        {Number(product.rating).toFixed(1)}
                    </div>
                </div>
                <div>
                    <div className="overline">Score</div>
                    <div
                        className="mono text-lg font-semibold mt-0.5"
                        style={{ color: scoreColor(product.relevance_score) }}
                        data-testid={`product-score-${product.hotmart_id}`}
                    >
                        {Math.round(product.relevance_score)}
                    </div>
                </div>
            </div>

            {product.matched_pain_points && product.matched_pain_points.length > 0 && (
                <div>
                    <div className="overline mb-1.5">Dolores que resuelve</div>
                    <div className="flex flex-wrap gap-1">
                        {product.matched_pain_points.slice(0, 4).map((pp) => (
                            <span
                                key={pp}
                                className="text-[11px] px-2 py-0.5 hard-border"
                            >
                                {pp}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Affiliate flow — fully automated */}
            <div className="hard-border-t pt-4 space-y-2">
                {isMyAffiliation && hasLink ? (
                    <div
                        className="hard-border p-3 flex items-center gap-2 text-xs"
                        style={{ background: "#DCFCE7", borderColor: "#86EFAC" }}
                        data-testid={`auto-link-ready-${product.hotmart_id}`}
                    >
                        <Lightning size={13} weight="fill" color="#16A34A" />
                        <div className="flex-1 min-w-0">
                            <div
                                className="font-semibold"
                                style={{ color: "#166534" }}
                            >
                                Hotlink auto-generado
                            </div>
                            <div className="mono text-[10px] text-[#166534] truncate">
                                {product.affiliate_link}
                            </div>
                        </div>
                        <button
                            data-testid={`copy-link-${product.hotmart_id}`}
                            onClick={handleCopy}
                            className="inline-flex items-center gap-1 px-3 py-1.5 bg-[#09090b] text-white font-medium text-[11px] uppercase tracking-wide hover:bg-[#27272a]"
                        >
                            <Copy size={11} weight="bold" />
                            Copiar
                        </button>
                    </div>
                ) : (
                    <div className="space-y-2">
                        <div
                            className="hard-border p-2.5 text-[11px] leading-relaxed"
                            style={{ background: "#FEF3C7", borderColor: "#FCD34D" }}
                            data-testid={`not-affiliated-${product.hotmart_id}`}
                        >
                            <span style={{ color: "#92400E" }} className="font-semibold">
                                Aún no estás afiliado.
                            </span>{" "}
                            <span style={{ color: "#52525B" }}>
                                Abre el marketplace de Hotmart con la búsqueda prellenada,
                                afíliate al producto real que prefieras y vuelve a pulsar
                                "Sincronizar y auto-enlazar" arriba.
                            </span>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                            <a
                                href={viewProductUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                data-testid={`open-product-${product.hotmart_id}`}
                                className="inline-flex items-center justify-center gap-1.5 px-3 py-2 hard-border surface-hover text-[11px] font-medium uppercase tracking-wide"
                                title={
                                    isFallback
                                        ? `Buscar "${searchKeyword}" en el marketplace de Hotmart`
                                        : "Ver producto en Hotmart"
                                }
                            >
                                <ArrowSquareOut size={12} weight="bold" />
                                Ver producto
                            </a>
                            <a
                                href={marketplaceSearchUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                data-testid={`open-affiliates-${product.hotmart_id}`}
                                className="inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-[#09090b] text-white text-[11px] font-medium uppercase tracking-wide hover:bg-[#27272a]"
                                title={`Abrir marketplace Hotmart buscando "${searchKeyword}"`}
                            >
                                <Lightning size={12} weight="bold" />
                                Afiliarme
                            </a>
                        </div>
                    </div>
                )}
            </div>
        </article>
    );
}
