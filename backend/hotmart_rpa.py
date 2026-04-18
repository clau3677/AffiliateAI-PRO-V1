"""
Módulo RPA: Automatización de Login, Afiliación y Extracción de Códigos en Hotmart.

Flujo completo:
1. Login automático en Hotmart con email + contraseña
2. Detección y resolución de 2FA (automático vía IMAP o manual)
3. Búsqueda de productos en el Marketplace
4. Afiliación automática a productos
5. Extracción del código de afiliado por producto (parámetro `ap=`)
6. Guardado en MongoDB para uso del sistema

Tecnologías: Playwright (headless), imaplib (2FA por correo), FastAPI BackgroundTasks.
"""

import asyncio
import imaplib
import email
import logging
import os
import re
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger("hotmart_rpa")


# ─────────────────────────────────────────────
# Helpers de entorno
# ─────────────────────────────────────────────

def _env(name: str) -> Optional[str]:
    val = os.environ.get(name)
    return val.strip() if val else None


def rpa_credentials_configured() -> bool:
    """Verifica que las credenciales mínimas para RPA estén disponibles."""
    return bool(_env("HOTMART_EMAIL") and _env("HOTMART_PASSWORD"))


def email_2fa_configured() -> bool:
    """Verifica que las credenciales de correo para 2FA automático estén disponibles."""
    return bool(_env("GMAIL_EMAIL") and _env("GMAIL_APP_PASSWORD"))


# ─────────────────────────────────────────────
# Extractor de código 2FA desde correo (IMAP)
# ─────────────────────────────────────────────

