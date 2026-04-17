import React, { useEffect, useRef, useState, useCallback } from "react";
import {
    X,
    Trash,
    Target,
    Fire,
    Lightning,
    Storefront,
    MagicWand,
} from "@phosphor-icons/react";
import {
    fetchTrends,
    fetchSummary,
    clearCountry,
    fetchProducts,
    startMatching,
    getMatchingExecution,
    fetchHotmartStatus,
} from "../lib/api";
import TrendsTable from "./TrendsTable";
import PriorityBadge from "./PriorityBadge";
import ProductCard from "./ProductCard";
import { COUNTRY_LABELS } from "../lib/country-flags";
import { toast } from "sonner";

export default function CountryDetail({ country, onClose, onChanged }) {
    const [trends, setTrends] = useState([]);
    const [summary, setSummary] = useState(null);
    const [products, setProducts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [matching, setMatching] = useState(false);
    const [hotmartStatus, setHotmartStatus] = useState(null);
    const [tab, setTab] = useState("trends");
    const pollRef = useRef(null);

    const meta = COUNTRY_LABELS[country.code] || {
        name: country.name,
        color: "#09090B",
    };

    const loadAll = useCallback(async () => {
        setLoading(true);
        try {
            const [tr, sm, pr, hs] = await Promise.all([
                fetchTrends(country.code),
                fetchSummary(country.code).catch(() => null),
                fetchProducts(country.code).catch(() => []),
                fetchHotmartStatus().catch(() => null),
            ]);
            setTrends(tr);
            setSummary(sm);
            setProducts(pr);
            setHotmartStatus(hs);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, [country.code]);

    useEffect(() => {
        loadAll();
        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
        };
    }, [loadAll]);

    const handleClear = async () => {
        if (!window.confirm(`¿Borrar tendencias de ${country.name}?`)) return;
        try {
            await clearCountry(country.code);
            toast.success("Tendencias borradas");
            onChanged && onChanged();
            onClose();
        } catch {
            toast.error("No se pudo borrar");
        }
    };

    const handleStartMatching = async () => {
        if (!trends || trends.length === 0) {
            toast.warning("Ejecuta investigación primero para tener tendencias");
            return;
        }
        setMatching(true);
        try {
            const res = await startMatching(country.code, 10, true);
            toast.success("Búsqueda de productos iniciada");
            setTab("products");
            // Poll execution
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = setInterval(async () => {
                try {
                    const exec = await getMatchingExecution(res.execution_id);
                    if (exec.status === "completed" || exec.status === "failed") {
                        clearInterval(pollRef.current);
                        pollRef.current = null;
                        setMatching(false);
                        if (exec.status === "completed") {
                            toast.success(
                                `${exec.products_found} productos encontrados`,
                            );
                            const pr = await fetchProducts(country.code);
                            setProducts(pr);
                        } else {
                            toast.error("La búsqueda falló");
                        }
                    }
                } catch (e) {
                    console.error(e);
                }
            }, 3000);
        } catch (e) {
            console.error(e);
            const msg =
                e.response?.data?.detail || "No se pudo iniciar la búsqueda";
            toast.error(msg);
            setMatching(false);
        }
    };

    return (
        <div
            data-testid="country-detail-overlay"
            className="fixed inset-0 z-40 bg-[#09090b]/40 backdrop-blur-sm flex items-stretch justify-end"
            onClick={onClose}
        >
            <aside
                className="w-full md:w-[min(1100px,92vw)] surface hard-border-l overflow-y-auto"
                onClick={(e) => e.stopPropagation()}
                data-testid="country-detail-panel"
            >
                <div className="hard-border-b px-6 sm:px-10 py-6 flex items-start justify-between sticky top-0 surface z-10">
                    <div className="flex items-center gap-4">
                        <div
                            className="w-12 h-12 flex items-center justify-center font-mono font-bold text-sm text-white"
                            style={{ background: meta.color }}
                        >
                            {country.code}
                        </div>
                        <div>
                            <div className="overline">
                                {country.currency} · {country.language}
                            </div>
                            <h2
                                className="font-display text-2xl sm:text-3xl font-semibold tracking-tight"
                                data-testid="detail-country-name"
                            >
                                {country.name}
                            </h2>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            data-testid="clear-country-btn"
                            onClick={handleClear}
                            className="p-2.5 hard-border surface-hover"
                            title="Borrar tendencias"
                        >
                            <Trash size={16} weight="bold" />
                        </button>
                        <button
                            data-testid="close-detail-btn"
                            onClick={onClose}
                            className="p-2.5 hard-border surface-hover"
                        >
                            <X size={16} weight="bold" />
                        </button>
                    </div>
                </div>

                {/* Tabs */}
                <div className="hard-border-b px-6 sm:px-10 flex gap-1 sticky top-[89px] surface z-10">
                    <TabButton
                        active={tab === "trends"}
                        onClick={() => setTab("trends")}
                        testid="tab-trends"
                    >
                        Tendencias
                        <span className="ml-2 mono text-xs text-[#a1a1aa]">
                            {trends.length}
                        </span>
                    </TabButton>
                    <TabButton
                        active={tab === "products"}
                        onClick={() => setTab("products")}
                        testid="tab-products"
                    >
                        <Storefront size={14} weight="bold" className="inline mr-1.5" />
                        Productos Hotmart
                        <span className="ml-2 mono text-xs text-[#a1a1aa]">
                            {products.length}
                        </span>
                    </TabButton>
                </div>

                <div className="px-6 sm:px-10 py-8 space-y-8">
                    {loading && (
                        <div data-testid="detail-loading" className="linear-progress" />
                    )}

                    {tab === "trends" && (
                        <>
                            {summary && (
                                <section
                                    className="hard-border p-6"
                                    data-testid="executive-summary"
                                >
                                    <div className="flex items-center gap-2 mb-5">
                                        <Target size={16} weight="bold" />
                                        <h3 className="font-display text-lg font-semibold tracking-tight">
                                            Resumen Ejecutivo
                                        </h3>
                                        <span className="ml-auto">
                                            <PriorityBadge
                                                level={summary.recommendation_priority}
                                            />
                                        </span>
                                    </div>
                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
                                        <Metric
                                            label="Tendencias"
                                            value={summary.total_trends}
                                        />
                                        <Metric
                                            label="Score promedio"
                                            value={summary.avg_priority_score}
                                        />
                                        <div className="col-span-2">
                                            <div className="overline mb-2">
                                                Top necesidades
                                            </div>
                                            <div className="flex flex-wrap gap-1.5">
                                                {summary.top_needs.map((n) => (
                                                    <span
                                                        key={n}
                                                        className="text-xs px-2.5 py-1 hard-border font-medium"
                                                        data-testid={`top-need-${n}`}
                                                    >
                                                        {n}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                    <div className="mt-6 pt-6 hard-border-t">
                                        <div className="overline mb-3 flex items-center gap-1.5">
                                            <Fire size={11} weight="bold" /> Puntos de
                                            Dolor Identificados
                                        </div>
                                        <ul className="space-y-2">
                                            {summary.pain_points.map((p, i) => (
                                                <li
                                                    key={i}
                                                    data-testid={`pain-point-${i}`}
                                                    className="flex gap-3 text-sm leading-relaxed"
                                                >
                                                    <Lightning
                                                        size={14}
                                                        weight="bold"
                                                        className="mt-1 flex-shrink-0"
                                                    />
                                                    <span>{p}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </section>
                            )}

                            {!summary && !loading && (
                                <section
                                    className="hard-border p-10 text-center"
                                    data-testid="no-data-state"
                                >
                                    <div className="font-display text-xl font-semibold mb-2">
                                        Sin investigación aún
                                    </div>
                                    <p className="text-sm text-[#52525B]">
                                        Ejecuta "Ejecutar Investigación" desde la parte superior.
                                    </p>
                                </section>
                            )}

                            {trends.length > 0 && <TrendsTable trends={trends} />}
                        </>
                    )}

                    {tab === "products" && (
                        <ProductsSection
                            countryCode={country.code}
                            countryName={country.name}
                            products={products}
                            matching={matching}
                            hotmartStatus={hotmartStatus}
                            onStartMatching={handleStartMatching}
                            onRefresh={() =>
                                fetchProducts(country.code).then(setProducts)
                            }
                            canMatch={trends.length > 0}
                        />
                    )}
                </div>
            </aside>
        </div>
    );
}

function TabButton({ active, onClick, children, testid }) {
    return (
        <button
            data-testid={testid}
            onClick={onClick}
            className={`relative px-4 py-3 text-sm font-medium transition-colors ${
                active ? "text-[#09090b]" : "text-[#52525B] hover:text-[#09090b]"
            }`}
        >
            {children}
            {active && (
                <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#09090b]" />
            )}
        </button>
    );
}

function Metric({ label, value }) {
    return (
        <div>
            <div className="overline">{label}</div>
            <div className="mono text-2xl font-semibold mt-1">{value}</div>
        </div>
    );
}

function ProductsSection({
    countryCode,
    countryName,
    products,
    matching,
    hotmartStatus,
    onStartMatching,
    onRefresh,
    canMatch,
}) {
    return (
        <section data-testid="products-section">
            <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
                <div>
                    <div className="overline flex items-center gap-1.5">
                        <MagicWand size={11} weight="bold" />
                        Módulo 2 · Matching Hotmart
                    </div>
                    <h3 className="font-display text-2xl font-semibold tracking-tight mt-1">
                        Productos recomendados para {countryName}
                    </h3>
                    <p className="text-sm text-[#52525B] mt-1 max-w-xl">
                        Hotmart marketplace + fallback IA cuando hay bloqueo. Scoring combinado por relevancia (dolor) y rentabilidad (comisión × rating × volumen).
                    </p>
                </div>
                <button
                    data-testid="start-matching-btn"
                    onClick={onStartMatching}
                    disabled={matching || !canMatch}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#09090b] text-white text-sm font-medium uppercase tracking-wide hover:bg-[#27272a] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    title={!canMatch ? "Ejecuta investigación primero" : ""}
                >
                    <Storefront size={14} weight="bold" />
                    {matching ? "Buscando…" : "Buscar productos"}
                </button>
            </div>

            {matching && (
                <div
                    data-testid="matching-progress"
                    className="hard-border p-4 mb-6"
                >
                    <div className="overline mb-2">
                        Buscando en marketplace Hotmart…
                    </div>
                    <div className="linear-progress" />
                </div>
            )}

            {hotmartStatus && !hotmartStatus.credentials_configured && (
                <div
                    className="hard-border p-4 mb-6 flex items-start gap-3"
                    style={{ background: "#FEF3C7", borderColor: "#FCD34D" }}
                    data-testid="credentials-warning"
                >
                    <div className="flex-1 text-sm">
                        <div className="font-semibold mb-1" style={{ color: "#92400E" }}>
                            Credenciales Hotmart pendientes
                        </div>
                        <p className="text-[#52525B] text-xs leading-relaxed">
                            Los productos y scoring ya funcionan. Para generar hotlinks de afiliado reales, agrega <code className="mono">HOTMART_CLIENT_ID</code>, <code className="mono">HOTMART_CLIENT_SECRET</code> y <code className="mono">HOTMART_BASIC_AUTH</code> en{" "}
                            <code className="mono">backend/.env</code>. Obtenlas en{" "}
                            <a
                                href="https://developers.hotmart.com"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="underline font-medium"
                            >
                                developers.hotmart.com
                            </a>.
                        </p>
                    </div>
                </div>
            )}

            {products.length === 0 && !matching ? (
                <div
                    className="hard-border p-10 text-center"
                    data-testid="no-products-state"
                >
                    <Storefront size={32} weight="bold" className="mx-auto mb-3" />
                    <div className="font-display text-lg font-semibold mb-1">
                        {canMatch
                            ? "Sin productos aún"
                            : "Primero ejecuta investigación"}
                    </div>
                    <p className="text-sm text-[#52525B]">
                        {canMatch
                            ? 'Haz click en "Buscar productos" para encontrar matches en Hotmart.'
                            : "Necesitas tendencias para poder hacer matching."}
                    </p>
                </div>
            ) : (
                <div
                    className="grid grid-cols-1 lg:grid-cols-2 gap-4"
                    data-testid="products-grid"
                >
                    {products.map((p, i) => (
                        <ProductCard
                            key={`${p.hotmart_id}-${i}`}
                            product={p}
                            countryCode={countryCode}
                            index={i}
                            onUpdated={onRefresh}
                        />
                    ))}
                </div>
            )}
        </section>
    );
}
