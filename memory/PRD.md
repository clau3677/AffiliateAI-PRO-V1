# Hotmart Super Agent — PRD

## Original Problem Statement
Sistema de agente que investiga necesidades reales en Sudamérica (AR, CL, CO, PE, BR) usando Google Trends + LLM para identificar oportunidades, y empareja automáticamente con productos Hotmart afiliados por el usuario para generar hotlinks listos para promocionar. Toda la cadena debe ser automática: cero botones manuales, cero copy/paste de links.

## Architecture
- **Backend**: FastAPI + MongoDB (motor) + pytrends + emergentintegrations (Claude Sonnet 4.5) + APScheduler + Hotmart OAuth API.
- **Frontend**: React 19 + Tailwind + Shadcn + Phosphor Icons + sonner.
- **Módulo 1**: `/api/research/run` → Google Trends por país → Claude enriquece (pain_point, commercial_intent, priority_score) → MongoDB `trends`.
- **Módulo 2 (automático)**: `/api/hotmart/rematch-all` → sincroniza afiliaciones reales del usuario (`GET /affiliation/v2/affiliates/products`) → matchea contra pain points → upsert en `products` con `is_my_affiliation=true` + `affiliate_link` (hotlink real).

## User Personas
- Creadores / afiliados Hotmart en Latam que necesitan saber qué se demanda por país.
- Marketers regionales priorizando keywords por intención comercial real.

## Core Requirements
1. Investigar 5 países sudamericanos con Google Trends + Claude.
2. Clasificar por intención comercial (Alta/Media/Baja) y priority_score 0-100.
3. Dashboard en español con trends y productos matcheados.
4. Pipeline Hotmart 100% automático (sin inputs manuales, sin copy/paste).
5. Si el usuario no tiene afiliación para un trend, UI muestra CTA directo a Hotmart Affiliates Panel.

## Implemented (2026-04-17)
### Módulo 1
- Endpoints: `/api/health`, `/api/countries`, `/api/research/run`, `/api/research/executions[/{id}]`, `/api/research/overview`, `/api/research/trends/{code}` (GET/DELETE, sort_by), `/api/research/summary/{code}`.
- Orquestador background con delays éticos; fallback heurístico si LLM falla.
- Upsert `(country_code, keyword)` sin duplicados.

### Módulo 2 — Hotmart automatizado (iteración actual)
- Credenciales OAuth Hotmart configuradas con scopes productivos. `test-connection` devuelve `scopes_ok:true`.
- **Pipeline automático único**: `POST /api/hotmart/rematch-all` sincroniza afiliaciones reales + reejecuta matching para los 5 países en background.
- `match_and_score` (backend/hotmart.py) prioriza siempre `is_my_affiliation=true` con hotlink real; rellena con discovery (scraping + LLM) cuando hay menos afiliaciones que el limit.
- `match_real_affiliations_to_trends`: fuzzy match título+categoría vs keywords del trend.
- Endpoints data viva: `/api/hotmart/my-affiliations`, `/sales-summary`, `/sales-history`, `/commissions`, `/status`, `/test-connection`.

### UI limpia (sin flujo manual)
- `HotmartAccountPanel`: único botón **"Sincronizar y auto-enlazar"** (data-testid `sync-affiliations-btn`). Empty state explica al usuario: afíliate UNA VEZ en `app-vlc.hotmart.com/affiliates`, vuelve y sincroniza.
- `ProductCard` reescrito:
  - Si `is_my_affiliation && hasLink` → banner verde "Hotlink auto-generado" + botón Copiar.
  - Si no → aviso amarillo "Aún no estás afiliado" + 2 botones: "Ver producto" (abre `product_url`) y "Afiliarme" (abre panel Hotmart).
  - ❌ Eliminado: input manual de link, botones Guardar/Borrar, panel de ayuda amarillo.

### Código eliminado en esta iteración
- `ExpressAffiliationWizard.jsx` (componente completo).
- `/api/hotmart/express-wizard` (endpoint).
- `/api/hotmart/sync-affiliations` standalone (consolidado dentro de `/rematch-all`).
- `PATCH /api/products/{code}/{id}/manual-link` y su `DELETE`.
- `ManualLinkPayload` model.
- Frontend: `fetchExpressWizard`, `saveManualAffiliateLink`, `clearManualAffiliateLink`, `syncAffiliations` en `lib/api.js`.
- Tests obsoletos: `tests/test_express_wizard.py`, `tests/test_manual_link.py`, `TestHotmartSyncAffiliations`, `TestModule2Placeholder`, y tests de manual-link dentro de `test_auto_sync.py`.

## Verified
- `curl /api/health` → ok
- `curl /api/hotmart/test-connection` → `scopes_ok:true`
- `curl /api/hotmart/express-wizard` → 404 (correctamente eliminado)
- `curl /api/products/AR/X/manual-link` (PATCH) → 404 (correctamente eliminado)
- `curl /api/hotmart/rematch-all` → `status:started`, execution_id, 5 países
- Testing agent (backend + code review): 5 endpoints eliminados confirman 404; UI confirmada sin referencias rotas.
- Tests rápidos 20/20 passing.
- Lint Python y JS limpios en archivos de producción.

## Backlog
### P1
- Generar copy/anuncio automáticamente por producto+país (pedido del usuario para próxima iteración).
- Export CSV/JSON de productos matcheados con hotlink.

### P2
- Ampliar a 10 países sudamericanos (BO, EC, PY, UY, VE).
- Fuentes adicionales (MercadoLibre, foros locales) para pain points no comerciales.
- Autenticación multi-usuario con workspaces aislados.
- Cron diario de re-sync automático de afiliaciones (además del weekly existente).

## Credentials
- `EMERGENT_LLM_KEY` configurado — da acceso a Claude Sonnet 4.5.
- `HOTMART_CLIENT_ID`, `HOTMART_CLIENT_SECRET`, `HOTMART_BASIC_AUTH` configurados con scopes productivos.
- Hotmart UI login (para afiliarse manualmente a productos): `Traficoclaudio@gmail.com` → panel `https://app-vlc.hotmart.com/affiliates`.
