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

Notas importantes:

- El servidor debe estar publicado con HTTPS para que Meta pueda llamar el webhook.
- La demo local en `/` sigue funcionando para pruebas manuales.
- Para mensajes reales de Instagram, el bot mantiene el estado por usuario en memoria del proceso.
- Si Meta no permite obtener el username del remitente, el sistema usa un identificador estable interno para no duplicar leads.

## Probar sin navegador

```powershell
python test_flows.py
```

## Qué incluye

- Mensaje de bienvenida al iniciar/reiniciar la conversación.
- FAQs: ubicaciones, horarios, HYROX, precios y clase muestra.
- Preguntas de seguimiento (sucursal) antes de enviar imagen o link de WhatsApp.
- Captura de leads (nombre, teléfono, programa, sucursal) guardada en `leads.xlsx`.
- Handoff a WhatsApp cuando no entiende o el usuario pide un asesor.

## Personalizar

Números de WhatsApp, rutas de imágenes y programas se editan en [config.py](config.py).
Las imágenes van en [static/images](static/images).
