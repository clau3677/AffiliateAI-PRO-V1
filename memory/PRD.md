# Hotmart Super Agent — Módulo 1 (Investigación de Mercado)

## Original Problem Statement
Sistema de agente que investiga necesidades reales en Sudamérica (AR, CL, CO, PE, BR) usando Google Trends + LLM para identificar oportunidades de productos Hotmart. Módulo 1 = investigación de mercado. Módulo 2 (futuro) = selector de productos Hotmart.

## Architecture
- **Backend**: FastAPI (Python), MongoDB (motor async), pytrends, emergentintegrations (Claude Sonnet 4.5)
- **Frontend**: React 19 + Tailwind + Shadcn + Phosphor Icons + sonner (toasts)
- **Data flow**: `/api/research/run` → background task → pytrends (Google Trends per country) → Claude Sonnet 4.5 enrichment (pain_point, commercial_intent, priority_score, suggested_product_type) → MongoDB `trends` collection.

## User Personas
- **Creadores / afiliados Hotmart** en Latam que necesitan saber qué demanda real existe por país.
- **Marketers regionales** que quieren priorizar keywords por intención comercial y dolor.

## Core Requirements (static)
1. Investigar 5 países sudamericanos (AR, CL, CO, PE, BR) con keywords semilla por país.
2. Combinar Google Trends real + análisis IA (Claude Sonnet 4.5).
3. Clasificar por intención comercial (Alta/Media/Baja) y score de prioridad 0-100.
4. Dashboard web en español para visualizar resultados.
5. Estructura lista para el Módulo 2 (matching con productos Hotmart).

## Implemented (2026-04-17)
- Backend endpoints: `/api/health`, `/api/countries`, `/api/research/run`, `/api/research/executions[/{id}]`, `/api/research/overview`, `/api/research/trends/{code}` (GET/DELETE, sort_by), `/api/research/summary/{code}`, `/api/products/match/{code}` (501 placeholder).
- Orquestador background que procesa países en secuencia con delays éticos.
- Fallback heurístico cuando LLM falla.
- Upsert en MongoDB por (country_code, keyword) → sin duplicados.
- Dashboard Swiss/high-contrast: stat strip, country cards, detalle modal con resumen ejecutivo + tabla sortable/filtrable de tendencias.
- Execution tracker con progress bar y polling cada 2.5s.
- Toasts (sonner) para feedback del usuario.
- 100% test pass (19 backend + 8 frontend).

## Backlog
- **P0 — Módulo 2 (Hotmart Product Selector)**: integrar `hotmart-python` SDK oficial. Matching automático pain_point → producto. Ranking por comisión/rating/conversión.
- **P1**: Programar ejecuciones automáticas (cron / scheduler) para refrescar tendencias semanalmente.
- **P1**: Export CSV/JSON de tendencias y resúmenes ejecutivos.
- **P2**: Expandir a los 10 países sudamericanos (BO, EC, PY, UY, VE).
- **P2**: Integrar fuentes adicionales (MercadoLibre, foros locales) con LLM para extraer pain points no comerciales.
- **P2**: Autenticación por usuario y separación de datos por workspace.

## Credentials
- `EMERGENT_LLM_KEY` ya configurado en `/app/backend/.env`. Da acceso a Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`).
