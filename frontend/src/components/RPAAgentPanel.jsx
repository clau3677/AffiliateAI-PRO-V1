import React, { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Alert, AlertDescription } from "./ui/alert";
import { Progress } from "./ui/progress";

const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// ─── API helpers ─────────────────────────────────────────────────────────────

async function fetchRPAStatus() {
  const r = await fetch(`${API_BASE}/api/rpa/status`);
  return r.json();
}

async function startRPASession(keywords, countryCode, manual2fa, headless) {
  const r = await fetch(`${API_BASE}/api/rpa/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      keywords,
      country_code: countryCode,
      manual_2fa_code: manual2fa || null,
      headless,
    }),
  });
  return r.json();
}

async function fetchSession(sessionId) {
  const r = await fetch(`${API_BASE}/api/rpa/sessions/${sessionId}`);
  return r.json();
}

async function fetchSessions() {
  const r = await fetch(`${API_BASE}/api/rpa/sessions?limit=10`);
  return r.json();
}

async function saveAffiliations(sessionId) {
  const r = await fetch(
    `${API_BASE}/api/rpa/save-affiliations?session_id=${sessionId}`,
    { method: "POST" }
  );
  return r.json();
}

// ─── Sub-componentes ──────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const map = {
    pending:   { label: "Pendiente",   color: "bg-yellow-100 text-yellow-800" },
    running:   { label: "Ejecutando",  color: "bg-blue-100 text-blue-800" },
    completed: { label: "Completado",  color: "bg-green-100 text-green-800" },
    error:     { label: "Error",       color: "bg-red-100 text-red-800" },
    login_failed: { label: "Login fallido", color: "bg-red-100 text-red-800" },
    waiting_2fa:  { label: "Esperando 2FA", color: "bg-purple-100 text-purple-800" },
  };
  const { label, color } = map[status] || { label: status, color: "bg-gray-100 text-gray-800" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

function AffiliationCard({ aff }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    if (aff.hotlink) {
      navigator.clipboard.writeText(aff.hotlink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };
  return (
    <div className="border rounded-lg p-3 bg-white space-y-1">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-gray-900 truncate">{aff.title || aff.product_id}</p>
        <StatusBadge status={aff.status} />
      </div>
      {aff.affiliate_code && (
        <p className="text-xs text-gray-500">
          Código afiliado:{" "}
          <span className="font-mono font-bold text-indigo-600">{aff.affiliate_code}</span>
        </p>
      )}
      {aff.hotlink && (
        <div className="flex items-center gap-2 mt-1">
          <input
            readOnly
            value={aff.hotlink}
            className="flex-1 text-xs border rounded px-2 py-1 bg-gray-50 font-mono truncate"
          />
          <button
            onClick={copy}
            className="text-xs px-2 py-1 rounded bg-indigo-600 text-white hover:bg-indigo-700 transition"
          >
            {copied ? "✓" : "Copiar"}
          </button>
        </div>
      )}
      {aff.keyword && (
        <p className="text-xs text-gray-400">Keyword: {aff.keyword}</p>
      )}
    </div>
  );
}

// ─── Panel principal ──────────────────────────────────────────────────────────

export default function RPAAgentPanel() {
  const [rpaStatus, setRpaStatus] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Formulario
  const [keywords, setKeywords] = useState("");
  const [countryCode, setCountryCode] = useState("CL");
  const [manual2fa, setManual2fa] = useState("");
  const [headless, setHeadless] = useState(true);
  const [show2faInput, setShow2faInput] = useState(false);

  // Cargar estado inicial
  const loadStatus = useCallback(async () => {
    try {
      const s = await fetchRPAStatus();
      setRpaStatus(s);
    } catch (e) {
      setError("No se pudo conectar al backend RPA.");
    }
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      const s = await fetchSessions();
      setSessions(Array.isArray(s) ? s : []);
    } catch (e) {}
  }, []);

  useEffect(() => {
    loadStatus();
    loadSessions();
  }, [loadStatus, loadSessions]);

  // Polling de sesión activa
  useEffect(() => {
    if (!activeSession || ["completed", "error", "login_failed"].includes(activeSession.status)) return;
    const interval = setInterval(async () => {
      try {
        const updated = await fetchSession(activeSession.id);
        setActiveSession(updated);
        if (["completed", "error", "login_failed"].includes(updated.status)) {
          loadSessions();
          clearInterval(interval);
        }
      } catch (e) {}
    }, 3000);
    return () => clearInterval(interval);
  }, [activeSession, loadSessions]);

  // Iniciar sesión RPA
  const handleStart = async () => {
    setError(null);
    const kws = keywords.split(",").map((k) => k.trim()).filter(Boolean);
    if (kws.length === 0) {
      setError("Ingresa al menos una keyword.");
      return;
    }
    setLoading(true);
    try {
      const result = await startRPASession(kws, countryCode, manual2fa || null, headless);
      if (result.session_id) {
        const session = await fetchSession(result.session_id);
        setActiveSession(session);
        loadSessions();
      } else {
        setError(result.detail || "Error al iniciar la sesión RPA.");
      }
    } catch (e) {
      setError("Error de conexión al iniciar el agente.");
    } finally {
      setLoading(false);
    }
  };

  // Guardar afiliaciones en MongoDB
  const handleSave = async () => {
    if (!activeSession) return;
    setLoading(true);
    try {
      const result = await saveAffiliations(activeSession.id);
      alert(`✅ ${result.affiliations_saved} afiliaciones guardadas en la base de datos.`);
    } catch (e) {
      setError("Error al guardar afiliaciones.");
    } finally {
      setLoading(false);
    }
  };

  const progressValue = activeSession
    ? activeSession.progress || (activeSession.status === "completed" ? 100 : activeSession.status === "running" ? 50 : 0)
    : 0;

  const affiliations = activeSession?.result?.affiliations || [];
  const successfulAffiliations = affiliations.filter((a) => a.affiliate_code);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">🤖 Agente RPA Hotmart</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Automatiza login, afiliación y extracción de códigos de afiliado
          </p>
        </div>
        {rpaStatus && (
          <div className="flex gap-2">
            <Badge variant={rpaStatus.rpa_credentials_configured ? "default" : "destructive"}>
              {rpaStatus.rpa_credentials_configured ? "✅ Credenciales OK" : "❌ Sin credenciales"}
            </Badge>
            <Badge variant={rpaStatus.email_2fa_configured ? "default" : "secondary"}>
              {rpaStatus.email_2fa_configured ? "✅ 2FA Auto" : "⚠️ 2FA Manual"}
            </Badge>
          </div>
        )}
      </div>

      {/* Alerta de credenciales faltantes */}
      {rpaStatus && !rpaStatus.rpa_credentials_configured && (
        <Alert className="border-amber-200 bg-amber-50">
          <AlertDescription className="text-amber-800 text-sm">
            <strong>Configura las credenciales RPA</strong> en{" "}
            <code className="bg-amber-100 px-1 rounded">backend/.env</code>:
            <br />
            <code>HOTMART_EMAIL=tu@email.com</code>
            <br />
            <code>HOTMART_PASSWORD=tu_contraseña</code>
            <br />
            <span className="text-xs mt-1 block text-amber-600">
              Opcional para 2FA automático: GMAIL_EMAIL + GMAIL_APP_PASSWORD
            </span>
          </AlertDescription>
        </Alert>
      )}

      {/* Formulario de inicio */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Iniciar Automatización</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">
              Keywords (separadas por coma)
            </label>
            <Input
              placeholder="ej: curso marketing, finanzas personales, inglés"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              disabled={loading}
            />
            <p className="text-xs text-gray-400 mt-1">
              El agente buscará productos en Hotmart para cada keyword y se afiliará automáticamente.
            </p>
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="text-sm font-medium text-gray-700 block mb-1">País</label>
              <select
                className="w-full border rounded-md px-3 py-2 text-sm bg-white"
                value={countryCode}
                onChange={(e) => setCountryCode(e.target.value)}
                disabled={loading}
              >
                <option value="CL">🇨🇱 Chile</option>
                <option value="AR">🇦🇷 Argentina</option>
                <option value="CO">🇨🇴 Colombia</option>
                <option value="MX">🇲🇽 México</option>
                <option value="PE">🇵🇪 Perú</option>
                <option value="BR">🇧🇷 Brasil</option>
                <option value="ES">🇪🇸 España</option>
              </select>
            </div>

            <div className="flex items-end gap-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={headless}
                  onChange={(e) => setHeadless(e.target.checked)}
                  className="rounded"
                  disabled={loading}
                />
                <span className="text-sm text-gray-700">Modo silencioso</span>
              </label>
            </div>
          </div>

          {/* 2FA Manual */}
          <div>
            <button
              type="button"
              className="text-xs text-indigo-600 hover:underline"
              onClick={() => setShow2faInput(!show2faInput)}
            >
              {show2faInput ? "▲ Ocultar" : "▼ Tengo código 2FA manual"}
            </button>
            {show2faInput && (
              <div className="mt-2">
                <Input
                  placeholder="Código 2FA (6 dígitos)"
                  value={manual2fa}
                  onChange={(e) => setManual2fa(e.target.value)}
                  maxLength={6}
                  className="max-w-xs"
                  disabled={loading}
                />
                <p className="text-xs text-gray-400 mt-1">
                  Solo si Hotmart pide verificación y no tienes 2FA automático configurado.
                </p>
              </div>
            )}
          </div>

          {error && (
            <Alert className="border-red-200 bg-red-50">
              <AlertDescription className="text-red-700 text-sm">{error}</AlertDescription>
            </Alert>
          )}

          <Button
            onClick={handleStart}
            disabled={loading || (rpaStatus && !rpaStatus.rpa_credentials_configured)}
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white"
          >
            {loading ? "⏳ Iniciando..." : "🚀 Iniciar Agente RPA"}
          </Button>
        </CardContent>
      </Card>

      {/* Sesión activa */}
      {activeSession && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Sesión Activa</CardTitle>
              <StatusBadge status={activeSession.status} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-xs text-gray-500 font-mono bg-gray-50 rounded px-2 py-1">
              ID: {activeSession.id}
            </div>

            {/* Progreso */}
            {["running", "pending"].includes(activeSession.status) && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-500">
                  <span>Progreso</span>
                  <span>{progressValue}%</span>
                </div>
                <Progress value={progressValue} className="h-2" />
                <p className="text-xs text-gray-400 animate-pulse">
                  {activeSession.status === "running"
                    ? "🤖 El agente está trabajando... (login → búsqueda → afiliación → extracción de códigos)"
                    : "⏳ Iniciando agente..."}
                </p>
              </div>
            )}

            {/* Resultado del login */}
            {activeSession.result?.login && (
              <div className="text-xs">
                <span className="font-medium">Login: </span>
                <StatusBadge status={activeSession.result.login.status} />
                {activeSession.result.login.error && (
                  <span className="text-red-600 ml-2">{activeSession.result.login.error}</span>
                )}
              </div>
            )}

            {/* Resumen */}
            {activeSession.status === "completed" && (
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center bg-blue-50 rounded-lg p-3">
                  <p className="text-2xl font-bold text-blue-700">
                    {activeSession.result?.products_found || 0}
                  </p>
                  <p className="text-xs text-blue-600">Productos encontrados</p>
                </div>
                <div className="text-center bg-green-50 rounded-lg p-3">
                  <p className="text-2xl font-bold text-green-700">
                    {successfulAffiliations.length}
                  </p>
                  <p className="text-xs text-green-600">Códigos extraídos</p>
                </div>
                <div className="text-center bg-purple-50 rounded-lg p-3">
                  <p className="text-2xl font-bold text-purple-700">
                    {affiliations.length}
                  </p>
                  <p className="text-xs text-purple-600">Afiliaciones totales</p>
                </div>
              </div>
            )}

            {/* Lista de afiliaciones */}
            {affiliations.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-gray-700">
                  Afiliaciones y Códigos Extraídos
                </h4>
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {affiliations.map((aff, i) => (
                    <AffiliationCard key={i} aff={aff} />
                  ))}
                </div>
              </div>
            )}

            {/* Errores */}
            {activeSession.result?.errors?.length > 0 && (
              <Alert className="border-red-200 bg-red-50">
                <AlertDescription className="text-red-700 text-xs">
                  {activeSession.result.errors.join(", ")}
                </AlertDescription>
              </Alert>
            )}

            {/* Botón guardar */}
            {activeSession.status === "completed" && successfulAffiliations.length > 0 && (
              <Button
                onClick={handleSave}
                disabled={loading}
                className="w-full bg-green-600 hover:bg-green-700 text-white"
              >
                💾 Guardar {successfulAffiliations.length} afiliaciones en la base de datos
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {/* Historial de sesiones */}
      {sessions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Historial de Sesiones</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between p-2 rounded border hover:bg-gray-50 cursor-pointer"
                  onClick={() => setActiveSession(s)}
                >
                  <div>
                    <p className="text-xs font-mono text-gray-500">{s.id.slice(0, 8)}...</p>
                    <p className="text-xs text-gray-600">
                      {s.keywords?.join(", ").slice(0, 40)}
                      {s.keywords?.join(", ").length > 40 ? "..." : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">{s.country_code}</span>
                    <StatusBadge status={s.status} />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
