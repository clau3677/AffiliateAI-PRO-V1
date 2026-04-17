import React, { useCallback, useEffect, useRef, useState } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster, toast } from "sonner";
import { MapTrifold, Sparkle, Stack } from "@phosphor-icons/react";

import Navbar from "@/components/Navbar";
import CountryCard from "@/components/CountryCard";
import CountryDetail from "@/components/CountryDetail";
import ExecutionStatus from "@/components/ExecutionStatus";
import HotmartAccountPanel from "@/components/HotmartAccountPanel";

import {
    fetchOverview,
    runResearch,
    getExecution,
    listExecutions,
} from "@/lib/api";

function Dashboard() {
    const [overview, setOverview] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState(null);
    const [execution, setExecution] = useState(null);
    const pollRef = useRef(null);

    const loadOverview = useCallback(async () => {
        try {
            const data = await fetchOverview();
            setOverview(data);
        } catch (e) {
            console.error(e);
            toast.error("No se pudo cargar la información");
        } finally {
            setLoading(false);
        }
    }, []);

    const loadLastExecution = useCallback(async () => {
        try {
            const list = await listExecutions();
            if (list && list.length > 0) {
                setExecution(list[0]);
                if (["pending", "running"].includes(list[0].status)) {
                    startPolling(list[0].id);
                }
            }
        } catch (e) {
            console.error(e);
        }
    }, []);

    useEffect(() => {
        loadOverview();
        loadLastExecution();
        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
        };
    }, [loadOverview, loadLastExecution]);

    const startPolling = (execId) => {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(async () => {
            try {
                const exec = await getExecution(execId);
                setExecution(exec);
                // Refresh overview each tick so tiles update live
                loadOverview();
                if (exec.status === "completed" || exec.status === "failed") {
                    clearInterval(pollRef.current);
                    pollRef.current = null;
                    if (exec.status === "completed") {
                        toast.success("Investigación completada");
                    } else {
                        toast.error("La investigación falló");
                    }
                }
            } catch (e) {
                console.error(e);
            }
        }, 2500);
    };

    const handleRun = async () => {
        try {
            const res = await runResearch();
            toast.success(
                `Investigación iniciada para ${res.countries.length} países`,
            );
            setExecution({
                id: res.execution_id,
                status: "running",
                progress: 0,
                trends_processed: 0,
                total_expected: res.total_expected,
                countries: res.countries,
            });
            startPolling(res.execution_id);
        } catch (e) {
            console.error(e);
            toast.error("No se pudo iniciar la investigación");
        }
    };

    const running =
        execution &&
        ["pending", "running"].includes(execution.status);

    const totalTrends = overview.reduce((s, c) => s + c.total_trends, 0);
    const highPriorityCount = overview.filter(
        (c) => c.recommendation_priority === "HIGH",
    ).length;

    return (
        <div className="min-h-screen">
            <Navbar
                onRun={handleRun}
                running={running}
                onRefresh={loadOverview}
            />

            <main className="max-w-[1600px] mx-auto px-6 sm:px-8 md:px-12 py-10 space-y-10">
                {/* Hero stats */}
                <section className="widget-enter">
                    <div className="overline mb-2">
                        Panel Regional · Sudamérica
                    </div>
                    <h1 className="font-display text-4xl sm:text-5xl tracking-tight font-bold max-w-3xl">
                        Inteligencia de mercado para creadores y afiliados.
                    </h1>
                    <p className="text-sm sm:text-base text-[#52525B] mt-4 max-w-2xl">
                        Google Trends + análisis con Claude Sonnet 4.5 identifican
                        qué están buscando los consumidores de Argentina, Chile,
                        Colombia, Perú y Brasil — con prioridad comercial y
                        punto de dolor por keyword.
                    </p>
                </section>

                {/* Stat strip */}
                <section
                    className="grid grid-cols-2 md:grid-cols-4 hard-border surface widget-enter"
                    data-testid="stat-strip"
                >
                    <StatCell
                        label="Países monitoreados"
                        value={overview.length}
                        icon={<MapTrifold size={14} weight="bold" />}
                        testid="stat-countries"
                    />
                    <StatCell
                        label="Tendencias recolectadas"
                        value={totalTrends}
                        icon={<Stack size={14} weight="bold" />}
                        testid="stat-total-trends"
                    />
                    <StatCell
                        label="Oportunidades alta prioridad"
                        value={highPriorityCount}
                        icon={<Sparkle size={14} weight="bold" />}
                        testid="stat-high-priority"
                        highlight={highPriorityCount > 0}
                    />
                    <StatCell
                        label="Modelo LLM"
                        value="Claude 4.5"
                        testid="stat-llm"
                        mono={false}
                    />
                </section>

                {execution && <ExecutionStatus execution={execution} />}

                <HotmartAccountPanel />

                {/* Countries grid */}
                <section>
                    <div className="flex items-end justify-between mb-6">
                        <div>
                            <div className="overline">01</div>
                            <h2 className="font-display text-2xl sm:text-3xl tracking-tight font-semibold">
                                Países objetivo
                            </h2>
                        </div>
                        <span
                            className="overline"
                            data-testid="countries-count"
                        >
                            {overview.length} mercados
                        </span>
                    </div>

                    {loading ? (
                        <div
                            data-testid="overview-loading"
                            className="linear-progress"
                        />
                    ) : (
                        <div
                            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
                            data-testid="country-grid"
                        >
                            {overview.map((c, i) => (
                                <CountryCard
                                    key={c.code}
                                    country={c}
                                    index={i}
                                    onSelect={setSelected}
                                />
                            ))}
                        </div>
                    )}
                </section>

                {/* How it works */}
                <section
                    className="hard-border surface p-8 widget-enter"
                    data-testid="how-it-works"
                >
                    <div className="overline mb-3">Cómo funciona</div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                        <Step
                            n="01"
                            title="Recolección"
                            body="Pytrends consulta Google Trends por keywords semilla de cada país (últimos 3 meses, idioma local)."
                        />
                        <Step
                            n="02"
                            title="Análisis IA"
                            body="Claude Sonnet 4.5 enriquece cada keyword con punto de dolor, intención comercial y score de prioridad 0–100."
                        />
                        <Step
                            n="03"
                            title="Resumen accionable"
                            body="MongoDB almacena las tendencias listas para el Módulo 2: matching con productos Hotmart."
                        />
                    </div>
                </section>

                <footer className="hard-border-t pt-8 pb-4 flex flex-col sm:flex-row justify-between items-start gap-3 text-xs text-[#52525B]">
                    <span className="overline">
                        Hotmart Super Agent · Módulo 1 v1.0
                    </span>
                    <span>
                        Datos: Google Trends · Análisis: Claude Sonnet 4.5 vía
                        Emergent LLM
                    </span>
                </footer>
            </main>

            {selected && (
                <CountryDetail
                    country={selected}
                    onClose={() => setSelected(null)}
                    onChanged={loadOverview}
                />
            )}

            <Toaster position="top-right" richColors />
        </div>
    );
}

function StatCell({ label, value, icon, testid, highlight = false, mono = true }) {
    return (
        <div
            className="p-6 border-r border-b md:border-b-0 last:border-r-0 hard-border-b md:hard-border-b-0 border-[#E4E4E7]"
            data-testid={testid}
        >
            <div className="overline flex items-center gap-1.5">
                {icon}
                {label}
            </div>
            <div
                className={`${mono ? "mono" : "font-display"} text-3xl font-semibold mt-2 ${
                    highlight ? "text-[#DC2626]" : ""
                }`}
            >
                {value}
            </div>
        </div>
    );
}

function Step({ n, title, body }) {
    return (
        <div>
            <div className="mono text-xs text-[#a1a1aa] mb-2">{n}</div>
            <div className="font-display text-lg font-semibold tracking-tight mb-1">
                {title}
            </div>
            <p className="text-sm text-[#52525B] leading-relaxed">{body}</p>
        </div>
    );
}

function App() {
    return (
        <div className="App">
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<Dashboard />} />
                </Routes>
            </BrowserRouter>
        </div>
    );
}

export default App;
