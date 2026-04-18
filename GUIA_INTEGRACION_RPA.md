# Guía de Integración: Agente RPA Hotmart

Esta guía explica cómo configurar y utilizar el nuevo módulo RPA (Robotic Process Automation) integrado en AffiliateAI-PRO-V1.

## 🚀 ¿Qué hace este módulo?

El Agente RPA automatiza el proceso completo de afiliación en Hotmart:
1. **Login automático** usando tus credenciales.
2. **Resolución de 2FA** (Verificación en dos pasos) extrayendo el código automáticamente desde tu correo Gmail.
3. **Búsqueda de productos** en el Marketplace basada en keywords.
4. **Afiliación automática** a los productos encontrados.
5. **Extracción del código de afiliado** único (`ap=XXXX`) para cada producto.
6. **Guardado en base de datos** para que el sistema pueda generar tus Hotlinks automáticamente.

---

## ⚙️ Configuración Necesaria

### 1. Instalar Dependencias

El módulo RPA utiliza Playwright para controlar un navegador oculto. Debes instalarlo en el entorno del backend:

```bash
cd backend
pip install playwright
playwright install chromium
```

### 2. Variables de Entorno

Añade las siguientes variables a tu archivo `backend/.env`:

```env
# Credenciales de Hotmart (Obligatorio)
HOTMART_EMAIL=tu_correo@ejemplo.com
HOTMART_PASSWORD=tu_contraseña_secreta

# Credenciales de Gmail para 2FA Automático (Recomendado)
# Nota: Debes usar una "Contraseña de Aplicación" de Google, no tu contraseña normal.
GMAIL_EMAIL=tu_correo@gmail.com
GMAIL_APP_PASSWORD=tu_contraseña_de_aplicacion_de_16_caracteres

# Configuración IMAP (Opcional, por defecto usa Gmail)
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
```

#### ¿Cómo obtener una Contraseña de Aplicación de Google?
1. Ve a tu Cuenta de Google > Seguridad.
2. Activa la Verificación en dos pasos (si no lo está).
3. Busca "Contraseñas de aplicaciones" y crea una nueva (ej. "AffiliateAI RPA").
4. Copia la contraseña de 16 letras y pégala en `GMAIL_APP_PASSWORD`.

---

## 💻 Cómo Usar el Panel RPA

El panel de control del Agente RPA ya está integrado en el Dashboard principal de la aplicación.

1. **Inicia la aplicación** (backend y frontend).
2. Ve al **Dashboard**.
3. Busca la sección **"Agente RPA Hotmart"**.
4. Ingresa las **Keywords** de los productos que buscas (ej. `marketing, finanzas`).
5. Selecciona el **País**.
6. Haz clic en **"Iniciar Agente RPA"**.

### Flujo de Ejecución

1. **Pendiente**: El agente se está iniciando.
2. **Ejecutando**: El agente está navegando por Hotmart de forma invisible.
3. **Esperando 2FA**: Si no configuraste el correo, el agente pausará y te pedirá que ingreses el código 2FA manualmente en la interfaz.
4. **Completado**: El agente terminó. Verás la lista de productos y los códigos de afiliado extraídos.
5. **Guardar**: Haz clic en el botón verde para guardar las afiliaciones en la base de datos.

---

## 🛠️ Archivos Modificados

La integración incluyó la creación y modificación de los siguientes archivos:

1. `backend/hotmart_rpa.py`: (NUEVO) Contiene toda la lógica de Playwright, IMAP y gestión de sesiones.
2. `backend/server.py`: (MODIFICADO) Se añadieron los endpoints `/api/rpa/*` para controlar el agente.
3. `frontend/src/components/RPAAgentPanel.jsx`: (NUEVO) Interfaz de usuario para controlar el agente.
4. `frontend/src/App.js`: (MODIFICADO) Se integró el `RPAAgentPanel` en el Dashboard.
5. `frontend/src/lib/api.js`: (MODIFICADO) Se añadieron las funciones para llamar a la API del RPA.

---

## ⚠️ Consideraciones de Seguridad y Uso

- **No compartas tu archivo `.env`**. Contiene tus credenciales reales.
- **Límites de Hotmart**: No ejecutes el agente cientos de veces al día para evitar bloqueos temporales por parte de Hotmart.
- **Modo Headless**: Por defecto, el navegador se ejecuta de forma invisible (`headless=True`). Si quieres ver qué está haciendo el agente para depurar, puedes desmarcar la opción "Modo silencioso" en la interfaz.
