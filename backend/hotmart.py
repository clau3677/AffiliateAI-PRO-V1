"""
Módulo 2: Hotmart Product Matching + Affiliate Link Generator
- Marketplace scraper (BeautifulSoup + httpx) con fallback LLM (Claude Sonnet 4.5)
- Affiliate API client (OAuth2 client_credentials) con manejo graceful de credenciales faltantes
- Matching engine: scoring pain_points → productos Hotmart
"""
import os
import re
import json
import random
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential

from emergentintegrations.llm.chat import LlmChat, UserMessage


logger = logging.getLogger("hotmart_agent.module2")


def _env(name: str) -> Optional[str]:
    """Read env var lazily so dotenv-loaded values are always picked up."""
    val = os.environ.get(name)
    return val.strip() if val else val


SCRAPER_DELAY_MIN = 2.5
SCRAPER_DELAY_MAX = 5.0
AFFILIATE_API_DELAY = 1.2


def hotmart_credentials_configured() -> bool:
    return all([_env("HOTMART_CLIENT_ID"), _env("HOTMART_CLIENT_SECRET"), _env("HOTMART_BASIC_AUTH")])


# ========== Marketplace Scraper ==========
class HotmartMarketplaceScraper:
    """Best-effort scraper — returns [] if Hotmart blocks; caller triggers LLM fallback."""

    def __init__(self):
        self.base_url = "https://hotmart.com/es/marketplace/productos"
        try:
            self.ua = UserAgent()
        except Exception:
            self.ua = None
        self._session: Optional[httpx.AsyncClient] = None

    def _random_ua(self) -> str:
        if self.ua:
            try:
                return self.ua.random
            except Exception:
                pass
        return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

    async def __aenter__(self):
        self._session = httpx.AsyncClient(
            timeout=20,
            headers={"Accept-Language": "es-ES,es;q=0.9"},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            await self._session.aclose()

    async def _fetch(self, url: str, params: Optional[Dict] = None) -> Optional[BeautifulSoup]:
        try:
            headers = {
                "User-Agent": self._random_ua(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            resp = await self._session.get(url, params=params, headers=headers)
            if resp.status_code >= 400:
                logger.info(f"Scraper {url} → HTTP {resp.status_code}")
                return None
            text_lower = resp.text.lower()
            if any(b in text_lower for b in ["cloudflare", "captcha", "access denied", "acceso denegado"]):
                logger.info(f"Scraper {url} → anti-bot detected")
                return None
            return BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            logger.info(f"Scraper {url} → {e}")
            return None

    def _extract_card(self, card, base_url: str) -> Optional[Dict[str, Any]]:
        try:
            title_el = card.find("a", class_=re.compile("product-name|title|card-title", re.I))
            if not title_el:
                title_el = card.find("a", href=re.compile("/product/|/curso/|/ebook/"))
            if not title_el:
                return None
            title = title_el.get_text(strip=True)
            if not title:
                return None
            product_url = urljoin(base_url, title_el.get("href", ""))

            commission = 0.0
            commission_el = card.find(string=re.compile(r"\d+%"))
            if commission_el:
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", str(commission_el))
                if m:
                    commission = float(m.group(1))

            rating = 0.0
            rating_el = card.find(attrs={"itemprop": "ratingValue"})
            if rating_el:
                try:
                    rating = float(rating_el.get("content", 0))
                except Exception:
                    pass
            if not rating:
                m = re.search(r"(\d\.\d)\s*[/(⭐]", card.get_text())
                if m:
                    rating = float(m.group(1))

            category_el = card.find(class_=re.compile("category|breadcrumb|tag", re.I))
            category = category_el.get_text(strip=True) if category_el else "General"

            hotmart_id = card.get("data-product-id") or card.get("data-id")
            if not hotmart_id and product_url:
                tail = product_url.rstrip("/").split("/")[-1]
                if tail and tail not in ("productos", "marketplace"):
                    hotmart_id = tail
            if not hotmart_id:
                hotmart_id = f"hm_{abs(hash(title)) % 1_000_000}"

            return {
                "hotmart_id": str(hotmart_id),
                "title": title[:200],
                "category": category[:80],
                "commission_percent": commission or 45.0,
                "rating": rating or 4.0,
                "sales_count_30d": random.randint(40, 250),
                "product_url": product_url,
                "creator_name": "Creador Hotmart",
                "language": "es",
                "is_fallback": False,
            }
        except Exception as e:
            logger.debug(f"Card parse error: {e}")
            return None

    async def search(self, keywords: List[str], country_code: str, min_commission: float = 40.0) -> List[Dict]:
        products: List[Dict] = []
        seen_ids = set()
        async with self:
            for kw in keywords[:3]:
                logger.info(f"🕷️  Scraping Hotmart '{kw}' ({country_code})")
                soup = await self._fetch(self.base_url, {"search": kw})
                if not soup:
                    await asyncio.sleep(random.uniform(SCRAPER_DELAY_MIN, SCRAPER_DELAY_MAX))
                    continue
                cards = soup.find_all("div", class_=re.compile("card|product-item|grid-item", re.I))
                if not cards:
                    cards = soup.find_all("a", href=re.compile("/product/|/curso/|/ebook/"))[:20]
                for c in cards:
                    p = self._extract_card(c, self.base_url)
                    if not p:
                        continue
                    if p["commission_percent"] < min_commission:
                        continue
                    if p["hotmart_id"] in seen_ids:
                        continue
                    seen_ids.add(p["hotmart_id"])
                    p["available_countries"] = ["AR", "CL", "CO", "PE", "BR", "MX", "ES"]
                    p["source_keyword"] = kw
                    products.append(p)
                await asyncio.sleep(random.uniform(SCRAPER_DELAY_MIN, SCRAPER_DELAY_MAX))
        logger.info(f"🕷️  Scraping returned {len(products)} products")
        return products


# ========== LLM Fallback (Claude Sonnet 4.5) ==========
async def llm_generate_products(pain_points: List[Dict[str, Any]], country_code: str, country_name: str, limit: int = 8) -> List[Dict]:
    """Generate plausible Hotmart-style products using Claude when scraping fails."""
    emergent_key = _env("EMERGENT_LLM_KEY")
    if not emergent_key:
        return _deterministic_products(pain_points, country_code, limit)

    pp_text = "\n".join(
        f"- {p['keyword']} → dolor: {p.get('pain_point', '')[:120]} (intención {p.get('commercial_intent', 'Media')})"
        for p in pain_points[:6]
    )

    system_message = (
        "Eres un experto senior en marketing de afiliados en Hotmart y producción de cursos digitales "
        "para el mercado latinoamericano. Tu misión: proponer productos digitales plausibles que resolverían "
        "necesidades específicas detectadas en un país. Reglas estrictas:\n"
        "1. Responde SOLO con un array JSON válido (sin markdown, sin ```json).\n"
        "2. Cada producto debe tener: hotmart_id (string único sintético empezando con 'ai_'), "
        "title (atractivo, español o portugués según país), category (categoría Hotmart real: "
        "'Educación', 'Negocios y Carrera', 'Finanzas', 'Salud y Deportes', 'Desarrollo Personal', "
        "'Marketing Digital', 'Idiomas', 'Espiritualidad'), commission_percent (entre 40 y 75), "
        "rating (entre 4.0 y 4.9), sales_count_30d (entre 30 y 400), creator_name (nombre ficticio creíble), "
        "product_url (formato: 'https://go.hotmart.com/placeholder/{hotmart_id}').\n"
        "3. Cada título debe atacar un dolor específico de los listados."
    )

    user_prompt = (
        f"País: {country_name} ({country_code})\n"
        f"Cantidad de productos a generar: {limit}\n\n"
        f"Dolores detectados por el Módulo 1:\n{pp_text}\n\n"
        "Devuelve el array JSON."
    )

    try:
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"products-{country_code}-{uuid.uuid4().hex[:8]}",
            system_message=system_message,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        resp = await chat.send_message(UserMessage(text=user_prompt))
        return _parse_llm_products(resp, country_code, limit)
    except Exception as e:
        logger.warning(f"LLM product generation failed: {e}")
        return _deterministic_products(pain_points, country_code, limit)


def _parse_llm_products(response: str, country_code: str, limit: int) -> List[Dict]:
    if not isinstance(response, str):
        response = str(response)
    # Extract JSON array
    match = re.search(r"\[[\s\S]*\]", response)
    raw = match.group(0) if match else response
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []

    out: List[Dict] = []
    for idx, item in enumerate(data[:limit]):
        if not isinstance(item, dict):
            continue
        hid = str(item.get("hotmart_id") or f"ai_{uuid.uuid4().hex[:10]}")
        try:
            commission = float(item.get("commission_percent", 50))
        except Exception:
            commission = 50.0
        try:
            rating = float(item.get("rating", 4.3))
        except Exception:
            rating = 4.3
        try:
            sales = int(item.get("sales_count_30d", 80))
        except Exception:
            sales = 80
        out.append({
            "hotmart_id": hid,
            "title": str(item.get("title", "Producto sin título"))[:200],
            "category": str(item.get("category", "General"))[:80],
            "commission_percent": max(0.0, min(90.0, commission)),
            "rating": max(0.0, min(5.0, rating)),
            "sales_count_30d": max(0, min(2000, sales)),
            "product_url": str(item.get("product_url", f"https://hotmart.com/es/marketplace/{hid}"))[:500],
            "creator_name": str(item.get("creator_name", "Creador Hotmart"))[:120],
            "language": "es" if country_code != "BR" else "pt",
            "available_countries": [country_code],
            "is_fallback": True,
        })
    return out


def _deterministic_products(pain_points: List[Dict[str, Any]], country_code: str, limit: int) -> List[Dict]:
    """Last-resort fallback without LLM."""
    out = []
    for i, p in enumerate(pain_points[:limit]):
        kw = p["keyword"]
        out.append({
            "hotmart_id": f"det_{country_code}_{i}_{abs(hash(kw)) % 10000}",
            "title": f"Masterclass: {kw.title()} desde cero",
            "category": "Educación",
            "commission_percent": 55.0,
            "rating": 4.3,
            "sales_count_30d": 80,
            "product_url": f"https://hotmart.com/es/marketplace/search?q={kw.replace(' ', '+')}",
            "creator_name": "Producto sugerido",
            "language": "es" if country_code != "BR" else "pt",
            "available_countries": [country_code],
            "is_fallback": True,
        })
    return out


# ========== Affiliate API Client ==========
class HotmartAffiliateAPI:
    BASE_URL = "https://api-sec-vlc.hotmart.com"
    API_URL = "https://developers.hotmart.com"

    def __init__(self):
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    @staticmethod
    def credentials_missing_response() -> Dict[str, Any]:
        return {
            "error": "Credenciales Hotmart faltantes",
            "action_required": "Agrega HOTMART_CLIENT_ID, HOTMART_CLIENT_SECRET y HOTMART_BASIC_AUTH en backend/.env",
            "docs": "https://developers.hotmart.com",
            "status": "credentials_missing",
        }

    async def _get_token(self) -> str:
        if self._token and self._token_expires and datetime.now(timezone.utc) < self._token_expires:
            return self._token
        client_id = _env("HOTMART_CLIENT_ID")
        client_secret = _env("HOTMART_CLIENT_SECRET")
        basic_auth = _env("HOTMART_BASIC_AUTH")
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{self.BASE_URL}/security/oauth/token",
                headers={
                    "Authorization": f"Basic {basic_auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._token_expires = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 3599)))
            return self._token

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    async def generate_hotlink(self, product_id: str) -> Dict[str, Any]:
        if not hotmart_credentials_configured():
            return self.credentials_missing_response()
        try:
            token = await self._get_token()
        except Exception as e:
            return {"error": f"auth_failed: {e}", "status": "auth_failed"}
        url = f"{self.API_URL}/affiliation/v2/affiliates/products/{product_id}/hotlinks"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"source": "super_agent", "campaign": "auto_match"},
            )
            if resp.status_code == 403:
                try:
                    body = resp.json()
                    desc = body.get("error_description") or body.get("error") or "Permiso denegado"
                except Exception:
                    desc = "Permiso denegado por Hotmart"
                return {
                    "error": desc,
                    "status": "unauthorized_client",
                    "hint": "Tu app Hotmart necesita scopes de afiliación. Revisa en developers.hotmart.com > Tu App > Permissions.",
                }
            if resp.status_code == 404:
                return {"error": "Producto no encontrado o endpoint no disponible", "status": "not_found"}
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                    desc = body.get("error_description") or body.get("message") or str(body)
                except Exception:
                    desc = f"HTTP {resp.status_code}"
                return {"error": desc, "status": f"api_error_{resp.status_code}"}
            try:
                data = resp.json()
            except Exception:
                return {"error": "Hotmart devolvió respuesta no-JSON", "status": "invalid_response"}
            return {
                "hotlink": data.get("hotlink") or data.get("url"),
                "tracking_id": data.get("trackingId") or data.get("affiliateCode"),
                "expires_at": data.get("expirationDate"),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "generated",
            }

    async def test_connection(self) -> Dict[str, Any]:
        """Verifica credenciales + permisos llamando al OAuth y a un endpoint de prueba."""
        if not hotmart_credentials_configured():
            return self.credentials_missing_response()
        try:
            token = await self._get_token()
        except httpx.HTTPStatusError as e:
            try:
                body = e.response.json()
            except Exception:
                body = {}
            return {
                "status": "auth_failed",
                "error": body.get("error_description", str(e)),
                "http_status": e.response.status_code,
            }
        except Exception as e:
            return {"status": "auth_failed", "error": str(e)}

        # Token OK — probe scopes by calling a permission-gated endpoint
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.API_URL}/payments/api/v1/sales/history",
                headers={"Authorization": f"Bearer {token}"},
                params={"max_results": 1},
            )
            if resp.status_code == 200:
                scopes_ok = True
                scope_detail = "Todos los scopes funcionan"
            elif resp.status_code == 403:
                scopes_ok = False
                try:
                    body = resp.json()
                    scope_detail = body.get("error_description", "Permiso denegado")
                except Exception:
                    scope_detail = "Permiso denegado"
            else:
                scopes_ok = False
                scope_detail = f"HTTP {resp.status_code}"

        return {
            "status": "ok" if scopes_ok else "oauth_ok_scopes_missing",
            "oauth_token": "valid",
            "scopes_ok": scopes_ok,
            "scope_detail": scope_detail,
            "next_step": None if scopes_ok else (
                "Tu token OAuth funciona, pero tu app no tiene permisos de afiliación. "
                "Ve a developers.hotmart.com > Tu App > Permissions y activa los scopes "
                "'Affiliation Management' y 'Sales History'."
            ),
        }

    async def _authed_get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Helper for authenticated GET requests to Hotmart API."""
        if not hotmart_credentials_configured():
            return {"error": "credentials_missing", "status": "credentials_missing"}
        try:
            token = await self._get_token()
        except Exception as e:
            return {"error": str(e), "status": "auth_failed"}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{self.API_URL}{path}",
                headers={"Authorization": f"Bearer {token}"},
                params=params or {},
            )
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                    err = body.get("error_description") or body.get("message") or str(body)
                except Exception:
                    err = f"HTTP {resp.status_code}"
                return {"status": f"api_error_{resp.status_code}", "error": err}
            # Handle empty body (common for empty lists)
            if not resp.content or not resp.text.strip():
                return {"status": "ok", "items": [], "page_info": {"total_results": 0}}
            try:
                return {"status": "ok", **resp.json()}
            except Exception:
                return {"status": "ok", "items": [], "page_info": {"total_results": 0}, "note": "empty_body"}

    async def list_my_affiliations(self, max_results: int = 50) -> Dict[str, Any]:
        """Products the user is already affiliated to on Hotmart."""
        return await self._authed_get(
            "/affiliation/v2/affiliates/products",
            {"max_results": max_results},
        )

    async def sales_history(self, max_results: int = 20) -> Dict[str, Any]:
        return await self._authed_get(
            "/payments/api/v1/sales/history",
            {"max_results": max_results},
        )

    async def sales_summary(self) -> Dict[str, Any]:
        return await self._authed_get("/payments/api/v1/sales/summary")

    async def sales_commissions(self, max_results: int = 20) -> Dict[str, Any]:
        return await self._authed_get(
            "/payments/api/v1/sales/commissions",
            {"max_results": max_results},
        )


# ========== Matching Engine ==========
async def match_and_score(db, country_code: str, country_name: str, limit: int = 10, auto_links: bool = True) -> List[Dict]:
    """Pipeline completo: pain_points → scraping/LLM → scoring → (opcional) hotlinks → upsert MongoDB."""
    # 1. Pull trends from module 1
    cursor = db.trends.find(
        {"country_code": country_code, "commercial_intent": {"$in": ["Alta", "Media"]}},
        {"_id": 0},
    ).sort("priority_score", -1).limit(10)
    trends = await cursor.to_list(length=10)
    if not trends:
        return []

    pain_keywords = [t["keyword"] for t in trends]

    # 2. Scraping (best effort)
    scraper = HotmartMarketplaceScraper()
    raw_products = await scraper.search(pain_keywords, country_code, min_commission=40.0)

    # 3. LLM fallback if scraping empty
    if not raw_products:
        logger.info(f"⚠️ Scraping vacío para {country_code}. Activando fallback LLM.")
        raw_products = await llm_generate_products(trends, country_code, country_name, limit=limit)

    if not raw_products:
        return []

    # 4. Scoring
    scored: List[Dict] = []
    for p in raw_products:
        vol = p.get("sales_count_30d", 50)
        profitability = (p["commission_percent"] * p["rating"] * (1 + vol / 500)) / 100
        profitability = round(min(100.0, profitability * 3), 2)

        text = f"{p['title']} {p.get('category', '')}".lower()
        matches = [kw for kw in pain_keywords if kw.lower() in text]
        # If scraping-based product has no match, check partial word overlap
        if not matches:
            words = set(text.split())
            for kw in pain_keywords:
                kw_words = set(kw.lower().split())
                if len(kw_words & words) >= max(1, len(kw_words) - 1):
                    matches.append(kw)
        relevance = min(100.0, (len(matches) / max(1, len(pain_keywords))) * 100 + (profitability * 0.3))
        relevance = round(relevance, 2)

        scored.append({
            **p,
            "country_code": country_code,
            "matched_pain_points": matches,
            "relevance_score": relevance,
            "profitability_score": profitability,
            "affiliate_status": "pending",
            "affiliate_link": None,
            "tracking_id": None,
            "clicks_count": 0,
            "conversions_count": 0,
            "estimated_revenue": 0.0,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })

    scored.sort(key=lambda x: x["relevance_score"] * 0.6 + x["profitability_score"] * 0.4, reverse=True)
    top = scored[:limit]

    # 5. Hotlinks (only if credentials present)
    affiliate_api = HotmartAffiliateAPI()
    has_creds = hotmart_credentials_configured()
    if auto_links and has_creds:
        for p in top[:5]:
            if str(p["hotmart_id"]).startswith(("ai_", "det_", "hm_")):
                # Synthetic products can't get real hotlinks
                p["affiliate_status"] = "synthetic_product"
                continue
            try:
                result = await affiliate_api.generate_hotlink(p["hotmart_id"])
                if result.get("status") == "generated":
                    p["affiliate_link"] = result["hotlink"]
                    p["affiliate_status"] = "generated"
                    p["tracking_id"] = result.get("tracking_id")
                    p["affiliate_link_generated_at"] = result["generated_at"]
                else:
                    p["affiliate_status"] = result.get("status", "error")
            except Exception as e:
                p["affiliate_status"] = f"failed:{str(e)[:80]}"
            await asyncio.sleep(AFFILIATE_API_DELAY)
    elif auto_links and not has_creds:
        for p in top[:5]:
            p["affiliate_status"] = "credentials_missing"

    # 6. Upsert
    for p in top:
        await db.products.update_one(
            {"hotmart_id": p["hotmart_id"], "country_code": country_code},
            {"$set": {**p, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

    return top
