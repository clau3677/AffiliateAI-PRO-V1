"""
Módulo 2: Hotmart Real Product Matching + Affiliate Link Generator.

Fuentes REALES de productos (cero mocks):
1. Sincronización de afiliaciones del usuario via Hotmart Affiliate API
   (GET /affiliation/v2/affiliates/products)
2. Scraping del marketplace público de Hotmart extrayendo __NEXT_DATA__
   (productos reales con productId, title, slug, rating, owner).

Si ambas fuentes no producen matches para los pain points del país,
`match_and_score` devuelve [] y el frontend muestra el estado vacío.
"""
import os
import re
import json
import random
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any

import httpx
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential


logger = logging.getLogger("hotmart_agent.module2")


def _env(name: str) -> Optional[str]:
    """Read env var lazily so dotenv-loaded values are always picked up."""
    val = os.environ.get(name)
    return val.strip() if val else val


SCRAPER_DELAY_MIN = 1.5
SCRAPER_DELAY_MAX = 3.5


def hotmart_credentials_configured() -> bool:
    return all([_env("HOTMART_CLIENT_ID"), _env("HOTMART_CLIENT_SECRET"), _env("HOTMART_BASIC_AUTH")])


# ========== Marketplace Scraper (real products from __NEXT_DATA__) ==========
class HotmartMarketplaceScraper:
    """Parses Hotmart's public marketplace HTML, extracting embedded Next.js JSON
    (`__NEXT_DATA__`) to return REAL products only — no LLM-generated fakes."""

    def __init__(self):
        try:
            self.ua = UserAgent()
        except Exception:
            self.ua = None

    def _random_ua(self) -> str:
        if self.ua:
            try:
                return self.ua.random
            except Exception:
                pass
        return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

    @staticmethod
    def _find_results_in_next_data(data: Any, depth: int = 0) -> Optional[List[Dict]]:
        """DFS looking for any `{'results': [{'productId':...}]}` block."""
        if depth > 10:
            return None
        if isinstance(data, dict):
            results = data.get("results")
            if isinstance(results, list) and results and isinstance(results[0], dict) and "productId" in results[0]:
                return results
            for v in data.values():
                found = HotmartMarketplaceScraper._find_results_in_next_data(v, depth + 1)
                if found:
                    return found
        elif isinstance(data, list):
            for it in data:
                found = HotmartMarketplaceScraper._find_results_in_next_data(it, depth + 1)
                if found:
                    return found
        return None

    @staticmethod
    def _normalize_category(raw: Any) -> str:
        if not raw:
            return "General"
        s = str(raw).replace("_", " ").strip().title()
        return s[:80]

    def _parse_product(self, raw: Dict, country_code: str, locale: str, keyword: str) -> Optional[Dict]:
        pid = str(raw.get("productId") or "").strip()
        if not pid:
            return None
        slug = str(raw.get("slug") or "").strip()
        product_url = (
            f"https://hotmart.com/{locale}/marketplace/productos/{slug}/{pid}"
            if slug
            else f"https://hotmart.com/{locale}/marketplace/productos?search={keyword.replace(' ', '+')}"
        )
        owner = raw.get("owner") if isinstance(raw.get("owner"), dict) else {}
        creator = (
            raw.get("ownerName")
            or owner.get("name")
            or raw.get("authorName")
            or "Creador Hotmart"
        )
        rating = raw.get("rating")
        try:
            rating = float(rating) if rating is not None else 0.0
        except Exception:
            rating = 0.0
        reviews = raw.get("totalReviews") or 0
        try:
            reviews = int(reviews)
        except Exception:
            reviews = 0
        language = str(raw.get("language") or raw.get("locale") or locale).lower()[:5]

        return {
            "hotmart_id": pid,
            "title": str(raw.get("title") or f"Producto {pid}")[:220],
            "category": self._normalize_category(raw.get("category")),
            # Commission % isn't public on the marketplace (only visible after affiliation);
            # we leave it at 0 so the UI can show "—" and updates to real value after sync.
            "commission_percent": 0.0,
            "rating": round(max(0.0, min(5.0, rating)), 2),
            "sales_count_30d": reviews,  # reviews as a proxy for popularity
            "product_url": product_url,
            "creator_name": str(creator)[:120],
            "language": language,
            "available_countries": [country_code, "AR", "CL", "CO", "PE", "BR", "MX", "ES"],
            "is_fallback": False,
            "source_keyword": keyword,
        }

    async def _search_one(self, client: httpx.AsyncClient, keyword: str, country_code: str) -> List[Dict]:
        locale = "pt-br" if country_code == "BR" else "es"
        accept_lang = "pt-BR,pt;q=0.9,en;q=0.5" if locale == "pt-br" else "es-ES,es;q=0.9,en;q=0.5"
        url = f"https://hotmart.com/{locale}/marketplace/productos"
        try:
            resp = await client.get(
                url,
                params={"search": keyword},
                headers={
                    "User-Agent": self._random_ua(),
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                    "Accept-Language": accept_lang,
                },
            )
        except Exception as e:
            logger.info(f"🕷️  Scraper fetch error '{keyword}' ({country_code}): {e}")
            return []

        if resp.status_code != 200:
            logger.info(f"🕷️  Scraper '{keyword}' ({country_code}) → HTTP {resp.status_code}")
            return []

        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.S)
        if not match:
            logger.info(f"🕷️  '{keyword}' ({country_code}) — no __NEXT_DATA__ block")
            return []

        try:
            data = json.loads(match.group(1))
        except Exception as e:
            logger.info(f"🕷️  NEXT_DATA parse error: {e}")
            return []

        raw_results = self._find_results_in_next_data(data) or []
        products: List[Dict] = []
        for raw in raw_results:
            p = self._parse_product(raw, country_code, locale, keyword)
            if p:
                products.append(p)
        logger.info(f"🕷️  '{keyword}' ({country_code}) → {len(products)} real products")
        return products

    async def search(self, keywords: List[str], country_code: str, min_commission: float = 0.0) -> List[Dict]:
        """Search marketplace for each keyword, dedupe by productId, return real products."""
        seen: set = set()
        out: List[Dict] = []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for kw in keywords[:5]:
                products = await self._search_one(client, kw, country_code)
                for p in products:
                    if p["hotmart_id"] in seen:
                        continue
                    seen.add(p["hotmart_id"])
                    out.append(p)
                await asyncio.sleep(random.uniform(SCRAPER_DELAY_MIN, SCRAPER_DELAY_MAX))
        logger.info(f"🕷️  Scraper total (dedup) for {country_code}: {len(out)} real products")
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
                    "hint": "Tu app Hotmart necesita scopes de afiliación.",
                }
            if resp.status_code == 404:
                return {"error": "Producto no afiliable o no existe", "status": "not_found"}
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
                "Tu token OAuth funciona pero tu app no tiene scopes de afiliación."
            ),
        }

    async def _authed_get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
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
            if not resp.content or not resp.text.strip():
                return {"status": "ok", "items": [], "page_info": {"total_results": 0}}
            try:
                return {"status": "ok", **resp.json()}
            except Exception:
                return {"status": "ok", "items": [], "page_info": {"total_results": 0}, "note": "empty_body"}

    async def list_my_affiliations(self, max_results: int = 50) -> Dict[str, Any]:
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


