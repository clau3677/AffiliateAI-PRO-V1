import React, { useState } from "react";
import {
    Copy,
    ArrowSquareOut,
    Sparkle,
    Lock,
    CheckCircle,
    Warning,
    Star,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import { generateAffiliateLink } from "../lib/api";

function statusMeta(status) {
    switch (status) {
        case "generated":
        case "cached":
            return { label: "Link listo", color: "#16A34A", icon: CheckCircle };
        case "credentials_missing":
            return { label: "Configura API", color: "#D97706", icon: Lock };
        case "synthetic_product":
            return { label: "Producto IA", color: "#2563EB", icon: Sparkle };
        case "not_affiliated":
            return { label: "No afiliado", color: "#DC2626", icon: Warning };
        case "not_found":
            return { label: "No encontrado", color: "#DC2626", icon: Warning };
        case "pending":
            return { label: "Pendiente", color: "#52525B", icon: Warning };
        default:
            return { label: status || "—", color: "#52525B", icon: Warning };
    }
}

export default function ProductCard({ product, countryCode, index = 0, onUpdated }) {
    const [loading, setLoading] = useState(false);
    const isFallback = product.is_fallback;
    const meta = statusMeta(product.affiliate_status);

    const handleGenerate = async () => {
        setLoading(true);
        try {
            const res = await generateAffiliateLink(countryCode, product.hotmart_id);
            if (res.status === "generated" || res.status === "cached") {
                toast.success("Link de afiliado listo");
                onUpdated && onUpdated();
            } else if (res.status === "credentials_missing") {
                toast.warning("Agrega credenciales Hotmart en backend/.env");
            } else if (res.status === "synthetic_product") {
                toast.info("Producto sugerido por IA — busca el equivalente real en Hotmart");
            } else {
                toast.error(res.error || "No se pudo generar el link");
            }
        } catch (e) {
            toast.error("Error al llamar al backend");
        } finally {
            setLoading(false);
        }
    };

    const handleCopy = async () => {
        if (!product.affiliate_link) return;
        try {
            await navigator.clipboard.writeText(product.affiliate_link);
            toast.success("Link copiado al portapapeles");
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

            <footer className="hard-border-t pt-3 flex flex-col gap-2">
                <div className="flex items-center gap-1.5 text-xs">
                    <meta.icon size={12} weight="bold" color={meta.color} />
                    <span style={{ color: meta.color }} className="font-medium">
                        {meta.label}
                    </span>
                    {product.tracking_id && (
                        <span className="mono text-[10px] text-[#a1a1aa] ml-auto">
                            {product.tracking_id}
                        </span>
                    )}
                </div>

                <div className="flex gap-2">
                    <a
                        href={product.product_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid={`view-product-${product.hotmart_id}`}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 hard-border surface-hover text-xs font-medium transition-colors"
                    >
                        <ArrowSquareOut size={13} weight="bold" />
                        Ver en Hotmart
                    </a>

                    {product.affiliate_status === "generated" ||
                    product.affiliate_status === "cached" ? (
                        <button
                            onClick={handleCopy}
                            data-testid={`copy-link-${product.hotmart_id}`}
                            className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-[#09090b] text-white text-xs font-medium uppercase tracking-wide hover:bg-[#27272a] transition-colors"
                        >
                            <Copy size={13} weight="bold" />
                            Copiar mi link
                        </button>
                    ) : (
                        <button
                            onClick={handleGenerate}
                            disabled={loading}
                            data-testid={`generate-link-${product.hotmart_id}`}
                            className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 hard-border surface-hover text-xs font-medium transition-colors disabled:opacity-50"
                        >
                            {loading ? "…" : "Generar link"}
                        </button>
                    )}
                </div>
            </footer>
        </article>
    );
}
