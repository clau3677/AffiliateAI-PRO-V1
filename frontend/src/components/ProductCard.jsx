import React from "react";
import {
    Copy,
    ArrowSquareOut,
    Star,
    Lightning,
} from "@phosphor-icons/react";
import { toast } from "sonner";

export default function ProductCard({ product, countryCode, index = 0 }) {
    const isMyAffiliation = product.is_my_affiliation;
    const hasLink =
        product.affiliate_link &&
        ["generated", "cached", "manual"].includes(product.affiliate_status);

    // Marketplace search URL using the first matched pain point (used by "Afiliarme"
    // and as a safety fallback for "Ver producto" if the real URL is missing).
    const searchKeyword =
        (product.matched_pain_points && product.matched_pain_points[0]) ||
        product.title ||
        "";
    const marketLocale = countryCode === "BR" ? "pt-br" : "es";
    const marketplaceSearchUrl = `https://hotmart.com/${marketLocale}/marketplace/productos?search=${encodeURIComponent(searchKeyword)}`;
    const viewProductUrl = product.product_url || marketplaceSearchUrl;

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
    const commission = Number(product.commission_percent) || 0;

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
                </div>
            </header>

            <div className="grid grid-cols-3 gap-3 hard-border-t pt-3">
                <div>
                    <div className="overline">Comisión</div>
                    <div className="mono text-lg font-semibold mt-0.5">
                        {commission > 0 ? `${Math.round(commission)}%` : "—"}
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

            {/* Affiliate flow — fully automated, no manual inputs */}
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
                                Producto real del marketplace.
                            </span>{" "}
                            <span style={{ color: "#52525B" }}>
                                Ábrelo, pulsa "Afiliarme" en Hotmart, vuelve aquí y dale a
                                "Sincronizar y auto-enlazar" — el hotlink aparece solo.
                            </span>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                            <a
                                href={viewProductUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                data-testid={`open-product-${product.hotmart_id}`}
                                className="inline-flex items-center justify-center gap-1.5 px-3 py-2 hard-border surface-hover text-[11px] font-medium uppercase tracking-wide"
                                title="Ver producto real en Hotmart"
                            >
                                <ArrowSquareOut size={12} weight="bold" />
                                Ver producto
                            </a>
                            <a
                                href={viewProductUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                data-testid={`open-affiliates-${product.hotmart_id}`}
                                className="inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-[#09090b] text-white text-[11px] font-medium uppercase tracking-wide hover:bg-[#27272a]"
                                title="Abrir producto y afiliarse en Hotmart"
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