async def sync_my_affiliations(db) -> Dict[str, Any]:
    """Fetch user's real Hotmart affiliations and upsert into MongoDB."""
    api = HotmartAffiliateAPI()
    result = await api.list_my_affiliations(max_results=200)
    if result.get("status") != "ok":
        return {"status": result.get("status", "error"), "synced": 0, "error": result.get("error")}

    raw_items = result.get("items", []) or []
    normalized: List[Dict[str, Any]] = []

    for item in raw_items:
        product = item.get("product") or {}
        hotmart_id = str(
            item.get("product_id")
            or product.get("id")
            or item.get("id")
            or ""
        ).strip()
        if not hotmart_id:
            continue

        hotlink = (
            item.get("hotlink")
            or item.get("link")
            or product.get("hotlink")
            or item.get("affiliate_url")
        )
        title = (
            product.get("name")
            or item.get("name")
            or item.get("product_name")
            or f"Producto Hotmart {hotmart_id}"
        )
        category = product.get("category") or item.get("category") or "General"
        commission = (
            item.get("commission_percent")
            or item.get("commission")
            or product.get("commission_percent")
            or 0.0
        )
        try:
            commission = float(commission)
        except Exception:
            commission = 0.0
        rating = float(product.get("rating") or item.get("rating") or 4.0)
        product_url = product.get("product_url") or item.get("product_url") or hotlink or ""
        creator = product.get("producer", {}).get("name") if isinstance(product.get("producer"), dict) else None
        creator = creator or item.get("producer") or product.get("creator") or "Creador Hotmart"

        doc = {
            "hotmart_id": hotmart_id,
            "title": str(title)[:220],
            "category": str(category)[:80],
            "commission_percent": commission,
            "rating": rating,
            "hotlink": hotlink,
            "product_url": str(product_url)[:500],
            "creator_name": str(creator)[:120],
            "raw": item,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.hotmart_affiliations.update_one(
            {"hotmart_id": hotmart_id},
            {"$set": doc},
            upsert=True,
        )
        normalized.append(doc)

    return {"status": "ok", "synced": len(normalized), "items": normalized}


def _text_match_score(title: str, category: str, keyword: str) -> float:
    text = f"{title} {category}".lower()
    kw = keyword.lower()
    if kw in text:
        return 1.0
    kw_words = [w for w in kw.split() if len(w) > 3]
    if not kw_words:
        return 0.0
    hits = sum(1 for w in kw_words if w in text)
    return hits / len(kw_words)


async def match_real_affiliations_to_trends(db, country_code: str, pain_keywords: List[str]) -> List[Dict]:
    cursor = db.hotmart_affiliations.find({}, {"_id": 0})
    affiliations = await cursor.to_list(length=500)
    if not affiliations:
        return []

    matched: List[Dict] = []
    for aff in affiliations:
        best_score = 0.0
        matched_kws: List[str] = []
        for kw in pain_keywords:
            s = _text_match_score(aff.get("title", ""), aff.get("category", ""), kw)
            if s > 0.0:
                matched_kws.append(kw)
                best_score = max(best_score, s)
        if not matched_kws:
            continue

        commission = float(aff.get("commission_percent") or 0.0)
        rating = float(aff.get("rating") or 4.0)
        profitability = round(min(100.0, (commission * rating) / 5.0), 2)
        relevance = round(min(100.0, best_score * 100 + profitability * 0.3), 2)

        matched.append({
            "hotmart_id": aff["hotmart_id"],
            "title": aff["title"],
            "category": aff["category"],
            "commission_percent": commission,
            "rating": rating,
            "sales_count_30d": 200,
            "product_url": aff.get("product_url") or aff.get("hotlink") or "",
            "creator_name": aff.get("creator_name", "Creador Hotmart"),
            "language": "es",
            "available_countries": [country_code],
            "is_fallback": False,
            "is_my_affiliation": True,
            "country_code": country_code,
            "matched_pain_points": matched_kws,
            "relevance_score": relevance,
            "profitability_score": profitability,
            "affiliate_status": "generated" if aff.get("hotlink") else "pending",
            "affiliate_link": aff.get("hotlink"),
            "tracking_id": "hotmart_api",
            "clicks_count": 0,
            "conversions_count": 0,
            "estimated_revenue": 0.0,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })
    return matched


# ========== Matching Engine (REAL products only) ==========
async def match_and_score(db, country_code: str, country_name: str, limit: int = 10, auto_links: bool = True) -> List[Dict]:
    """Pipeline real-only: pain_points → afiliaciones del usuario + marketplace scraping → scoring → upsert.

    NO genera productos con LLM. Si las dos fuentes reales no devuelven nada,
    retorna [] y el frontend muestra empty state.
    """
    # 1. Pull trends (pain points) for the country
    cursor = db.trends.find(
        {"country_code": country_code, "commercial_intent": {"$in": ["Alta", "Media"]}},
        {"_id": 0},
    ).sort("priority_score", -1).limit(10)
    trends = await cursor.to_list(length=10)
    if not trends:
        return []

    pain_keywords = [t["keyword"] for t in trends]

    # 2. Sync user's affiliations (if creds) and match
    real_affiliations: List[Dict] = []
    if hotmart_credentials_configured():
        try:
            await sync_my_affiliations(db)
            real_affiliations = await match_real_affiliations_to_trends(db, country_code, pain_keywords)
            if real_affiliations:
                logger.info(f"🔗 {len(real_affiliations)} user affiliations matched for {country_code}")
        except Exception as e:
            logger.warning(f"Affiliation sync failed: {e}")

    # 3. Marketplace scraping (REAL products only)
    scraped: List[Dict] = []
    if len(real_affiliations) < limit:
        try:
            scraper = HotmartMarketplaceScraper()
            scraped = await scraper.search(pain_keywords, country_code)
        except Exception as e:
            logger.warning(f"Marketplace scraping failed: {e}")

    # 4. Score scraped products
    scored_scraped: List[Dict] = []
    for p in scraped:
        commission = p.get("commission_percent", 0.0)
        rating = p.get("rating", 0.0)
        vol = p.get("sales_count_30d", 0)
        # Profitability proxy: rating + popularity (commission is unknown at scrape time)
        profitability = round(min(100.0, (rating * 15) + min(30.0, vol / 10)), 2)

        text = f"{p['title']} {p.get('category', '')}".lower()
        matches = [kw for kw in pain_keywords if kw.lower() in text]
        if not matches:
            words = set(text.split())
            for kw in pain_keywords:
                kw_words = set(kw.lower().split())
                if len(kw_words & words) >= max(1, len(kw_words) - 1):
                    matches.append(kw)
        relevance = min(100.0, (len(matches) / max(1, len(pain_keywords))) * 100 + profitability * 0.3)
        relevance = round(relevance, 2)

        scored_scraped.append({
            **p,
            "commission_percent": commission,
            "country_code": country_code,
            "is_my_affiliation": False,
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

    # 5. Merge: user affiliations first, then marketplace scraping. Dedupe by hotmart_id.
    seen = {p["hotmart_id"] for p in real_affiliations}
    merged = list(real_affiliations)
    for p in scored_scraped:
        if p["hotmart_id"] not in seen:
            merged.append(p)
            seen.add(p["hotmart_id"])

    merged.sort(
        key=lambda x: (
            1 if x.get("is_my_affiliation") else 0,
            x["relevance_score"] * 0.6 + x["profitability_score"] * 0.4,
        ),
        reverse=True,
    )
    top = merged[:limit]

    # 6. Clear previous cached products for this country before upserting new ones
    #    to avoid stale mocks from earlier runs.
    await db.products.delete_many({"country_code": country_code})

    # 7. Upsert fresh products
    for p in top:
        await db.products.update_one(
            {"hotmart_id": p["hotmart_id"], "country_code": country_code},
            {"$set": {**p, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

    return top
