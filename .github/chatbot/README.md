# FULL — Chatbot Instagram (prueba local)

Implementa el flujo definido en [../instructions/INSTRUCTIONS.md](../instructions/INSTRUCTIONS.md).

## Requisitos

Python 3.10+ (no hay un intérprete real en el PATH de esta máquina; instala Python desde
python.org o Microsoft Store antes de continuar).

## Ejecutar

```powershell
cd .github\chatbot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abre http://127.0.0.1:5000

## Conectar con Instagram via Meta

Este proyecto ahora incluye endpoints de webhook para la API oficial de Meta:

- `GET /webhook`: verificación del webhook
- `POST /webhook`: recepción de mensajes entrantes
- `GET /healthz`: estado básico del servicio

Variables de entorno requeridas para la integración real:

```powershell
$env:META_VERIFY_TOKEN="tu_verify_token"
$env:META_PAGE_ACCESS_TOKEN="tu_page_access_token"
$env:META_INSTAGRAM_ACCOUNT_ID="tu_instagram_business_account_id"
```

Opcional:

```powershell
$env:META_GRAPH_API_VERSION="v21.0"
```

Para guardar leads en Google Sheets con cuenta de servicio, agrega también:

```powershell
$env:GOOGLE_SHEETS_SPREADSHEET_ID="tu_spreadsheet_id"
$env:GOOGLE_SHEETS_WORKSHEET_NAME="Leads"
$env:GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
```

Si prefieres usar archivo JSON en vez de la cadena completa, puedes usar:

```powershell
$env:GOOGLE_SERVICE_ACCOUNT_FILE="/ruta/al/service-account.json"
```

Si no quieres usar Google Cloud, la alternativa gratis es Google Sheets + Apps Script.
Ese backend guarda los mismos campos que el Excel local, incluyendo Year, Month, Day y Hour.
Solo necesitas publicar un Web App y guardar su URL:

```powershell
$env:GOOGLE_APPS_SCRIPT_URL="https://script.google.com/macros/s/TU_DEPLOYMENT_ID/exec"
$env:GOOGLE_APPS_SCRIPT_TOKEN="token_opcional_para_proteger_el_endpoint"
```

El script listo para pegar está en [google_apps_script.gs](google_apps_script.gs).

Notas importantes:

- El servidor debe estar publicado con HTTPS para que Meta pueda llamar el webhook.
- La demo local en `/` sigue funcionando para pruebas manuales.
- Para mensajes reales de Instagram, el bot mantiene el estado por usuario en memoria del proceso.
- Si Meta no permite obtener el username del remitente, el sistema usa un identificador estable interno para no duplicar leads.
- Los leads se guardan primero en Google Apps Script si configuras `GOOGLE_APPS_SCRIPT_URL`.
- Si no hay Apps Script, el sistema intenta Google Sheets con cuenta de servicio.
- Si no hay backend en la nube configurado, se usa `leads.xlsx` como respaldo local.

## Configurar Google Sheets sin Google Cloud

1. Crea o abre tu Google Sheet y deja una pestaña llamada `Leads`.
2. Ve a `Extensiones > Apps Script`.
3. Pega el contenido de [google_apps_script.gs](google_apps_script.gs).
4. En el script, si quieres protegerlo, cambia `DEFAULT_TOKEN` por un valor secreto tuyo.
5. Haz clic en `Desplegar > Nueva implementación`.
6. Elige `Aplicación web`.
7. En `Ejecutar como`, selecciona tu cuenta.
8. En `Quién tiene acceso`, selecciona `Cualquiera` o `Cualquiera con el enlace`.
9. Copia la URL terminada en `/exec`.
10. En Render agrega `GOOGLE_APPS_SCRIPT_URL` con esa URL.
11. Si configuraste token, agrega también `GOOGLE_APPS_SCRIPT_TOKEN` con el mismo valor.
12. Vuelve a desplegar y prueba con un mensaje nuevo al chatbot.

## Probar sin navegador

```powershell
python test_flows.py
```

## Qué incluye

- Mensaje de bienvenida al iniciar/reiniciar la conversación.
- FAQs: ubicaciones, horarios, HYROX, precios y clase muestra.
- Preguntas de seguimiento (sucursal) antes de enviar imagen o link de WhatsApp.
- Captura de leads (Year, Month, Day, Hour, nombre, teléfono, correo, fecha de nacimiento, programa, sucursal) guardada en `leads.xlsx`.
- Handoff a WhatsApp cuando no entiende o el usuario pide un asesor.

## Personalizar

Números de WhatsApp, rutas de imágenes y programas se editan en [config.py](config.py).
Las imágenes van en [static/images](static/images).

## Despliegue público en Render

Este proyecto incluye [../../render.yaml](../../render.yaml) para desplegarlo como web service público con HTTPS en Render.

Variables de entorno importantes en producción:

```powershell
FLASK_SECRET_KEY=valor_secreto_largo
META_VERIFY_TOKEN=tu_verify_token
META_PAGE_ACCESS_TOKEN=tu_page_access_token
META_INSTAGRAM_ACCOUNT_ID=tu_instagram_business_account_id
META_GRAPH_API_VERSION=v21.0
```

En Render el servicio se levanta con `gunicorn --chdir .github/chatbot --bind 0.0.0.0:$PORT app:app`, por lo que no necesitas usar `FLASK_USE_HTTPS` en producción.
