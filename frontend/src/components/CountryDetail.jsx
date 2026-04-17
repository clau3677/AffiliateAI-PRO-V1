import React, { useEffect, useState } from "react";
import { X, Trash, Target, Fire, Lightning } from "@phosphor-icons/react";
import { fetchTrends, fetchSummary, clearCountry } from "../lib/api";
import TrendsTable from "./TrendsTable";
import PriorityBadge from "./PriorityBadge";
import { COUNTRY_LABELS } from "../lib/country-flags";
import { toast } from "sonner";

export default function CountryDetail({ country, onClose, onChanged }) {
    const [trends, setTrends] = useState([]);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let mounted = true;
        const load = async () => {
            setLoading(true);
            try {
                const [tr, sm] = await Promise.all([
                    fetchTrends(country.code),
                    fetchSummary(country.code).catch(() => null),
                ]);
                if (!mounted) return;
                setTrends(tr);
                setSummary(sm);
            } catch (e) {
                console.error(e);
            } finally {
                if (mounted) setLoading(false);
            }
        };
        load();
        return () => {
            mounted = false;
        };
    }, [country.code]);

    const meta = COUNTRY_LABELS[country.code] || {
        name: country.name,
        color: "#09090B",
    };

    const handleClear = async () => {
        if (!window.confirm(`¿Borrar todas las tendencias de ${country.name}?`))
            return;
        try {
            await clearCountry(country.code);
            toast.success("Tendencias borradas");
            onChanged && onChanged();
            onClose();
        } catch {
            toast.error("No se pudo borrar");
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

                <div className="px-6 sm:px-10 py-8 space-y-8">
                    {/* Executive summary */}
                    {loading && (
                        <div
                            data-testid="detail-loading"
                            className="linear-progress"
                        />
                    )}

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
                                <div>
                                    <div className="overline">Tendencias</div>
                                    <div className="mono text-2xl font-semibold mt-1">
                                        {summary.total_trends}
                                    </div>
                                </div>
                                <div>
                                    <div className="overline">
                                        Score promedio
                                    </div>
                                    <div className="mono text-2xl font-semibold mt-1">
                                        {summary.avg_priority_score}
                                    </div>
                                </div>
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
                                Ejecuta una investigación desde el botón "Ejecutar Investigación" en la parte superior.
                            </p>
                        </section>
                    )}

                    {/* Trends table */}
                    {trends.length > 0 && <TrendsTable trends={trends} />}
                </div>
            </aside>
        </div>
    );
}
