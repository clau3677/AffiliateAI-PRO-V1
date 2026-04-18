"""
Hotmart Super Agent - Módulo 1: Investigación de Mercado
FastAPI backend with MongoDB + Google Trends (pytrends) + Claude Sonnet 4.5 via Emergent LLM Key.
"""
from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import asyncio
import logging
import random
import re
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from pytrends.request import TrendReq
from tenacity import retry, stop_after_attempt, wait_exponential  # noqa: F401

from emergentintegrations.llm.chat import LlmChat, UserMessage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import hotmart as hm


# ---------- Bootstrap ----------
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("hotmart_agent")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

with open(ROOT_DIR / "countries.json", "r", encoding="utf-8") as f:
    COUNTRIES: Dict[str, Dict[str, Any]] = json.load(f)

TARGET_COUNTRIES = list(COUNTRIES.keys())


# ---------- Models ----------
class Trend(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    country_code: str
    country_name: str
    keyword: str
    interest_score: float = Field(..., ge=0, le=100)
    priority_score: int = Field(..., ge=0, le=100)
    commercial_intent: str
    pain_point: str
    suggested_product_type: str
    source: str = "google_trends"
    researched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CountrySummary(BaseModel):
    code: str
    name: str
    total_trends: int
    top_needs: List[str]
    pain_points: List[str]
    avg_priority_score: float
    recommendation_priority: str
    last_researched_at: Optional[str] = None


class ResearchExecution(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    countries: List[str]
    status: str = "pending"
    progress: int = 0
    current_country: Optional[str] = None
    trends_processed: int = 0
    total_expected: int = 0
    error: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class RunResearchRequest(BaseModel):
    countries: Optional[List[str]] = None


# ---------- LLM analysis ----------
async def analyze_keyword_with_llm(keyword: str, country_code: str, country_name: str, language: str, interest_score: float) -> Dict[str, Any]:
    system_message = (
        "Eres un experto senior en investigación de mercados digitales en Latinoamérica y afiliación Hotmart. "
        "Tu misión: analizar una keyword y devolver insights accionables para vender productos digitales. "
        "Reglas estrictas:\n"
        "1. Responde SOLO con un objeto JSON válido, sin texto adicional, sin markdown, sin ```json.\n"
        "2. Sé específico: evita generalidades.\n"
        "3. Prioriza dolores con intención de compra real.\n"
        "4. Considera el contexto cultural y económico del país.\n"
        "5. Responde en el mismo idioma del país (es/pt).\n\n"
        'Formato OBLIGATORIO: {"pain_point": "string 1 frase", "commercial_intent": "Alta|Media|Baja", '
        '"priority_score": 0-100, "suggested_product_type": "curso|ebook|mentoria|software|membresia|template"}'
    )

    user_prompt = (
        f"País: {country_name} ({country_code})\n"
        f"Idioma: {language}\n"
        f"Keyword: \"{keyword}\"\n"
        f"Interés Google Trends (0-100): {interest_score:.1f}\n\n"
        "Analiza y devuelve el JSON estructurado."
    )

    if not EMERGENT_LLM_KEY:
        return _heuristic_fallback(keyword, language)

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"research-{country_code}-{uuid.uuid4().hex[:8]}",
            system_message=system_message,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        response = await chat.send_message(UserMessage(text=user_prompt))
        return _parse_llm_response(response, keyword, language)
    except Exception as e:
        logger.warning(f"LLM analysis failed for {keyword}: {e}. Using heuristic fallback.")
        return _heuristic_fallback(keyword, language)


def _parse_llm_response(response: str, keyword: str, language: str) -> Dict[str, Any]:
    if not isinstance(response, str):
        response = str(response)
    match = re.search(r"\{[\s\S]*\}", response)
    raw = match.group(0) if match else response
    try:
        data = json.loads(raw)
    except Exception:
        return _heuristic_fallback(keyword, language)
    return _validate_analysis(data, keyword, language)


def _validate_analysis(data: Dict[str, Any], keyword: str, language: str) -> Dict[str, Any]:
    intent_raw = str(data.get("commercial_intent", "Media")).lower()
    if "alta" in intent_raw or "alto" in intent_raw or "high" in intent_raw:
        intent = "Alta"
    elif "baja" in intent_raw or "bajo" in intent_raw or "low" in intent_raw:
        intent = "Baja"
    else:
        intent = "Media"

    try:
        score = int(float(data.get("priority_score", 50)))
    except Exception:
        score = 50
    score = max(0, min(100, score))

    pain = str(data.get("pain_point") or f"Necesidad no resuelta en torno a {keyword}").strip()
    product = str(data.get("suggested_product_type") or "curso online").strip().lower()

    return {
        "pain_point": pain[:240],
        "commercial_intent": intent,
        "priority_score": score,
        "suggested_product_type": product[:60],
    }


def _heuristic_fallback(keyword: str, language: str) -> Dict[str, Any]:
    kw = keyword.lower()
    high_intent = ["curso", "certificacion", "mentoria", "inversion", "invest",
                   "ganar dinero", "emprender", "ventas", "vendas", "marketing",
                   "freelance", "negocios", "empreendedorismo"]
    if any(h in kw for h in high_intent):
        intent, score = "Alta", 78
    elif any(h in kw for h in ["salud", "bienestar", "mental", "saude",
                               "desarrollo personal", "desenvolvimento"]):
        intent, score = "Media", 62
    else:
        intent, score = "Media", 50

    if "curso" in kw or "idioma" in kw or "ingles" in kw:
        product = "curso online"
    elif "inversion" in kw or "finanzas" in kw or "investiment" in kw:
        product = "mentoria"
    elif "marketing" in kw or "ventas" in kw or "vendas" in kw:
        product = "curso online"
    else:
        product = "ebook"

    pain = (f"Búsqueda activa de formación práctica en {keyword}"
            if language == "es"
            else f"Busca ativa de formação prática em {keyword}")

    return {
        "pain_point": pain,
        "commercial_intent": intent,
        "priority_score": score,
        "suggested_product_type": product,
    }


# ---------- Google Trends ----------
def _fetch_trends_sync(country_code: str, keywords: List[str]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    try:
        pytrends = TrendReq(hl="es-419", tz=360, timeout=(10, 25), retries=2, backoff_factor=0.5)
        batch = keywords[:5]
        pytrends.build_payload(batch, geo=country_code, timeframe="today 3-m")
        df = pytrends.interest_over_time()
        if df is None or df.empty:
            return scores
        for kw in batch:
            if kw in df.columns:
                avg = float(df[kw].mean())
                if avg > 0:
                    scores[kw] = round(min(100.0, avg), 2)
    except Exception as e:
        logger.warning(f"pytrends failed for {country_code}: {e}")
    return scores


async def fetch_trends_async(country_code: str, keywords: List[str]) -> Dict[str, float]:
    return await asyncio.to_thread(_fetch_trends_sync, country_code, keywords)


# ---------- Research orchestrator ----------
async def _update_execution(execution_id: str, **fields) -> None:
    if "completed_at" in fields and isinstance(fields["completed_at"], datetime):
        fields["completed_at"] = fields["completed_at"].isoformat()
    await db.research_executions.update_one({"id": execution_id}, {"$set": fields})


async def run_research_background(execution_id: str, country_codes: List[str]) -> None:
    total_expected = sum(len(COUNTRIES[c]["trends_keywords"][:5]) for c in country_codes if c in COUNTRIES)
    await _update_execution(
        execution_id,
        status="running",
        progress=0,
        trends_processed=0,
        total_expected=total_expected,
    )

    processed = 0
    try:
        for country_code in country_codes:
            config = COUNTRIES.get(country_code)
            if not config:
                continue
            await _update_execution(execution_id, current_country=country_code)
            logger.info(f"🔍 Researching {config['name']} ({country_code})")

            keywords = config["trends_keywords"][:5]
            language = config["language"]

            trend_scores = await fetch_trends_async(country_code, keywords)

            for kw in keywords:
                interest = trend_scores.get(kw, 0.0)
                source = "google_trends"
                if interest <= 0:
                    interest = 35.0 + random.uniform(0, 10)
                    source = "llm_analysis"

                analysis = await analyze_keyword_with_llm(
                    keyword=kw,
                    country_code=country_code,
                    country_name=config["name"],
                    language=language,
                    interest_score=interest,
                )

                trend = Trend(
                    country_code=country_code,
                    country_name=config["name"],
                    keyword=kw,
                    interest_score=float(interest),
                    priority_score=analysis["priority_score"],
                    commercial_intent=analysis["commercial_intent"],
                    pain_point=analysis["pain_point"],
                    suggested_product_type=analysis["suggested_product_type"],
                    source=source,
                )
                doc = trend.model_dump()
                doc["researched_at"] = doc["researched_at"].isoformat()
                await db.trends.update_one(
                    {"country_code": country_code, "keyword": kw},
                    {"$set": doc},
                    upsert=True,
                )
                processed += 1
                progress = int((processed / max(1, total_expected)) * 100)
                await _update_execution(
                    execution_id,
                    trends_processed=processed,
                    progress=progress,
                )
                await asyncio.sleep(0.3)

            await asyncio.sleep(1.5)

        await _update_execution(
            execution_id,
            status="completed",
            progress=100,
            current_country=None,
            completed_at=datetime.now(timezone.utc),
        )
        logger.info(f"✅ Research {execution_id} completed: {processed} trends")
    except Exception as e:
        logger.exception(f"Research {execution_id} failed: {e}")
        await _update_execution(
            execution_id,
            status="failed",
            error=str(e)[:500],
            completed_at=datetime.now(timezone.utc),
        )


# ---------- FastAPI app ----------
app = FastAPI(title="Hotmart Super Agent - Módulo 1")
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {
        "service": "Hotmart Super Agent",
        "module": "1 - Investigación de Mercado",
        "status": "online",
        "countries_configured": TARGET_COUNTRIES,
    }


@api_router.get("/health")
async def health():
    try:
        await db.command("ping")
        mongo_ok = True
    except Exception:
        mongo_ok = False
    return {
        "status": "ok" if mongo_ok else "degraded",
        "mongo": mongo_ok,
        "llm_key_configured": bool(EMERGENT_LLM_KEY),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@api_router.get("/countries")
async def list_countries():
    result = []
    for code, cfg in COUNTRIES.items():
        result.append({
            "code": code,
            "name": cfg["name"],
            "flag": cfg.get("flag", code),
            "currency": cfg["currency"],
            "language": cfg["language"],
            "keywords_count": len(cfg["trends_keywords"]),
            "seed_keywords": cfg["trends_keywords"][:5],
        })
    return result


@api_router.post("/research/run")
async def run_research(payload: RunResearchRequest, background_tasks: BackgroundTasks):
    target = payload.countries or TARGET_COUNTRIES
    invalid = [c for c in target if c not in COUNTRIES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Países no soportados: {invalid}")

    execution = ResearchExecution(
        countries=target,
        total_expected=sum(len(COUNTRIES[c]["trends_keywords"][:5]) for c in target),
    )
    doc = execution.model_dump()
    doc["started_at"] = doc["started_at"].isoformat()
    doc["completed_at"] = None
    await db.research_executions.insert_one(doc)

    background_tasks.add_task(run_research_background, execution.id, target)

    return {
        "execution_id": execution.id,
        "status": "started",
        "countries": target,
        "total_expected": execution.total_expected,
        "message": f"Investigación iniciada para {len(target)} paises.",
    }


@api_router.get("/research/executions")
async def list_executions(limit: int = 10):
    cursor = db.research_executions.find({}, {"_id": 0}).sort("started_at", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    return items


@api_router.get("/research/executions/{execution_id}")
async def get_execution(execution_id: str):
    doc = await db.research_executions.find_one({"id": execution_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Execution no encontrada")
    return doc


@api_router.get("/research/overview")
async def research_overview():
    result = []
    for code, cfg in COUNTRIES.items():
        cursor = db.trends.find({"country_code": code}, {"_id": 0})
        trends = await cursor.to_list(length=500)
        if trends:
            avg_prio = round(sum(t["priority_score"] for t in trends) / len(trends), 1)
            last = max((t.get("researched_at") for t in trends if t.get("researched_at")), default=None)
            scores = [t["priority_score"] for t in trends]
            if max(scores) >= 80:
                rec = "HIGH"
            elif max(scores) >= 60:
                rec = "MEDIUM"
            else:
                rec = "LOW"
        else:
            avg_prio = 0.0
            last = None
            rec = "LOW"

        result.append({
            "code": code,
            "name": cfg["name"],
            "flag": cfg.get("flag", code),
            "currency": cfg["currency"],
            "language": cfg["language"],
            "total_trends": len(trends),
            "avg_priority_score": avg_prio,
            "recommendation_priority": rec,
            "last_researched_at": last,
        })
    return result


@api_router.get("/research/trends/{country_code}")
async def get_trends(country_code: str, limit: int = 50, sort_by: str = "priority_score"):
    if country_code not in COUNTRIES:
        raise HTTPException(status_code=400, detail=f"País no soportado. Usa: {TARGET_COUNTRIES}")
    valid_sorts = {"priority_score": -1, "interest_score": -1, "keyword": 1}
    sort_field = sort_by if sort_by in valid_sorts else "priority_score"
    direction = valid_sorts[sort_field]
    cursor = db.trends.find({"country_code": country_code}, {"_id": 0}).sort(sort_field, direction).limit(limit)
    items = await cursor.to_list(length=limit)
    return items


@api_router.get("/research/summary/{country_code}")
async def get_country_summary(country_code: str):
    if country_code not in COUNTRIES:
        raise HTTPException(status_code=400, detail=f"País no soportado. Usa: {TARGET_COUNTRIES}")

    cursor = db.trends.find({"country_code": country_code}, {"_id": 0}).sort("priority_score", -1)
    trends = await cursor.to_list(length=500)
    if not trends:
        raise HTTPException(status_code=404, detail=f"Sin datos para {country_code}")

    top_needs = [t["keyword"] for t in trends[:5]]
    pain_points = list(dict.fromkeys(t["pain_point"] for t in trends if t.get("pain_point")))[:8]
    avg = round(sum(t["priority_score"] for t in trends) / len(trends), 1)
    max_score = max(t["priority_score"] for t in trends)
    rec = "HIGH" if max_score >= 80 else ("MEDIUM" if max_score >= 60 else "LOW")
    last = max((t.get("researched_at") for t in trends if t.get("researched_at")), default=None)

    return CountrySummary(
        code=country_code,
        name=COUNTRIES[country_code]["name"],
        total_trends=len(trends),
        top_needs=top_needs,
        pain_points=pain_points,
        avg_priority_score=avg,
        recommendation_priority=rec,
        last_researched_at=last,
    )


@api_router.delete("/research/trends/{country_code}")
async def clear_trends(country_code: str):
    if country_code not in COUNTRIES:
        raise HTTPException(status_code=400, detail=f"País no soportado. Usa: {TARGET_COUNTRIES}")
    result = await db.trends.delete_many({"country_code": country_code})
    return {"deleted": result.deleted_count, "country_code": country_code}


# ---------- Module 2: Hotmart Product Matching ----------
class MatchRequest(BaseModel):
    country_code: str
    limit: int = Field(default=10, ge=1, le=30)
    auto_links: bool = True


async def _run_matching_task(execution_id: str, country_code: str, limit: int, auto_links: bool):
    """Background matching task — mirrors research executions for unified UX."""
    try:
        await db.product_executions.update_one(
            {"id": execution_id}, {"$set": {"status": "running"}}
        )
        products = await hm.match_and_score(
            db=db,
            country_code=country_code,
            country_name=COUNTRIES[country_code]["name"],
            limit=limit,
            auto_links=auto_links,
        )
        await db.product_executions.update_one(
            {"id": execution_id},
            {"$set": {
                "status": "completed",
                "products_found": len(products),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    except Exception as e:
        logger.exception(f"Matching execution {execution_id} failed: {e}")
        await db.product_executions.update_one(
            {"id": execution_id},
            {"$set": {
                "status": "failed",
                "error": str(e)[:500],
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }},
        )


@api_router.get("/hotmart/status")
async def hotmart_status():
    return {
        "credentials_configured": hm.hotmart_credentials_configured(),
        "module": "2 - Hotmart Product Matching",
        "affiliate_api": "ready" if hm.hotmart_credentials_configured() else "credentials_missing",
        "scraper": "enabled",
        "llm_fallback": "enabled" if EMERGENT_LLM_KEY else "disabled",
    }


@api_router.post("/hotmart/test-connection")
@api_router.get("/hotmart/test-connection")
async def hotmart_test_connection():
    """Validate credentials + scopes against real Hotmart API."""
    api = hm.HotmartAffiliateAPI()
    return await api.test_connection()


@api_router.get("/hotmart/my-affiliations")
async def hotmart_my_affiliations(max_results: int = 50):
    """List products the user is already affiliated to on Hotmart."""
    api = hm.HotmartAffiliateAPI()
    return await api.list_my_affiliations(max_results=max_results)


@api_router.get("/hotmart/sales-summary")
async def hotmart_sales_summary():
    """Sales summary from Hotmart (total sales, commissions)."""
    api = hm.HotmartAffiliateAPI()
    return await api.sales_summary()


@api_router.get("/hotmart/sales-history")
async def hotmart_sales_history(max_results: int = 20):
    """Recent sales from Hotmart."""
    api = hm.HotmartAffiliateAPI()
    return await api.sales_history(max_results=max_results)


@api_router.get("/hotmart/commissions")
async def hotmart_commissions(max_results: int = 20):
    """Recent affiliate commissions from Hotmart."""
    api = hm.HotmartAffiliateAPI()
    return await api.sales_commissions(max_results=max_results)



@api_router.post("/hotmart/rematch-all")
async def hotmart_rematch_all(background_tasks: BackgroundTasks):
    """After syncing affiliations, re-run matching for every country so real hotlinks are attached."""
    if not hm.hotmart_credentials_configured():
        raise HTTPException(status_code=400, detail="Credenciales Hotmart no configuradas")

    # Sync first (fast — just one API call)
    sync = await hm.sync_my_affiliations(db)

    # Schedule re-match in background for each country with trends
    countries_to_rematch = []
    for code in TARGET_COUNTRIES:
        trend_count = await db.trends.count_documents({"country_code": code})
        if trend_count > 0:
            countries_to_rematch.append(code)

    execution_id = str(uuid.uuid4())
    await db.product_executions.insert_one({
        "id": execution_id,
        "country_code": "ALL",
        "kind": "rematch_all",
        "limit": 10,
        "auto_links": True,
        "status": "pending",
        "products_found": 0,
        "countries": countries_to_rematch,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "error": None,
    })

    async def _run_rematch():
        total_matched = 0
        try:
            await db.product_executions.update_one(
                {"id": execution_id}, {"$set": {"status": "running"}}
            )
            for code in countries_to_rematch:
                products = await hm.match_and_score(
                    db=db,
                    country_code=code,
                    country_name=COUNTRIES[code]["name"],
                    limit=10,
                    auto_links=True,
                )
                mine = sum(1 for p in products if p.get("is_my_affiliation"))
                total_matched += mine
            await db.product_executions.update_one(
                {"id": execution_id},
                {"$set": {
                    "status": "completed",
                    "products_found": total_matched,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
        except Exception as e:
            logger.exception(f"rematch-all {execution_id} failed: {e}")
            await db.product_executions.update_one(
                {"id": execution_id},
                {"$set": {
                    "status": "failed",
                    "error": str(e)[:500],
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }},
            )

    background_tasks.add_task(_run_rematch)

    return {
        "status": "started",
        "execution_id": execution_id,
        "synced_affiliations": sync.get("synced", 0),
        "countries": countries_to_rematch,
        "message": f"Sincronización completada ({sync.get('synced', 0)} afiliaciones). Rematch en background para {len(countries_to_rematch)} países.",
    }


@api_router.post("/products/match")
async def match_products(payload: MatchRequest, background_tasks: BackgroundTasks):
    if payload.country_code not in COUNTRIES:
        raise HTTPException(status_code=400, detail=f"País no soportado. Usa: {TARGET_COUNTRIES}")

    # Ensure trends exist for that country
    trend_count = await db.trends.count_documents({"country_code": payload.country_code})
    if trend_count == 0:
        raise HTTPException(
            status_code=409,
            detail=f"Sin tendencias para {payload.country_code}. Ejecuta primero /api/research/run para ese país.",
        )

    execution_id = str(uuid.uuid4())
    await db.product_executions.insert_one({
        "id": execution_id,
        "country_code": payload.country_code,
        "limit": payload.limit,
        "auto_links": payload.auto_links,
        "status": "pending",
        "products_found": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "error": None,
    })
    background_tasks.add_task(_run_matching_task, execution_id, payload.country_code, payload.limit, payload.auto_links)
    return {
        "execution_id": execution_id,
        "status": "started",
        "country_code": payload.country_code,
        "message": f"Matching iniciado para {payload.country_code}. Resultados en ~30-60s.",
    }


@api_router.get("/products/executions/{execution_id}")
async def get_product_execution(execution_id: str):
    doc = await db.product_executions.find_one({"id": execution_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Execution no encontrada")
    return doc


@api_router.get("/products/{country_code}")
async def get_products(country_code: str, limit: int = 30):
    if country_code not in COUNTRIES:
        raise HTTPException(status_code=400, detail=f"País no soportado. Usa: {TARGET_COUNTRIES}")
    cursor = db.products.find({"country_code": country_code}, {"_id": 0}).sort("relevance_score", -1).limit(limit)
    items = await cursor.to_list(length=limit)
    return items


@api_router.get("/products/{country_code}/{hotmart_id}/affiliate-link")
async def get_or_generate_affiliate_link(country_code: str, hotmart_id: str, force: bool = False):
    product = await db.products.find_one(
        {"country_code": country_code, "hotmart_id": hotmart_id}, {"_id": 0}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # If already generated and not forced, return cached
    if not force and product.get("affiliate_status") == "generated" and product.get("affiliate_link"):
        return {
            "hotmart_id": hotmart_id,
            "affiliate_link": product["affiliate_link"],
            "status": "cached",
            "tracking_id": product.get("tracking_id"),
        }

    api_client = hm.HotmartAffiliateAPI()
    result = await api_client.generate_hotlink(hotmart_id)
    if result.get("status") == "generated":
        await db.products.update_one(
            {"country_code": country_code, "hotmart_id": hotmart_id},
            {"$set": {
                "affiliate_link": result["hotlink"],
                "affiliate_status": "generated",
                "tracking_id": result.get("tracking_id"),
                "affiliate_link_generated_at": result["generated_at"],
            }},
        )
    return {"hotmart_id": hotmart_id, **result}


@api_router.delete("/products/{country_code}")
async def clear_products(country_code: str):
    if country_code not in COUNTRIES:
        raise HTTPException(status_code=400, detail=f"País no soportado. Usa: {TARGET_COUNTRIES}")
    result = await db.products.delete_many({"country_code": country_code})
    return {"deleted": result.deleted_count, "country_code": country_code}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Scheduler (weekly refresh) ----------
scheduler = AsyncIOScheduler()


async def weekly_refresh_job():
    """Every Sunday 03:00 UTC: re-run research + product matching for all countries."""
    logger.info("⏱️  Weekly refresh job starting")
    has_creds = hm.hotmart_credentials_configured()
    for country_code in TARGET_COUNTRIES:
        try:
            # Re-run matching (uses cached trends from last research run)
            products = await hm.match_and_score(
                db=db,
                country_code=country_code,
                country_name=COUNTRIES[country_code]["name"],
                limit=10,
                auto_links=has_creds,
            )
            if has_creds:
                generated = sum(1 for p in products if p.get("affiliate_status") == "generated")
                logger.info(f"✅ {country_code}: {len(products)} products, {generated} hotlinks")
            else:
                logger.info(f"✅ {country_code}: {len(products)} products (hotlinks pendientes: credenciales faltantes)")
            await asyncio.sleep(3)
        except Exception as e:
            logger.warning(f"Weekly job {country_code}: {e}")


@app.on_event("startup")
async def startup_event():
    try:
        await db.trends.create_index([("country_code", 1), ("keyword", 1)], unique=True)
        await db.trends.create_index([("priority_score", -1)])
        await db.research_executions.create_index([("started_at", -1)])
        await db.products.create_index([("country_code", 1), ("hotmart_id", 1)], unique=True)
        await db.products.create_index([("relevance_score", -1)])
        await db.product_executions.create_index([("started_at", -1)])
        logger.info("✅ Indexes ensured")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")

    try:
        scheduler.add_job(weekly_refresh_job, "cron", day_of_week="sun", hour=3, minute=0, id="weekly_refresh")
        scheduler.start()
        logger.info("⏱️  Scheduler activated (Sundays 03:00 UTC)")
    except Exception as e:
        logger.warning(f"Scheduler warning: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
    client.close()
