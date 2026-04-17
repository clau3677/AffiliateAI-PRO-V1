import React, { useState, useMemo } from "react";
import { CaretUp, CaretDown, MagnifyingGlass } from "@phosphor-icons/react";
import { IntentChip } from "./PriorityBadge";

const scoreColor = (score) => {
    if (score >= 80) return "#DC2626";
    if (score >= 60) return "#D97706";
    return "#2563EB";
};

export default function TrendsTable({ trends }) {
    const [sortKey, setSortKey] = useState("priority_score");
    const [sortDir, setSortDir] = useState("desc");
    const [query, setQuery] = useState("");
    const [intentFilter, setIntentFilter] = useState("all");

    const sorted = useMemo(() => {
        let items = [...trends];
        if (query.trim()) {
            const q = query.toLowerCase();
            items = items.filter(
                (t) =>
                    t.keyword.toLowerCase().includes(q) ||
                    (t.pain_point || "").toLowerCase().includes(q),
            );
        }
        if (intentFilter !== "all") {
            items = items.filter((t) => t.commercial_intent === intentFilter);
        }
        items.sort((a, b) => {
            const av = a[sortKey];
            const bv = b[sortKey];
            if (typeof av === "string") {
                return sortDir === "asc"
                    ? av.localeCompare(bv)
                    : bv.localeCompare(av);
            }
            return sortDir === "asc" ? av - bv : bv - av;
        });
        return items;
    }, [trends, sortKey, sortDir, query, intentFilter]);

    const toggleSort = (key) => {
        if (key === sortKey) {
            setSortDir(sortDir === "asc" ? "desc" : "asc");
        } else {
            setSortKey(key);
            setSortDir("desc");
        }
    };

    const SortHeader = ({ label, k, mono, className = "" }) => (
        <th
            data-testid={`sort-header-${k}`}
            onClick={() => toggleSort(k)}
            className={`px-4 py-3 text-left overline cursor-pointer select-none hover:text-[#09090b] transition-colors ${className}`}
        >
            <span className="inline-flex items-center gap-1">
                {label}
                {sortKey === k &&
                    (sortDir === "asc" ? (
                        <CaretUp size={10} weight="bold" />
                    ) : (
                        <CaretDown size={10} weight="bold" />
                    ))}
            </span>
        </th>
    );

    return (
        <div className="hard-border surface" data-testid="trends-table-wrapper">
            <div className="px-4 py-3 hard-border-b flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
                <div className="flex items-center gap-2 flex-1 max-w-md">
                    <MagnifyingGlass size={16} weight="bold" />
                    <input
                        data-testid="trends-search"
                        type="text"
                        placeholder="Buscar por keyword o dolor…"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        className="flex-1 bg-transparent outline-none text-sm placeholder-[#a1a1aa]"
                    />
                </div>
                <div className="flex items-center gap-2">
                    <span className="overline">Intención</span>
                    {["all", "Alta", "Media", "Baja"].map((opt) => (
                        <button
                            key={opt}
                            data-testid={`intent-filter-${opt.toLowerCase()}`}
                            onClick={() => setIntentFilter(opt)}
                            className={`px-2.5 py-1 text-xs font-medium transition-colors hard-border ${
                                intentFilter === opt
                                    ? "bg-[#09090b] text-white border-[#09090b]"
                                    : "surface-hover"
                            }`}
                        >
                            {opt === "all" ? "Todas" : opt}
                        </button>
                    ))}
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="hard-border-b bg-[#FAFAFA]">
                        <tr>
                            <SortHeader label="Keyword" k="keyword" />
                            <th className="px-4 py-3 text-left overline">
                                Punto de Dolor
                            </th>
                            <SortHeader
                                label="Intención"
                                k="commercial_intent"
                            />
                            <th className="px-4 py-3 text-left overline">
                                Producto
                            </th>
                            <SortHeader
                                label="Interés"
                                k="interest_score"
                                className="text-right"
                            />
                            <SortHeader
                                label="Prioridad"
                                k="priority_score"
                                className="text-right"
                            />
                        </tr>
                    </thead>
                    <tbody>
                        {sorted.length === 0 && (
                            <tr>
                                <td
                                    colSpan={6}
                                    className="px-4 py-12 text-center text-[#a1a1aa]"
                                    data-testid="trends-empty-state"
                                >
                                    Sin resultados. Ajusta el filtro o ejecuta
                                    una investigación.
                                </td>
                            </tr>
                        )}
                        {sorted.map((t, i) => (
                            <tr
                                key={`${t.country_code}-${t.keyword}-${i}`}
                                data-testid={`trend-row-${i}`}
                                className="hard-border-b surface-hover transition-colors"
                            >
                                <td className="px-4 py-3 font-medium">
                                    {t.keyword}
                                </td>
                                <td className="px-4 py-3 text-[#52525B] max-w-md">
                                    {t.pain_point}
                                </td>
                                <td className="px-4 py-3">
                                    <IntentChip intent={t.commercial_intent} />
                                </td>
                                <td className="px-4 py-3 text-[#52525B] capitalize">
                                    {t.suggested_product_type}
                                </td>
                                <td className="px-4 py-3 text-right mono">
                                    {Number(t.interest_score).toFixed(1)}
                                </td>
                                <td className="px-4 py-3 text-right">
                                    <span
                                        className="mono font-semibold"
                                        style={{
                                            color: scoreColor(t.priority_score),
                                        }}
                                    >
                                        {t.priority_score}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="px-4 py-3 hard-border-t overline flex items-center justify-between">
                <span data-testid="trends-count">
                    {sorted.length} de {trends.length} tendencias
                </span>
                <span>Ordenado por {sortKey.replace("_", " ")}</span>
            </div>
        </div>
    );
}
