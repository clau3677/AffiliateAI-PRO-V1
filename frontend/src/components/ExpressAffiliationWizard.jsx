import React, { useEffect, useState } from "react";
import {
    X,
    Lightning,
    ArrowSquareOut,
    CheckCircle,
    Rocket,
    Target,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import { fetchExpressWizard, rematchAllCountries } from "../lib/api";

const INTENT_STYLES = {
    Alta: { bg: "#DCFCE7", fg: "#166534", border: "#86EFAC" },
    Media: { bg: "#FEF3C7", fg: "#92400E", border: "#FCD34D" },
    Baja: { bg: "#F4F4F5", fg: "#3F3F46", border: "#D4D4D8" },
};

export default function ExpressAffiliationWizard({ onClose, onDone }) {
    const [opportunities, setOpportunities] = useState([]);
    const [loading, setLoading] = useState(true);
    const [opened, setOpened] = useState(new Set());
    const [selected, setSelected] = useState(new Set());
    const [step, setStep] = useState(1); // 1 = browse, 2 = waiting for user to affiliate, 3 = syncing
    const [syncing, setSyncing] = useState(false);

    useEffect(() => {
        fetchExpressWizard(2, 10)
            .then((r) => {
                setOpportunities(r.opportunities || []);
                // Preselect TOP 5 by default
                const top5 = (r.opportunities || []).slice(0, 5).map(
                    (o, i) => `${o.country_code}-${i}`,
                );
                setSelected(new Set(top5));
            })
            .catch(() => toast.error("No se pudieron cargar las oportunidades"))
            .finally(() => setLoading(false));
    }, []);

    const toggle = (id) => {
        const next = new Set(selected);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        setSelected(next);
    };

    const openAllSelected = () => {
        const picked = opportunities.filter((_, i) => {
            const id = `${opportunities[i].country_code}-${i}`;
            return selected.has(id);
        });
        if (picked.length === 0) {
            toast.warning("Selecciona al menos una oportunidad");
            return;
        }
        // Stagger tab opens to avoid browser blocking
        picked.forEach((o, i) => {
            setTimeout(() => {
                const win = window.open(
                    o.hotmart_discovery_url,
                    "_blank",
                    "noopener,noreferrer",
                );
                if (!win && i === 0) {
                    toast.warning(
                        "Habilita popups en tu navegador para abrir varios tabs",
                    );
                }
                setOpened((prev) => {
                    const next = new Set(prev);
                    next.add(`${o.country_code}-${opportunities.indexOf(o)}`);
                    return next;
                });
            }, i * 250);
        });
        toast.success(
            `${picked.length} búsquedas abiertas en Hotmart. Afíliate a los productos que te gusten y vuelve aquí.`,
        );
        setStep(2);
    };

    const handleSync = async () => {
        setSyncing(true);
        setStep(3);
        try {
            const res = await rematchAllCountries();
            toast.success(
                `Sincronización iniciada: ${res.synced_affiliations} afiliaciones · ${res.countries.length} países`,
            );
            onDone && onDone(res);
            setTimeout(() => onClose(), 1200);
        } catch (e) {
            toast.error(
                e.response?.data?.detail || "No se pudo sincronizar",
            );
            setStep(2);
        } finally {
            setSyncing(false);
        }
    };

    return (
        <div
            data-testid="express-wizard-overlay"
            className="fixed inset-0 z-50 bg-[#09090b]/50 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={onClose}
        >
            <div
                className="surface hard-border w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col"
                onClick={(e) => e.stopPropagation()}
                data-testid="express-wizard-panel"
            >
                {/* Header */}
                <div className="hard-border-b px-6 sm:px-8 py-5 flex items-start justify-between">
                    <div>
                        <div className="overline flex items-center gap-1.5">
                            <Rocket size={11} weight="bold" />
                            Asistente Express
                        </div>
                        <h2 className="font-display text-2xl tracking-tight font-semibold mt-1">
                            Afíliate a 10 productos en 60 segundos
                        </h2>
                        <p className="text-xs text-[#52525B] mt-1 max-w-xl">
                            Selecciona las oportunidades con mayor prioridad · abrimos las búsquedas en Hotmart · te afilias con 1 clic en cada una · sincronizamos los hotlinks automáticos.
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        data-testid="close-wizard-btn"
                        className="p-2 hard-border surface-hover"
                    >
                        <X size={14} weight="bold" />
                    </button>
                </div>

                {/* Stepper */}
                <div className="hard-border-b px-6 sm:px-8 py-3 flex items-center gap-4 text-xs">
                    <StepPill n={1} label="Selecciona" active={step === 1} done={step > 1} />
                    <div className="flex-1 h-px bg-[#E4E4E7]" />
                    <StepPill n={2} label="Afíliate" active={step === 2} done={step > 2} />
                    <div className="flex-1 h-px bg-[#E4E4E7]" />
                    <StepPill n={3} label="Sincroniza" active={step === 3} done={false} />
                </div>

                {/* Body */}
                <div className="flex-1 overflow-y-auto">
                    {loading && <div className="linear-progress" />}

                    {!loading && opportunities.length === 0 && (
                        <div className="p-10 text-center">
                            <div className="font-display text-lg font-semibold mb-1">
                                Sin oportunidades todavía
                            </div>
                            <p className="text-sm text-[#52525B]">
                                Ejecuta primero la investigación del Módulo 1.
                            </p>
                        </div>
                    )}

                    {!loading && opportunities.length > 0 && (
                        <div className="divide-y divide-[#E4E4E7]">
                            {opportunities.map((o, i) => {
                                const id = `${o.country_code}-${i}`;
                                const isSelected = selected.has(id);
                                const isOpened = opened.has(id);
                                const intentStyle =
                                    INTENT_STYLES[o.commercial_intent] ||
                                    INTENT_STYLES.Media;
                                return (
                                    <label
                                        key={id}
                                        data-testid={`opportunity-row-${i}`}
                                        className={`flex items-center gap-4 px-6 sm:px-8 py-4 cursor-pointer surface-hover ${
                                            isSelected
                                                ? "bg-[#FAFAFA]"
                                                : ""
                                        }`}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={isSelected}
                                            onChange={() => toggle(id)}
                                            data-testid={`opportunity-checkbox-${i}`}
                                            className="w-4 h-4 accent-[#09090b]"
                                        />
                                        <div className="mono text-xs w-10 text-[#a1a1aa]">
                                            {o.country_code}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="font-medium text-sm">
                                                {o.keyword}
                                            </div>
                                            <div className="text-xs text-[#52525B] truncate mt-0.5">
                                                {o.pain_point}
                                            </div>
                                        </div>
                                        <span
                                            className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium"
                                            style={{
                                                background: intentStyle.bg,
                                                color: intentStyle.fg,
                                                border: `1px solid ${intentStyle.border}`,
                                            }}
                                        >
                                            {o.commercial_intent}
                                        </span>
                                        <div className="mono text-sm font-semibold w-10 text-right">
                                            {o.priority_score}
                                        </div>
                                        <a
                                            href={o.hotmart_discovery_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setOpened((prev) => {
                                                    const next = new Set(prev);
                                                    next.add(id);
                                                    return next;
                                                });
                                            }}
                                            data-testid={`open-opportunity-${i}`}
                                            className="inline-flex items-center gap-1 px-2.5 py-1.5 hard-border surface-hover text-xs font-medium"
                                        >
                                            {isOpened ? (
                                                <>
                                                    <CheckCircle
                                                        size={12}
                                                        weight="fill"
                                                        color="#16A34A"
                                                    />
                                                    Abierto
                                                </>
                                            ) : (
                                                <>
                                                    <ArrowSquareOut
                                                        size={12}
                                                        weight="bold"
                                                    />
                                                    Abrir
                                                </>
                                            )}
                                        </a>
                                    </label>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Footer / Actions */}
                <div className="hard-border-t px-6 sm:px-8 py-4 flex flex-wrap items-center justify-between gap-3">
                    <div className="text-xs text-[#52525B]">
                        {selected.size} de {opportunities.length} seleccionadas
                        {opened.size > 0 && (
                            <>
                                {" · "}
                                <span className="mono text-[#09090b] font-semibold">
                                    {opened.size} abiertas
                                </span>
                            </>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        {step < 2 && (
                            <button
                                data-testid="open-all-btn"
                                onClick={openAllSelected}
                                disabled={selected.size === 0}
                                className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#09090b] text-white text-xs font-medium uppercase tracking-wide hover:bg-[#27272a] disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <Target size={13} weight="bold" />
                                Abrir las {selected.size} seleccionadas
                            </button>
                        )}
                        {step >= 2 && (
                            <>
                                <button
                                    onClick={openAllSelected}
                                    data-testid="reopen-btn"
                                    className="inline-flex items-center gap-1 px-3 py-2 hard-border surface-hover text-xs font-medium"
                                >
                                    Abrir de nuevo
                                </button>
                                <button
                                    data-testid="sync-wizard-btn"
                                    onClick={handleSync}
                                    disabled={syncing}
                                    className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#09090b] text-white text-xs font-medium uppercase tracking-wide hover:bg-[#27272a] disabled:opacity-50"
                                >
                                    <Lightning
                                        size={13}
                                        weight="bold"
                                        className={syncing ? "animate-pulse" : ""}
                                    />
                                    {syncing
                                        ? "Sincronizando…"
                                        : "Ya me afilié — Sincronizar"}
                                </button>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

function StepPill({ n, label, active, done }) {
    const bg = done ? "#16A34A" : active ? "#09090B" : "#E4E4E7";
    const fg = done || active ? "#ffffff" : "#52525B";
    return (
        <div className="flex items-center gap-2">
            <div
                className="w-5 h-5 flex items-center justify-center font-mono text-[10px] font-bold"
                style={{ background: bg, color: fg, borderRadius: "50%" }}
            >
                {done ? "✓" : n}
            </div>
            <span
                className={`mono text-xs ${
                    active ? "font-semibold text-[#09090b]" : "text-[#52525B]"
                }`}
            >
                {label}
            </span>
        </div>
    );
}
