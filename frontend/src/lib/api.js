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
