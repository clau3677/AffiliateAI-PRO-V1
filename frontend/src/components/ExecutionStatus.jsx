import React from "react";
import { CheckCircle, XCircle, CircleNotch } from "@phosphor-icons/react";

export default function ExecutionStatus({ execution }) {
    if (!execution) return null;

    const { status, progress, trends_processed, total_expected, current_country, error } = execution;

    const statusLabel = {
        pending: "En cola",
        running: "En curso",
        completed: "Completada",
        failed: "Fallida",
    }[status] || status;

    const icon =
        status === "completed" ? (
            <CheckCircle size={16} weight="fill" color="#16A34A" />
        ) : status === "failed" ? (
            <XCircle size={16} weight="fill" color="#DC2626" />
        ) : (
            <CircleNotch size={16} weight="bold" className="animate-spin" />
        );

    return (
        <section
            data-testid="execution-status"
            className="hard-border surface p-6 widget-enter"
        >
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    {icon}
                    <span className="font-display font-semibold text-base tracking-tight">
                        Investigación {statusLabel}
                    </span>
                </div>
                <span
                    className="mono text-sm font-semibold"
                    data-testid="execution-progress-pct"
                >
                    {progress}%
                </span>
            </div>

            <div className="h-1 bg-[#E4E4E7] relative overflow-hidden">
                <div
                    className="absolute inset-y-0 left-0 bg-[#09090B] transition-all duration-500"
                    style={{ width: `${progress}%` }}
                    data-testid="progress-bar-fill"
                />
            </div>

            <div className="mt-4 flex flex-wrap gap-6 text-xs text-[#52525B]">
                <div>
                    <div className="overline">Procesadas</div>
                    <div className="mono text-sm font-semibold text-[#09090B] mt-0.5">
                        {trends_processed} / {total_expected}
                    </div>
                </div>
                {current_country && status === "running" && (
                    <div>
                        <div className="overline">País actual</div>
                        <div className="mono text-sm font-semibold text-[#09090B] mt-0.5">
                            {current_country}
                        </div>
                    </div>
                )}
                <div>
                    <div className="overline">Países</div>
                    <div className="mono text-sm font-semibold text-[#09090B] mt-0.5">
                        {(execution.countries || []).join(" · ")}
                    </div>
                </div>
                {error && (
                    <div className="w-full text-[#DC2626]">
                        <div className="overline">Error</div>
                        <div className="mt-0.5 text-sm">{error}</div>
                    </div>
                )}
            </div>
        </section>
    );
}
