import React from "react";
import { ArrowRight, ChartBar, Clock } from "@phosphor-icons/react";
import PriorityBadge from "./PriorityBadge";
import { COUNTRY_LABELS } from "../lib/country-flags";

function formatDate(iso) {
    if (!iso) return "—";
    try {
        const d = new Date(iso);
        return d.toLocaleDateString("es-419", {
            day: "2-digit",
            month: "short",
            year: "numeric",
        });
    } catch {
        return "—";
    }
}

export default function CountryCard({ country, onSelect, index = 0 }) {
    const meta = COUNTRY_LABELS[country.code] || {
        name: country.name,
        color: "#09090B",
    };
    const empty = country.total_trends === 0;

    return (
        <button
            data-testid={`country-card-${country.code}`}
            onClick={() => onSelect(country)}
            style={{ animationDelay: `${index * 60}ms` }}
            className="widget-enter text-left hard-border surface surface-hover transition-colors p-6 flex flex-col gap-5 group"
        >
            <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                    <div
                        className="w-12 h-12 flex items-center justify-center font-mono font-bold text-sm text-white"
                        style={{ background: meta.color }}
                    >
                        {country.code}
                    </div>
                    <div>
                        <div className="overline">{country.currency}</div>
                        <div
                            className="font-display font-semibold text-xl tracking-tight"
                            data-testid={`country-name-${country.code}`}
                        >
                            {country.name}
                        </div>
                    </div>
                </div>
                <PriorityBadge
                    level={country.recommendation_priority}
                    testid={`country-priority-${country.code}`}
                />
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div>
                    <div className="overline flex items-center gap-1.5">
                        <ChartBar size={11} weight="bold" /> Tendencias
                    </div>
                    <div
                        className="mono text-2xl font-semibold mt-1"
                        data-testid={`country-total-trends-${country.code}`}
                    >
                        {country.total_trends}
                    </div>
                </div>
                <div>
                    <div className="overline">Score promedio</div>
                    <div
                        className="mono text-2xl font-semibold mt-1"
                        data-testid={`country-avg-score-${country.code}`}
                    >
                        {country.avg_priority_score.toFixed
                            ? country.avg_priority_score.toFixed(1)
                            : country.avg_priority_score}
                    </div>
                </div>
            </div>

            <div className="hard-border-t pt-4 flex items-center justify-between text-xs text-[#52525B]">
                <span className="flex items-center gap-1.5">
                    <Clock size={12} weight="bold" />
                    {empty
                        ? "Sin investigar"
                        : formatDate(country.last_researched_at)}
                </span>
                <span className="flex items-center gap-1 font-medium text-[#09090B] group-hover:translate-x-0.5 transition-transform">
                    Ver detalle <ArrowRight size={13} weight="bold" />
                </span>
            </div>
        </button>
    );
}
