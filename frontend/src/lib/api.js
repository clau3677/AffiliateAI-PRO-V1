import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
    baseURL: API,
    timeout: 30000,
});

export const fetchCountries = () => api.get("/countries").then((r) => r.data);
export const fetchOverview = () =>
    api.get("/research/overview").then((r) => r.data);
export const fetchTrends = (code, sortBy = "priority_score") =>
    api
        .get(`/research/trends/${code}`, { params: { sort_by: sortBy } })
        .then((r) => r.data);
export const fetchSummary = (code) =>
    api.get(`/research/summary/${code}`).then((r) => r.data);
export const runResearch = (countries = null) =>
    api.post("/research/run", { countries }).then((r) => r.data);
export const getExecution = (id) =>
    api.get(`/research/executions/${id}`).then((r) => r.data);
export const listExecutions = () =>
    api.get("/research/executions").then((r) => r.data);
export const clearCountry = (code) =>
    api.delete(`/research/trends/${code}`).then((r) => r.data);

// ---- Module 2: Hotmart products ----
export const fetchHotmartStatus = () =>
    api.get("/hotmart/status").then((r) => r.data);
export const testHotmartConnection = () =>
    api.get("/hotmart/test-connection").then((r) => r.data);
export const fetchProducts = (code, limit = 30) =>
    api
        .get(`/products/${code}`, { params: { limit } })
        .then((r) => r.data);
export const startMatching = (code, limit = 10, autoLinks = true) =>
    api
        .post("/products/match", {
            country_code: code,
            limit,
            auto_links: autoLinks,
        })
        .then((r) => r.data);
export const getMatchingExecution = (id) =>
    api.get(`/products/executions/${id}`).then((r) => r.data);
export const generateAffiliateLink = (code, hotmartId, force = false) =>
    api
        .get(`/products/${code}/${hotmartId}/affiliate-link`, {
            params: { force },
        })
        .then((r) => r.data);
export const clearProducts = (code) =>
    api.delete(`/products/${code}`).then((r) => r.data);

// ---- Hotmart live data ----
export const fetchMyAffiliations = () =>
    api.get("/hotmart/my-affiliations").then((r) => r.data);
export const fetchSalesSummary = () =>
    api.get("/hotmart/sales-summary").then((r) => r.data);
export const fetchSalesHistory = (maxResults = 10) =>
    api
        .get("/hotmart/sales-history", { params: { max_results: maxResults } })
        .then((r) => r.data);
export const fetchCommissions = (maxResults = 10) =>
    api
        .get("/hotmart/commissions", { params: { max_results: maxResults } })
        .then((r) => r.data);
export const rematchAllCountries = () =>
    api.post("/hotmart/rematch-all").then((r) => r.data);

// ---- Módulo RPA: Automatización Hotmart ----
export const fetchRPAStatus = () =>
    api.get("/rpa/status").then((r) => r.data);
export const startRPASession = (keywords, countryCode, manual2fa = null, headless = true) =>
    api
        .post("/rpa/start", {
            keywords,
            country_code: countryCode,
            manual_2fa_code: manual2fa,
            headless,
        })
        .then((r) => r.data);
export const fetchRPASession = (sessionId) =>
    api.get(`/rpa/sessions/${sessionId}`).then((r) => r.data);
export const fetchRPASessions = (limit = 20) =>
    api.get("/rpa/sessions", { params: { limit } }).then((r) => r.data);
export const provide2FACode = (sessionId, code) =>
    api.post(`/rpa/sessions/${sessionId}/2fa`, null, { params: { code } }).then((r) => r.data);
export const saveRPAAffiliations = (sessionId) =>
    api.post("/rpa/save-affiliations", null, { params: { session_id: sessionId } }).then((r) => r.data);
