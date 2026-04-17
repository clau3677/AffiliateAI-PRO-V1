import React, { useEffect, useState, useCallback } from "react";
import {
    ChartLineUp,
    CurrencyCircleDollar,
    Handshake,
    ArrowClockwise,
    Receipt,
    Lightning,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import {
    fetchMyAffiliations,
    fetchSalesSummary,
    fetchSalesHistory,
    fetchCommissions,
    testHotmartConnection,
    rematchAllCountries,
} from "../lib/api";

function fmtMoney(value, currency = "USD") {
    if (value === null || value === undefined) return "—";
    try {
        return new Intl.NumberFormat("es-419", {
            style: "currency",
            currency,
            maximumFractionDigits: 0,
        }).format(value);
    } catch {
        return `${value}`;
    }
}

export default function HotmartAccountPanel() {
    const [connection, setConnection] = useState(null);
    const [affiliations, setAffiliations] = useState([]);
    const [summary, setSummary] = useState(null);
    const [history, setHistory] = useState([]);
    const [commissions, setCommissions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [syncing, setSyncing] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [conn, aff, sum, hist, comm] = await Promise.all([
                testHotmartConnection().catch(() => null),
                fetchMyAffiliations().catch(() => ({ items: [] })),
                fetchSalesSummary().catch(() => null),
                fetchSalesHistory(10).catch(() => ({ items: [] })),
                fetchCommissions(10).catch(() => ({ items: [] })),
            ]);
            setConnection(conn);
            setAffiliations(aff?.items || []);
            setSummary(sum);
            setHistory(hist?.items || []);
            setCommissions(comm?.items || []);
        } catch (e) {
            toast.error("No se pudo cargar la cuenta Hotmart");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const handleSync = async () => {
        setSyncing(true);
        try {
            const res = await rematchAllCountries();
            toast.success(
                `Sincronización iniciada: ${res.synced_affiliations} afiliaciones · rematch en ${res.countries.length} países (background, ~3 min)`,
            );
            await load();
        } catch (e) {
            toast.error(
                e.response?.data?.detail || "No se pudo sincronizar Hotmart",
            );
        } finally {
            setSyncing(false);
        }
    };

    const statusColor =
        connection?.status === "ok"
            ? "#16A34A"
            : connection?.status === "oauth_ok_scopes_missing"
              ? "#D97706"
              : "#52525B";

    const totalSales = summary?.items?.[0]?.total_items ?? 0;

    return (
        <section
            className="widget-enter hard-border surface"
            data-testid="hotmart-account-panel"
        >
            <div className="hard-border-b px-6 sm:px-8 py-5 flex items-center justify-between">
                <div>
                    <div className="overline">API en vivo · Hotmart</div>
                    <h2 className="font-display text-2xl tracking-tight font-semibold mt-1">
                        Mi cuenta Hotmart
                    </h2>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 text-xs">
                        <span
                            className="inline-block w-2 h-2"
                            style={{
                                background: statusColor,
                                borderRadius: "50%",
                            }}
                        />
                        <span
                            className="mono font-medium"
                            data-testid="connection-status"
                        >
                            {connection?.status === "ok"
                                ? "Conectado"
                                : connection?.status === "oauth_ok_scopes_missing"
                                  ? "Scopes faltan"
                                  : "Desconectado"}
                        </span>
                    </div>
                    <button
                        onClick={handleSync}
                        disabled={syncing || connection?.status !== "ok"}
                        data-testid="sync-affiliations-btn"
                        className="inline-flex items-center gap-1.5 px-3 py-2 bg-[#09090b] text-white text-xs font-medium uppercase tracking-wide hover:bg-[#27272a] disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Sincroniza tus afiliaciones reales de Hotmart y las enlaza a las tendencias"
                    >
                        <Lightning
                            size={12}
                            weight="bold"
                            className={syncing ? "animate-pulse" : ""}
                        />
                        {syncing ? "Sincronizando…" : "Sincronizar y auto-enlazar"}
                    </button>
                    <button
                        onClick={load}
                        disabled={loading}
                        data-testid="refresh-hotmart-btn"
                        className="inline-flex items-center gap-1.5 px-3 py-2 hard-border surface-hover text-xs font-medium disabled:opacity-50"
                    >
                        <ArrowClockwise
                            size={12}
                            weight="bold"
                            className={loading ? "animate-spin" : ""}
                        />
                        Refrescar
                    </button>
                </div>
            </div>

            {/* Stat grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3">
                <StatCell
                    icon={<Handshake size={14} weight="bold" />}
                    label="Afiliaciones activas"
                    value={affiliations.length}
                    testid="stat-affiliations"
                />
                <StatCell
                    icon={<Receipt size={14} weight="bold" />}
                    label="Ventas totales"
                    value={totalSales}
                    testid="stat-total-sales"
                    borderLeft
                />
                <StatCell
                    icon={<CurrencyCircleDollar size={14} weight="bold" />}
                    label="Comisiones recientes"
                    value={commissions.length}
                    testid="stat-commissions"
                    borderLeft
                />
            </div>

            {/* Empty / status message */}
            {!loading &&
                totalSales === 0 &&
                affiliations.length === 0 &&
                commissions.length === 0 && (
                    <div
                        className="hard-border-t px-6 sm:px-8 py-6 text-sm text-[#52525B] leading-relaxed"
                        data-testid="hotmart-empty-state"
                    >
                        <div className="flex items-start gap-2">
                            <ChartLineUp size={18} weight="bold" className="mt-0.5" />
                            <div>
                                <p className="font-semibold text-[#09090B] mb-1">
                                    Cuenta conectada. Aún no tienes afiliaciones activas.
                                </p>
                                <p>
                                    Para activar el pipeline automático: afíliate a
                                    productos en el{" "}
                                    <a
                                        href="https://app.hotmart.com/market"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="underline font-medium text-[#09090B]"
                                        data-testid="hotmart-affiliates-link"
                                    >
                                        marketplace Hotmart
                                    </a>
                                    . Al volver, haz clic en{" "}
                                    <strong>"Sincronizar y auto-enlazar"</strong> y los
                                    hotlinks aparecerán automáticamente en cada país.
                                </p>
                            </div>
                        </div>
                    </div>
                )}

            {/* Recent commissions */}
            {commissions.length > 0 && (
                <div className="hard-border-t px-6 sm:px-8 py-5">
                    <div className="overline mb-3">Comisiones recientes</div>
                    <div className="space-y-2">
                        {commissions.slice(0, 5).map((c, i) => (
                            <div
                                key={i}
                                data-testid={`commission-row-${i}`}
                                className="flex items-center justify-between hard-border p-3 text-sm"
                            >
                                <span className="truncate flex-1 font-medium">
                                    {c.product?.name ||
                                        c.product_name ||
                                        c.transaction ||
                                        "—"}
                                </span>
                                <span className="mono font-semibold">
                                    {fmtMoney(
                                        c.commission_value || c.value,
                                        c.currency_code || "USD",
                                    )}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Affiliations list */}
            {affiliations.length > 0 && (
                <div className="hard-border-t px-6 sm:px-8 py-5">
                    <div className="overline mb-3">Mis afiliaciones</div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {affiliations.slice(0, 10).map((a, i) => (
                            <div
                                key={i}
                                data-testid={`affiliation-row-${i}`}
                                className="hard-border p-3 text-sm"
                            >
                                <div className="font-medium truncate">
                                    {a.product?.name || a.name || "—"}
                                </div>
                                <div className="overline mt-1">
                                    ID: {a.product?.id || a.id || "—"}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </section>
    );
}

function StatCell({ icon, label, value, testid, borderLeft = false }) {
    return (
        <div
            className={`p-5 ${borderLeft ? "sm:border-l" : ""} border-[#E4E4E7]`}
            data-testid={testid}
        >
            <div className="overline flex items-center gap-1.5">
                {icon}
                {label}
            </div>
            <div className="mono text-3xl font-semibold mt-2">{value}</div>
        </div>
    );
}
