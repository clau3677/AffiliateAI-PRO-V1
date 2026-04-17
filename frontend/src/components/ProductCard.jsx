import React, { useState } from "react";
import {
    Copy,
    ArrowSquareOut,
    Sparkle,
    CheckCircle,
    Star,
    FloppyDisk,
    X as XIcon,
    Link as LinkIcon,
    Info,
    Lightning,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import {
    saveManualAffiliateLink,
    clearManualAffiliateLink,
} from "../lib/api";

export default function ProductCard({ product, countryCode, index = 0, onUpdated }) {
    const [linkInput, setLinkInput] = useState(product.affiliate_link || "");
    const [saving, setSaving] = useState(false);
    const [showHelp, setShowHelp] = useState(false);
    const isFallback = product.is_fallback;
    const isMyAffiliation = product.is_my_affiliation;
    const hasLink =
        product.affiliate_link &&
        ["generated", "cached", "manual"].includes(product.affiliate_status);

    const handleOpenHotmart = () => {
        window.open(product.product_url, "_blank", "noopener,noreferrer");
        setShowHelp(true);
    };

    const handleSave = async () => {
        const link = linkInput.trim();
        if (!link) {
            toast.warning("Pega tu link de afiliado primero");
            return;
        }
        setSaving(true);
        try {
            await saveManualAffiliateLink(countryCode, product.hotmart_id, link);
            toast.success("Link guardado");
            setShowHelp(false);
            onUpdated && onUpdated();
        } catch (e) {
            toast.error(e.response?.data?.detail || "No se pudo guardar");
        } finally {
            setSaving(false);
        }
    };

    const handleClear = async () => {
        setSaving(true);
        try {
            await clearManualAffiliateLink(countryCode, product.hotmart_id);
            setLinkInput("");
            toast.success("Link eliminado");
            onUpdated && onUpdated();
        } catch {
            toast.error("No se pudo eliminar");
        } finally {
            setSaving(false);
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

            {/* Affiliate flow — auto if real affiliation, manual otherwise */}
            <div className="hard-border-t pt-4 space-y-3">
                {isMyAffiliation && hasLink ? (
                    <div
                        className="hard-border p-3 flex items-center gap-2 text-xs"
                        style={{ background: "#DCFCE7", borderColor: "#86EFAC" }}
                        data-testid={`auto-link-ready-${product.hotmart_id}`}
                    >
                        <Lightning size={13} weight="fill" color="#16A34A" />
                        <div className="flex-1">
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
                    <>
                        {!hasLink && (
                            <button
                                data-testid={`open-hotmart-${product.hotmart_id}`}
                                onClick={handleOpenHotmart}
                                className="w-full inline-flex items-center justify-center gap-2 px-3 py-2.5 bg-[#09090b] text-white text-xs font-medium uppercase tracking-wide hover:bg-[#27272a] transition-colors"
                            >
                                <ArrowSquareOut size={14} weight="bold" />
                                Afiliarme en Hotmart
                            </button>
                        )}

                        {showHelp && !hasLink && (
                            <div
                                className="hard-border p-3 text-xs leading-relaxed space-y-1.5"
                                style={{ background: "#FEF3C7", borderColor: "#FCD34D" }}
                                data-testid="manual-help"
                            >
                                <div className="flex items-start gap-2">
                                    <Info size={13} weight="bold" className="mt-0.5 flex-shrink-0" />
                                    <div className="flex-1">
                                        <div className="font-semibold mb-1">
                                            3 pasos rápidos (≈15 seg):
                                        </div>
                                        <ol className="list-decimal list-inside space-y-0.5 text-[#52525B]">
                                            <li>En Hotmart: clic en "Afiliarme".</li>
                                            <li>
                                                Vuelve y haz clic en{" "}
                                                <strong>"Sincronizar y enlazar"</strong> arriba — el link se cargará automáticamente.
                                            </li>
                                            <li>O pega manualmente abajo.</li>
                                        </ol>
                                    </div>
                                    <button
                                        onClick={() => setShowHelp(false)}
                                        className="p-1 hover:bg-[#FDE68A]"
                                        aria-label="Cerrar ayuda"
                                    >
                                        <XIcon size={11} weight="bold" />
                                    </button>
                                </div>
                            </div>
                        )}

                        <div>
                            <div className="overline mb-1.5 flex items-center gap-1.5">
                                <LinkIcon size={10} weight="bold" />
                                Tu link de afiliado (manual)
                            </div>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    data-testid={`link-input-${product.hotmart_id}`}
                                    value={linkInput}
                                    onChange={(e) => setLinkInput(e.target.value)}
                                    placeholder="https://go.hotmart.com/..."
                                    className="flex-1 px-3 py-2 hard-border text-xs mono bg-white outline-none focus:border-[#09090b]"
                                    disabled={saving}
                                />
                                {!hasLink ? (
                                    <button
                                        data-testid={`save-link-${product.hotmart_id}`}
                                        onClick={handleSave}
                                        disabled={saving || !linkInput.trim()}
                                        className="inline-flex items-center gap-1 px-3 py-2 hard-border surface-hover text-xs font-medium disabled:opacity-50"
                                    >
                                        <FloppyDisk size={12} weight="bold" />
                                        Guardar
                                    </button>
                                ) : (
                                    <button
                                        data-testid={`clear-link-${product.hotmart_id}`}
                                        onClick={handleClear}
                                        disabled={saving}
                                        className="inline-flex items-center gap-1 px-3 py-2 hard-border surface-hover text-xs font-medium disabled:opacity-50"
                                        title="Eliminar link guardado"
                                    >
                                        <XIcon size={12} weight="bold" />
                                    </button>
                                )}
                            </div>
                        </div>

                        {hasLink && !isMyAffiliation && (
                            <div
                                className="hard-border p-2.5 flex items-center gap-2 text-xs"
                                style={{ background: "#DCFCE7", borderColor: "#86EFAC" }}
                                data-testid={`link-saved-${product.hotmart_id}`}
                            >
                                <CheckCircle size={13} weight="fill" color="#16A34A" />
                                <span
                                    className="font-medium"
                                    style={{ color: "#166534" }}
                                >
                                    Link guardado
                                </span>
                                <button
                                    data-testid={`copy-link-${product.hotmart_id}`}
                                    onClick={handleCopy}
                                    className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 bg-[#09090b] text-white font-medium text-[11px] uppercase tracking-wide hover:bg-[#27272a]"
                                >
                                    <Copy size={11} weight="bold" />
                                    Copiar
                                </button>
                            </div>
                        )}
                    </>
                )}

                <a
                    href={product.product_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    data-testid={`view-product-${product.hotmart_id}`}
                    className="block text-center text-[11px] text-[#52525B] hover:text-[#09090b] underline"
                >
                    Ver producto en Hotmart →
                </a>
            </div>
        </article>
    );
}