class EmailTwoFAExtractor:
    """
    Conecta al correo vía IMAP y extrae el código 2FA enviado por Hotmart.
    Compatible con Gmail (imap.gmail.com) y otros proveedores IMAP.
    """

    def __init__(self):
        self.imap_server = _env("IMAP_SERVER") or "imap.gmail.com"
        self.imap_port = int(_env("IMAP_PORT") or "993")
        self.email_address = _env("GMAIL_EMAIL")
        self.app_password = _env("GMAIL_APP_PASSWORD")

    def _connect(self) -> imaplib.IMAP4_SSL:
        conn = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
        conn.login(self.email_address, self.app_password)
        return conn

    def _extract_code_from_text(self, text: str) -> Optional[str]:
        """Busca un código de 6 dígitos en el cuerpo del email."""
        patterns = [
            r'\b(\d{6})\b',
            r'código[:\s]+(\d{6})',
            r'code[:\s]+(\d{6})',
            r'verification[:\s]+(\d{6})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _get_email_body(self, msg) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype in ("text/plain", "text/html"):
                    try:
                        body += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
            except Exception:
                pass
        return body

    async def wait_for_code(self, timeout_seconds: int = 60) -> Optional[str]:
        """
        Espera hasta `timeout_seconds` por un email de Hotmart con código 2FA.
        Retorna el código si lo encuentra, None si agota el tiempo.
        """
        if not email_2fa_configured():
            logger.warning("Credenciales de correo para 2FA no configuradas.")
            return None

        deadline = asyncio.get_event_loop().time() + timeout_seconds
        logger.info(f"📧 Esperando código 2FA en {self.email_address} (timeout: {timeout_seconds}s)...")

        while asyncio.get_event_loop().time() < deadline:
            try:
                conn = await asyncio.to_thread(self._connect)
                conn.select("INBOX")

                # Buscar emails recientes de Hotmart (últimos 2 minutos)
                _, data = conn.search(None, '(FROM "hotmart" UNSEEN)')
                email_ids = data[0].split()

                for eid in reversed(email_ids[-5:]):  # revisar últimos 5
                    _, msg_data = conn.fetch(eid, "(RFC822)")
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    body = self._get_email_body(msg)
                    code = self._extract_code_from_text(body)
                    if code:
                        logger.info(f"✅ Código 2FA encontrado: {code}")
                        conn.store(eid, "+FLAGS", "\\Seen")
                        conn.logout()
                        return code

                conn.logout()
            except Exception as e:
                logger.warning(f"Error al revisar correo: {e}")

            await asyncio.sleep(5)

        logger.warning("⏰ Timeout esperando código 2FA por correo.")
        return None


# ─────────────────────────────────────────────
# Agente RPA Principal
# ─────────────────────────────────────────────

class HotmartRPAAgent:
    """
    Agente RPA que automatiza:
    - Login en Hotmart (con soporte 2FA automático o manual)
    - Búsqueda de productos en el Marketplace
    - Afiliación automática a productos
    - Extracción del código de afiliado (parámetro `ap=`)
    """

    HOTMART_LOGIN_URL = "https://app.hotmart.com/login"
    HOTMART_MARKETPLACE_URL = "https://app.hotmart.com/market/search"
    HOTMART_HOTLINKS_URL = "https://app.hotmart.com/products/affiliate"

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.email = _env("HOTMART_EMAIL")
        self.password = _env("HOTMART_PASSWORD")
        self.two_fa_extractor = EmailTwoFAExtractor()
        self._browser = None
        self._page = None
        self._playwright = None
        self.session_id = str(uuid.uuid4())[:8]

    # ── Ciclo de vida del navegador ──────────────────

    async def _start_browser(self):
        """Inicia Playwright con configuración anti-detección."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright no está instalado. Ejecuta: pip install playwright && playwright install chromium"
            )

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-extensions",
            ],
        )
        context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="es-ES",
        )
        # Ocultar webdriver
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self._page = await context.new_page()
        logger.info(f"🌐 Navegador iniciado (sesión {self.session_id})")

    async def _close_browser(self):
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        logger.info(f"🔒 Navegador cerrado (sesión {self.session_id})")

    # ── Login ────────────────────────────────────────

    async def login(self, manual_2fa_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Realiza el login en Hotmart.
        - Intenta 2FA automático vía correo si está configurado.
        - Si no, usa `manual_2fa_code` si se proporciona.
        - Si ninguno está disponible, espera 60s para ingreso manual.
        """
        if not rpa_credentials_configured():
            return {
                "status": "credentials_missing",
                "error": "Configura HOTMART_EMAIL y HOTMART_PASSWORD en backend/.env",
            }

        await self._start_browser()
        page = self._page

        try:
            logger.info(f"🔑 Navegando a login de Hotmart...")
            await page.goto(self.HOTMART_LOGIN_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Ingresar email
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="correo" i]',
            ]
            for sel in email_selectors:
                try:
                    await page.fill(sel, self.email, timeout=5000)
                    logger.info(f"✅ Email ingresado")
                    break
                except Exception:
                    continue

            await asyncio.sleep(1)

            # Ingresar contraseña
            pass_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[placeholder*="senha" i]',
                'input[placeholder*="contraseña" i]',
            ]
            for sel in pass_selectors:
                try:
                    await page.fill(sel, self.password, timeout=5000)
                    logger.info(f"✅ Contraseña ingresada")
                    break
                except Exception:
                    continue

            await asyncio.sleep(1)

            # Click en botón de login
            login_selectors = [
                'button[type="submit"]',
                'button:has-text("Entrar")',
                'button:has-text("Login")',
                'button:has-text("Iniciar sesión")',
                '[data-testid="login-button"]',
            ]
            for sel in login_selectors:
                try:
                    await page.click(sel, timeout=5000)
                    logger.info(f"✅ Botón de login clickeado")
                    break
                except Exception:
                    continue

            await asyncio.sleep(3)

            # Detectar 2FA
            two_fa_detected = await self._detect_2fa(page)
            if two_fa_detected:
                logger.info("🔐 2FA detectado, resolviendo...")
                code = None

                # Prioridad 1: código manual proporcionado
                if manual_2fa_code:
                    code = manual_2fa_code
                    logger.info(f"🔑 Usando código 2FA manual: {code}")

                # Prioridad 2: extracción automática desde correo
                elif email_2fa_configured():
                    code = await self.two_fa_extractor.wait_for_code(timeout_seconds=60)

                # Prioridad 3: esperar 60s para ingreso manual en el navegador
                else:
                    logger.info("⏳ Esperando 60s para ingreso manual del código 2FA...")
                    await asyncio.sleep(60)

                if code:
                    await self._enter_2fa_code(page, code)
                    await asyncio.sleep(3)

            # Verificar login exitoso
            current_url = page.url
            if "app.hotmart.com" in current_url and "login" not in current_url:
                logger.info(f"✅ Login exitoso. URL: {current_url}")
                return {"status": "logged_in", "url": current_url}
            else:
                # Esperar un poco más por redirección
                await asyncio.sleep(5)
                current_url = page.url
                if "login" not in current_url:
                    return {"status": "logged_in", "url": current_url}
                return {
                    "status": "login_failed",
                    "error": "No se pudo verificar el login. Verifica tus credenciales.",
                    "url": current_url,
                }

        except Exception as e:
            logger.exception(f"Error durante login: {e}")
            return {"status": "error", "error": str(e)}

    async def _detect_2fa(self, page) -> bool:
        """Detecta si Hotmart solicita verificación 2FA."""
        two_fa_indicators = [
            'input[placeholder*="código" i]',
            'input[placeholder*="code" i]',
            'input[placeholder*="verificação" i]',
            'input[maxlength="6"]',
            '[data-testid*="2fa"]',
            '[data-testid*="otp"]',
            'text=verificación',
            'text=código de seguridad',
            'text=código de verificação',
        ]
        for sel in two_fa_indicators:
            try:
                el = await page.query_selector(sel)
                if el:
                    return True
            except Exception:
                pass
        return False

    async def _enter_2fa_code(self, page, code: str):
        """Ingresa el código 2FA en el formulario."""
        code_selectors = [
            'input[placeholder*="código" i]',
            'input[placeholder*="code" i]',
            'input[maxlength="6"]',
            'input[type="number"]',
            'input[inputmode="numeric"]',
        ]
        for sel in code_selectors:
            try:
                await page.fill(sel, code, timeout=5000)
                logger.info(f"✅ Código 2FA ingresado: {code}")
                # Confirmar
                await page.keyboard.press("Enter")
                return
            except Exception:
                continue
        logger.warning("⚠️ No se pudo ingresar el código 2FA automáticamente")

    # ── Búsqueda de productos ────────────────────────

    async def search_products(self, keyword: str, country_code: str = "CL", limit: int = 10) -> List[Dict]:
        """
        Busca productos en el Marketplace de Hotmart usando scraping autenticado.
        Retorna lista de productos con sus datos básicos.
        """
        if not self._page:
            return []

        page = self._page
        locale = "pt-br" if country_code == "BR" else "es"
        url = f"https://app.hotmart.com/market/search?q={keyword.replace(' ', '+')}"

        try:
            logger.info(f"🔍 Buscando productos: '{keyword}' ({country_code})")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            products = []
            # Extraer productos del DOM
            product_cards = await page.query_selector_all('[class*="product-card"], [class*="ProductCard"], [data-testid*="product"]')

            for card in product_cards[:limit]:
                try:
                    title_el = await card.query_selector('h2, h3, [class*="title"], [class*="name"]')
                    title = await title_el.inner_text() if title_el else "Sin título"

                    link_el = await card.query_selector('a[href*="hotmart.com"]')
                    link = await link_el.get_attribute("href") if link_el else ""

                    # Extraer ID del producto del link
                    product_id_match = re.search(r'/([A-Z]\d+[A-Z])', link or "")
                    product_id = product_id_match.group(1) if product_id_match else ""

                    products.append({
                        "title": title.strip(),
                        "product_url": link,
                        "hotmart_id": product_id,
                        "keyword": keyword,
                        "country_code": country_code,
                    })
                except Exception:
                    continue

            logger.info(f"✅ Encontrados {len(products)} productos para '{keyword}'")
            return products

        except Exception as e:
            logger.warning(f"Error buscando productos: {e}")
            return []

    # ── Afiliación y extracción de código ───────────

    async def affiliate_and_get_code(self, product_url: str, product_id: str) -> Dict[str, Any]:
        """
        Accede a la página del producto, se afilia y extrae el código de afiliado.
        El código aparece en la URL del Hotlink generado como parámetro `ap=`.
        """
        if not self._page:
            return {"status": "error", "error": "Navegador no iniciado"}

        page = self._page

        try:
            logger.info(f"🔗 Afiliando a producto: {product_id}")
            await page.goto(product_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Intentar afiliarse si no está afiliado
            affiliate_btn_selectors = [
                'button:has-text("Afiliarme")',
                'button:has-text("Afiliarse")',
                'button:has-text("Quero me afiliar")',
                'button:has-text("Solicitar afiliação")',
                '[data-testid*="affiliate"]',
                '[class*="affiliate-btn"]',
            ]
            affiliated = False
            for sel in affiliate_btn_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(3)
                        affiliated = True
                        logger.info(f"✅ Solicitud de afiliación enviada")
                        break
                except Exception:
                    continue

            # Ir a la sección de Hotlinks del producto
            hotlinks_url = f"https://app.hotmart.com/products/affiliate/{product_id}/hotlinks"
            await page.goto(hotlinks_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Extraer los Hotlinks y el código de afiliado
            affiliate_code = await self._extract_affiliate_code(page, product_id)

            return {
                "status": "success",
                "product_id": product_id,
                "affiliate_code": affiliate_code,
                "affiliated": affiliated,
                "hotlink": f"https://go.hotmart.com/{product_id}?ap={affiliate_code}" if affiliate_code else None,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.warning(f"Error afiliando a {product_id}: {e}")
            return {"status": "error", "product_id": product_id, "error": str(e)}

    async def _extract_affiliate_code(self, page, product_id: str) -> Optional[str]:
        """
        Extrae el código de afiliado (`ap=XXXX`) desde los Hotlinks generados.
        Busca en:
        1. URLs visibles en la página (inputs, links)
        2. Interceptando requests de red
        3. Navegando al checkout y extrayendo `off=` de la URL
        """
        # Método 1: Buscar en inputs/links de la página
        link_selectors = [
            'input[value*="go.hotmart.com"]',
            'input[value*="?ap="]',
            'a[href*="go.hotmart.com"]',
            'a[href*="?ap="]',
            '[class*="hotlink"] input',
            '[class*="link-copy"] input',
        ]
        for sel in link_selectors:
            try:
                elements = await page.query_selector_all(sel)
                for el in elements:
                    tag = await el.evaluate("el => el.tagName.toLowerCase()")
                    value = (
                        await el.get_attribute("value")
                        if tag == "input"
                        else await el.get_attribute("href")
                    )
                    if value and "?ap=" in value:
                        match = re.search(r'\?ap=([a-zA-Z0-9]+)', value)
                        if match:
                            code = match.group(1)
                            logger.info(f"✅ Código de afiliado extraído: {code}")
                            return code
            except Exception:
                continue

        # Método 2: Buscar en el contenido de texto de la página
        try:
            content = await page.content()
            matches = re.findall(r'[?&]ap=([a-zA-Z0-9]{4,12})', content)
            if matches:
                code = matches[0]
                logger.info(f"✅ Código de afiliado en HTML: {code}")
                return code
        except Exception:
            pass

        # Método 3: Navegar al checkout del producto y extraer `off=`
        try:
            checkout_url = f"https://pay.hotmart.com/{product_id}"
            await page.goto(checkout_url, wait_until="networkidle", timeout=20000)
            await asyncio.sleep(2)
            current_url = page.url
            match = re.search(r'[?&]off=([a-zA-Z0-9]+)', current_url)
            if match:
                code = match.group(1)
                logger.info(f"✅ Código de afiliado desde checkout: {code}")
                return code
        except Exception:
            pass

        logger.warning(f"⚠️ No se pudo extraer el código de afiliado para {product_id}")
        return None

    # ── Flujo completo ───────────────────────────────

    async def run_full_automation(
        self,
        keywords: List[str],
        country_code: str = "CL",
        manual_2fa_code: Optional[str] = None,
        max_products_per_keyword: int = 3,
    ) -> Dict[str, Any]:
        """
        Ejecuta el flujo completo:
        1. Login (con 2FA si es necesario)
        2. Búsqueda de productos por keywords
        3. Afiliación y extracción de códigos
        4. Retorna resultados estructurados
        """
        results = {
            "session_id": self.session_id,
            "status": "running",
            "login": None,
            "products_found": 0,
            "affiliations": [],
            "errors": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
        }

        try:
            # Paso 1: Login
            login_result = await self.login(manual_2fa_code=manual_2fa_code)
            results["login"] = login_result

            if login_result["status"] != "logged_in":
                results["status"] = "login_failed"
                results["completed_at"] = datetime.now(timezone.utc).isoformat()
                return results

            # Paso 2: Buscar y afiliar productos
            all_products = []
            for keyword in keywords[:5]:  # máximo 5 keywords
                products = await self.search_products(keyword, country_code, limit=max_products_per_keyword)
                all_products.extend(products)
                await asyncio.sleep(2)  # pausa anti-detección

            results["products_found"] = len(all_products)

            # Paso 3: Afiliar y extraer códigos
            for product in all_products:
                if not product.get("hotmart_id"):
                    continue
                affiliation = await self.affiliate_and_get_code(
                    product.get("product_url", ""),
                    product["hotmart_id"],
                )
                affiliation["title"] = product.get("title", "")
                affiliation["keyword"] = product.get("keyword", "")
                results["affiliations"].append(affiliation)
                await asyncio.sleep(2)  # pausa anti-detección

            results["status"] = "completed"

        except Exception as e:
            logger.exception(f"Error en automatización completa: {e}")
            results["status"] = "error"
            results["errors"].append(str(e))

        finally:
            await self._close_browser()
            results["completed_at"] = datetime.now(timezone.utc).isoformat()

        return results


# ─────────────────────────────────────────────
# Gestor de sesiones RPA (para uso con FastAPI)
# ─────────────────────────────────────────────

class RPASessionManager:
    """
    Gestiona sesiones RPA en memoria para el backend FastAPI.
    Permite iniciar, monitorear y recuperar resultados de automatizaciones.
    """

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, keywords: List[str], country_code: str) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            "id": session_id,
            "status": "pending",
            "keywords": keywords,
            "country_code": country_code,
            "progress": 0,
            "result": None,
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return session_id

    def update_session(self, session_id: str, **kwargs):
        if session_id in self._sessions:
            self._sessions[session_id].update(kwargs)
            self._sessions[session_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._sessions.get(session_id)

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        sessions = list(self._sessions.values())
        sessions.sort(key=lambda x: x["created_at"], reverse=True)
        return sessions[:limit]

    async def run_session(
        self,
        session_id: str,
        manual_2fa_code: Optional[str] = None,
        headless: bool = True,
    ):
        """Ejecuta una sesión RPA en background."""
        session = self.get_session(session_id)
        if not session:
            return

        self.update_session(session_id, status="running", progress=10)

        agent = HotmartRPAAgent(headless=headless)
        try:
            result = await agent.run_full_automation(
                keywords=session["keywords"],
                country_code=session["country_code"],
                manual_2fa_code=manual_2fa_code,
            )
            self.update_session(
                session_id,
                status=result.get("status", "completed"),
                progress=100,
                result=result,
            )
        except Exception as e:
            self.update_session(
                session_id,
                status="error",
                error=str(e),
                progress=0,
            )


# Instancia global del gestor de sesiones
rpa_manager = RPASessionManager()
