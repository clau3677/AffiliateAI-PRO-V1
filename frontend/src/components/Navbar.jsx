import React from "react";
import { Play, ArrowClockwise } from "@phosphor-icons/react";

export default function Navbar({ onRun, running, onRefresh }) {
    return (
        <header
            data-testid="main-navbar"
            className="hard-border-b surface sticky top-0 z-30"
        >
            <div className="max-w-[1600px] mx-auto px-6 sm:px-8 md:px-12 py-5 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <div
                        className="w-9 h-9 hard-border flex items-center justify-center"
                        data-testid="brand-mark"
                    >
                        <span className="font-display font-bold text-sm">
                            H1
                        </span>
                    </div>
                    <div>
                        <div className="overline">Hotmart Super Agent</div>
                        <div
                            className="font-display font-semibold text-base sm:text-lg tracking-tight"
                            data-testid="module-title"
                        >
                            Módulo 1 — Investigación de Mercado
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <button
                        data-testid="refresh-overview-btn"
                        onClick={onRefresh}
                        className="hidden sm:inline-flex items-center gap-2 px-4 py-2.5 hard-border surface-hover text-sm font-medium transition-colors"
                    >
                        <ArrowClockwise size={16} weight="bold" />
                        Actualizar
                    </button>
                    <button
                        data-testid="run-research-btn"
                        onClick={onRun}
                        disabled={running}
                        className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#09090b] text-white text-sm font-medium uppercase tracking-wide hover:bg-[#27272a] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        <Play size={16} weight="fill" />
                        {running ? "Investigando…" : "Ejecutar Investigación"}
                    </button>
                </div>
            </div>
        </header>
    );
}
