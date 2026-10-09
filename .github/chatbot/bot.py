"""Intent detection and conversation flow for the FULL chatbot."""

import re
import unicodedata

from config import BRANCHES, PROGRAMS, SCHEDULE_TEXT, WELLNESS, WELCOME_MESSAGE
from leads import UNSPECIFIED, normalize_identifier, upsert_lead

BRANCH_QUICK_REPLIES = [BRANCHES["guadalupe"]["name"], BRANCHES["bosque"]["name"]]
MAIN_QUICK_REPLIES = [
    WELLNESS["label"],
    "Sucursales",
    "Horarios",
    "Precios",
    "¿Qué es HYROX?",
    "Clase muestra",
]
WELLNESS_HELP_QUICK_REPLIES = ["Precios", "Sucursales", "Horarios"]

PHONE_RE = re.compile(r"\+?[\d\s\-()]{8,20}")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
DATE_OF_BIRTH_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\s+de\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+\s+de\s+\d{4})\b",
    re.IGNORECASE,
)
NAME_PATTERNS = [
    re.compile(r"\bmi nombre es\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+){1,3})\b", re.IGNORECASE),
    re.compile(r"\bme llamo\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+){1,3})\b", re.IGNORECASE),
    re.compile(r"\bsoy\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+){1,3})\b", re.IGNORECASE),
]

INTENT_KEYWORDS = {
    "location": [
        "donde estan", "donde están", "ubicacion", "ubicación", "sucursal",
        "sucursales", "direccion", "dirección", "donde entreno",
        "donde puedo entrenar", "where are you", "location", "branch",
    ],
    "schedules": [
        "horario", "horarios", "clases", "que clases", "cuando puedo entrenar",
        "schedule", "schedules", "classes", "when can i train",
    ],
    "hyrox": [
        "hyrox", "que es hyrox", "what is hyrox",
    ],
    "pricing": [
        "precio", "precios", "costo", "costos", "cuanto cuesta", "mensualidad",
        "membresia", "membresía", "tarifas", "price", "pricing", "membership",
        "monthly fee", "how much",
    ],
    "trial": [
        "clase muestra", "clase de prueba", "prueba gratis", "puedo probar",
        "trial", "free trial", "try a class", "muestra",
    ],
    "lead": [
        "inscribirme", "inscripcion", "inscripción", "quiero unirme",
        "quiero entrenar", "registrarme", "me interesa", "quiero informacion para inscribirme",
        "sign up", "join", "enroll",
    ],
    "human": [
        "asesor", "humano", "persona", "hablar con alguien", "ayuda humana",
        "agente", "human", "talk to someone", "advisor",
    ],
    "greeting": [
        "hola", "buenas", "buenos dias", "buenos días", "buenas tardes",
        "hey", "hello", "hi", "que tal", "qué tal",
    ],
    "thanks": [
        "gracias", "thank you", "thanks", "muchas gracias",
    ],
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().strip())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text)


def _normalized_keywords():
    return {
        intent: [_normalize(k) for k in keywords]
        for intent, keywords in INTENT_KEYWORDS.items()
    }


NORMALIZED_KEYWORDS = _normalized_keywords()


def detect_intent(message: str) -> str:
    text = _normalize(message)
    best_intent, best_len = "fallback", 0
    for intent, keywords in NORMALIZED_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text and len(keyword) > best_len:
                best_intent, best_len = intent, len(keyword)
    return best_intent


def detect_branch(message: str):
    text = _normalize(message)
    if "guadalupe" in text or text in {"1", "a"}:
        return "guadalupe"
    if "bosque" in text or "santa anita" in text or "anita" in text or text in {"2", "b"}:
        return "bosque"
    return None


def detect_program(message: str):
    text = _normalize(message)
    for program in PROGRAMS:
        if _normalize(program) in text:
            return program
    if "correr" in text or "run" in text:
        return "Running"
    return None


def detect_phone(message: str):
    for match in PHONE_RE.finditer(message or ""):
        candidate = match.group(0).strip()
        digits = re.sub(r"\D", "", candidate)
        if len(digits) >= 8:
            return candidate
    return None


def detect_email(message: str):
    match = EMAIL_RE.search(message or "")
    if match:
        return match.group(0).strip().lower()
    return None


def detect_birth_date(message: str):
    match = DATE_OF_BIRTH_RE.search(message or "")
    if match:
        return " ".join(match.group(0).strip().split())
    return None


def detect_name(message: str):
    for pattern in NAME_PATTERNS:
        match = pattern.search(message or "")
        if not match:
            continue
        candidate = " ".join(match.group(1).strip().split())
        words = candidate.split()
        if any(word.lower() in {"guadalupe", "bosque", "anita", "running", "hyrox", "wellness"} for word in words):
            continue
        return " ".join(word.capitalize() for word in words)

    text = (message or "").strip()
    if not text:
        return None
    normalized = _normalize(text)
    if any(token in normalized for token in [
        "mi numero",
        "mi número",
        "telefono",
        "teléfono",
        "numero",
        "número",
        "clase muestra",
        "horarios",
        "precios",
        "sucursales",
        "hola",
        "gracias",
        "buenas",
        "whatsapp",
        "hyrox",
        "wellness",
        "running",
        "guadalupe",
        "bosque",
        "anita",
    ]):
        return None

    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", text)
    if 2 <= len(words) <= 4:
        cleaned = [word for word in words if word.lower() not in {"mi", "me", "llamo", "soy", "nombre", "es"}]
        if 2 <= len(cleaned) <= 4:
            candidate = " ".join(cleaned)
            if not any(token in _normalize(candidate).lower() for token in ["guadalupe", "bosque", "anita", "hyrox", "running", "wellness", "horarios", "precios", "sucursales"]):
                return " ".join(word.capitalize() for word in cleaned)
    return None


def new_state() -> dict:
    return {
        "pending": None,
        "lead": {
            "name": "",
            "phone": "",
            "email": "",
            "birth_date": "",
            "program": UNSPECIFIED,
            "branch": UNSPECIFIED,
            "registered": False,
        },
        "branch": None,
        "greeted": False,
        "instagram_username": "",
        "lead_identifier": "",
        "wellness_mode": False,
    }


def set_instagram_username(state: dict, username: str) -> None:
    cleaned = (username or "").strip()
    if not cleaned:
        return
    prefixed = cleaned if cleaned.startswith("@") else f"@{cleaned}"
    normalized = normalize_identifier(prefixed)
    state["instagram_username"] = normalized or prefixed.split()[0]


def set_lead_identifier(state: dict, identifier: str) -> None:
    normalized = (identifier or "").strip()
    if normalized:
        state["lead_identifier"] = normalized


IGNORED_EVENTS = {
    "share",
    "reel",
    "story_mention",
    "story_reply_media",
    "comment",
    "mention",
    "tag",
    "post",
    "reaction",
    "sticker",
    "audio",
    "image",
    "video",
    "file",
}

URL_ONLY_RE = re.compile(r"^(https?://\S+|www\.\S+)$", re.IGNORECASE)


def should_ignore(message: str, event_type: str = "text", attachments=None) -> bool:
    """Solo se atienden mensajes escritos en el DM; reels, etiquetas y comentarios se ignoran."""
    if (event_type or "text").lower() in IGNORED_EVENTS:
        return True
    if attachments:
        return True
    text = (message or "").strip()
    if not text:
        return True
    return bool(URL_ONLY_RE.match(text))


def _wants_branch_change(message: str) -> bool:
    text = _normalize(message)
    return any(
        phrase in text
        for phrase in ("otra sucursal", "cambiar sucursal", "cambiar de sucursal", "la otra sucursal")
    )


def _text(content):
    return {"type": "text", "content": content}


def _image(url, caption):
    return {"type": "image", "url": url, "caption": caption}


def _link(url, label):
    return {"type": "link", "url": url, "label": label}


def welcome():
    return {"messages": [_text(WELCOME_MESSAGE)], "quick_replies": MAIN_QUICK_REPLIES}


def _is_wellness_context(message: str, state: dict) -> bool:
    detected_program = detect_program(message)
    if detected_program == WELLNESS["label"]:
        state["wellness_mode"] = True
        state["branch"] = WELLNESS["location_branch"]
        return True
    if detected_program and detected_program != WELLNESS["label"]:
        state["wellness_mode"] = False
        return False
    return bool(state.get("wellness_mode"))


def _wellness_branch_key() -> str:
    return WELLNESS["location_branch"]


def _deliver_wellness_info(state, topic):
    branch = BRANCHES[_wellness_branch_key()]
    state["pending"] = None
    state["branch"] = _wellness_branch_key()
    state["wellness_mode"] = True

    if topic == "pricing":
        messages = [
            _text("Estos son los precios de Wellness 💳"),
            _image(WELLNESS["pricing_image"], f"Precios {branch['name']}"),
        ]
    elif topic == "schedules":
        messages = [
            _text("Para Wellness agenda tu cita directamente por WhatsApp ✨"),
            _link(WELLNESS["whatsapp"], "Agendar cita Wellness"),
        ]
    else:
        messages = [
            _text(
                f"Wellness se atiende en {branch['name']} 📍\n\n"
                "Si quieres, también te comparto precios o el enlace para agendar tu cita."
            )
        ]

    return {"messages": messages, "quick_replies": MAIN_QUICK_REPLIES}


def _show_wellness_menu(state):
    state["pending"] = None
    state["wellness_mode"] = True
    state["branch"] = _wellness_branch_key()
    return {
        "messages": [
            _text(
                "Perfecto, te ayudo con Wellness.\n\n"
                "Puedes pedirme precios, sucursal o el enlace para agendar tu cita."
            )
        ],
        "quick_replies": WELLNESS_HELP_QUICK_REPLIES,
    }


def _ask_branch(state, topic):
    if state.get("wellness_mode") and topic in {"location", "pricing", "schedules"}:
        return _deliver_wellness_info(state, topic)
    state["pending"] = f"branch:{topic}"
    prompts = {
        "schedules": "¡Claro! ¿De qué sucursal te gustaría ver los horarios?",
        "pricing": "¡Con gusto! ¿De qué sucursal quieres conocer los precios?",
        "trial": "¡Excelente decisión! 💪 ¿En qué sucursal prefieres tu clase muestra?",
        "location": "¿Sobre cuál sucursal te gustaría más información?",
    }
    return {
        "messages": [_text(prompts[topic])],
        "quick_replies": BRANCH_QUICK_REPLIES,
    }


def _ask_trial_name(state, branch_key):
    state["pending"] = f"name:trial:{branch_key}"
    state["branch"] = branch_key
    return {
        "messages": [
            _text(
                "¡Claro! Antes de enviarte el WhatsApp para agendar tu clase muestra, "
                "¿me puedes compartir tu nombre completo? 📝"
            )
        ],
        "quick_replies": [],
    }


def _ask_trial_email(state, branch_key):
    state["pending"] = f"email:trial:{branch_key}"
    state["branch"] = branch_key
    return {
        "messages": [
            _text("Gracias. Ahora compárteme tu correo electrónico, por favor ✉️")
        ],
        "quick_replies": [],
    }


def _ask_trial_phone(state, branch_key):
    state["pending"] = f"phone:trial:{branch_key}"
    state["branch"] = branch_key
    return {
        "messages": [
            _text("Perfecto. Ahora necesito tu número de teléfono 📱")
        ],
        "quick_replies": [],
    }


def _ask_trial_birth_date(state, branch_key):
    state["pending"] = f"dob:trial:{branch_key}"
    state["branch"] = branch_key
    return {
        "messages": [
            _text("Por último, compárteme tu fecha de nacimiento, por favor 📅")
        ],
        "quick_replies": [],
    }


def _deliver_trial_whatsapp(state, branch_key):
    branch = BRANCHES[branch_key]
    state["pending"] = None
    state["branch"] = branch_key
    return {
        "messages": [
            _text(
                f"¡Perfecto! Ya tengo tus datos. Escríbenos por WhatsApp de {branch['name']} y "
                "agendamos tu clase muestra 🙌"
            ),
            _link(branch["whatsapp"], f"WhatsApp {branch['name']}"),
        ],
        "quick_replies": MAIN_QUICK_REPLIES,
    }


def _advance_trial_flow(state, branch_key):
    lead = state.get("lead", {})
    if not (lead.get("name") or "").strip():
        return _ask_trial_name(state, branch_key)
    if not (lead.get("email") or "").strip():
        return _ask_trial_email(state, branch_key)
    if not (lead.get("phone") or "").strip():
        return _ask_trial_phone(state, branch_key)
    if not (lead.get("birth_date") or "").strip():
        return _ask_trial_birth_date(state, branch_key)
    return _deliver_trial_whatsapp(state, branch_key)


def _deliver_branch_info(state, topic, branch_key):
    if state.get("wellness_mode") and topic in {"location", "pricing", "schedules"}:
        return _deliver_wellness_info(state, topic)
    branch = BRANCHES[branch_key]
    state["pending"] = None
    state["branch"] = branch_key
    programs_by_branch = {
        "guadalupe": "HYROX, Full Training, Wellness y Running",
        "bosque": "HYROX y Full Training",
    }

    if topic == "schedules":
        messages = [
            _text(f"Estos son los horarios de {branch['name']} \U0001F5D3\uFE0F"),
            _text(SCHEDULE_TEXT),
        ]
    elif topic == "pricing":
        messages = [
            _text(f"Estos son nuestros planes en {branch['name']} 💳"),
            _image(branch["pricing_image"], f"Precios {branch['name']}"),
        ]
    elif topic == "trial":
        return _advance_trial_flow(state, branch_key)
    else:
        messages = [
            _text(
                f"{branch['emoji']} {branch['name']}\n\n"
                f"Ahí puedes entrenar {programs_by_branch.get(branch_key, 'HYROX y Full Training')}.\n"
                "¿Te comparto horarios, precios o una clase muestra?"
            )
        ]

    return {"messages": messages, "quick_replies": MAIN_QUICK_REPLIES}


def _lead_name(state: dict) -> str:
    lead = state.get("lead", {})
    real_name = (lead.get("name") or "").strip()
    instagram_username = (state.get("instagram_username") or "").strip()
    if real_name and instagram_username:
        return f"{real_name} ({instagram_username})"
    if real_name:
        return real_name
    if instagram_username:
        return instagram_username
    return "Usuario de Instagram"


def _lead_identifier(state: dict) -> str:
    explicit_identifier = (state.get("lead_identifier") or "").strip()
    if explicit_identifier:
        return explicit_identifier
    return normalize_identifier(state.get("instagram_username") or _lead_name(state))


def _sync_lead(state: dict, message: str) -> bool:
    lead = state.setdefault(
        "lead",
        {
            "name": "",
            "phone": "",
            "email": "",
            "birth_date": "",
            "program": UNSPECIFIED,
            "branch": UNSPECIFIED,
            "registered": False,
        },
    )
    changed = not lead.get("registered", False)

    name = detect_name(message)
    if name and name != lead.get("name"):
        lead["name"] = name
        changed = True

    phone = detect_phone(message)
    if phone and phone != lead.get("phone"):
        lead["phone"] = phone
        changed = True

    email = detect_email(message)
    if email and email != lead.get("email"):
        lead["email"] = email
        changed = True

    birth_date = detect_birth_date(message)
    if birth_date and birth_date != lead.get("birth_date"):
        lead["birth_date"] = birth_date
        changed = True

    program = detect_program(message)
    if program and program != lead.get("program"):
        lead["program"] = program
        changed = True

    branch_key = detect_branch(message) or state.get("branch")
    if branch_key:
        branch_name = BRANCHES[branch_key]["name"]
        if branch_name != lead.get("branch"):
            lead["branch"] = branch_name
            changed = True

    if changed:
        upsert_lead(
            _lead_name(state),
            lead.get("phone", ""),
            lead.get("email", ""),
            lead.get("birth_date", ""),
            lead.get("program", UNSPECIFIED),
            lead.get("branch", UNSPECIFIED),
            identifier=_lead_identifier(state),
        )
        lead["registered"] = True

    return changed


def _is_data_update_only(message: str) -> bool:
    normalized = _normalize(message)
    if detect_phone(message):
        return True
    if detect_email(message):
        return True
    if detect_birth_date(message):
        return True
    if detect_name(message):
        return True
    if detect_program(message) or detect_branch(message):
        return normalized not in {
            "horarios",
            "precio",
            "precios",
            "clase muestra",
            "sucursales",
            "guadalupe",
            "bosque",
            "bosque santa anita",
        }
    return False


def _start_lead(state, message: str):
    state["pending"] = None
    lead = state.get("lead", {})
    branch_name = lead.get("branch", UNSPECIFIED)
    program_name = lead.get("program", UNSPECIFIED)

    if branch_name != UNSPECIFIED:
        branch_key = next((key for key, branch in BRANCHES.items() if branch["name"] == branch_name), None)
        if branch_key:
            branch = BRANCHES[branch_key]
            return {
                "messages": [
                    _text(
                        f"Perfecto, ya tengo registrado tu interés en {program_name} para {branch_name}."
                    ),
                    _link(branch["whatsapp"], f"WhatsApp {branch['name']}"),
                ],
                "quick_replies": MAIN_QUICK_REPLIES,
            }

    return {
        "messages": [
            _text(
                "Perfecto, ya tengo registrado tu interés. También puedo compartirte horarios, precios o clase muestra."
            )
        ],
        "quick_replies": MAIN_QUICK_REPLIES,
    }


def _acknowledge_lead_update() -> dict:
    return {
        "messages": [_text("Gracias, actualicé tu registro con ese dato.")],
        "quick_replies": MAIN_QUICK_REPLIES,
    }


def _human_handoff(state):
    state["pending"] = None
    known = state.get("branch")
    branches = [BRANCHES[known]] if known else list(BRANCHES.values())
    links = [_link(b["whatsapp"], f"WhatsApp {b['name']}") for b in branches]
    detail = f" de {branches[0]['name']}" if known else " de la sucursal de tu preferencia"
    return {
        "messages": [
            _text(
                "Nuestro equipo estará encantado de ayudarte directamente. "
                f"Escríbenos por WhatsApp{detail}."
            ),
            *links,
        ],
        "quick_replies": MAIN_QUICK_REPLIES,
    }


def handle_message(message: str, state: dict) -> dict:
    message = (message or "").strip()
    if not message:
        return {"messages": [], "quick_replies": []}

    _sync_lead(state, message)

    if not state.get("greeted"):
        state["greeted"] = True
        reply = _route(message, state)
        greeting = welcome()
        if reply["messages"] and detect_intent(message) != "greeting":
            greeting["messages"].extend(reply["messages"])
            greeting["quick_replies"] = reply["quick_replies"]
        return greeting

    return _route(message, state)


def _route(message: str, state: dict) -> dict:
    pending = state.get("pending")
    wellness_context = _is_wellness_context(message, state)

    if _wants_branch_change(message):
        state["branch"] = None
        state["pending"] = None if state.get("wellness_mode") else "branch:location"
        if state.get("wellness_mode"):
            return _deliver_wellness_info(state, "location")
        return {
            "messages": [_text("¡Claro! ¿Qué sucursal te interesa ahora?")],
            "quick_replies": BRANCH_QUICK_REPLIES,
        }

    if pending and pending.startswith("branch:"):
        topic = pending.split(":", 1)[1]
        branch_key = detect_branch(message)
        if branch_key:
            return _deliver_branch_info(state, topic, branch_key)
        intent = detect_intent(message)
        if intent in {"location", "schedules", "hyrox", "pricing", "trial", "lead", "human"}:
            state["pending"] = None
        else:
            return {
                "messages": [_text("¿Te refieres a Guadalupe o a Bosque Santa Anita?")],
                "quick_replies": BRANCH_QUICK_REPLIES,
            }

    if pending and pending.startswith("name:trial:"):
        branch_key = pending.split(":", 2)[2]
        if (state.get("lead", {}).get("name") or "").strip():
            return _advance_trial_flow(state, branch_key)
        return {
            "messages": [
                _text("Para agendar tu clase muestra necesito tu nombre completo antes de enviarte el WhatsApp.")
            ],
            "quick_replies": [],
        }

    if pending and pending.startswith("email:trial:"):
        branch_key = pending.split(":", 2)[2]
        if (state.get("lead", {}).get("email") or "").strip():
            return _advance_trial_flow(state, branch_key)
        return {
            "messages": [
                _text("Para agendar tu clase muestra necesito tu correo electrónico antes de continuar.")
            ],
            "quick_replies": [],
        }

    if pending and pending.startswith("phone:trial:"):
        branch_key = pending.split(":", 2)[2]
        if (state.get("lead", {}).get("phone") or "").strip():
            return _advance_trial_flow(state, branch_key)
        return {
            "messages": [
                _text(
                    "Para agendar tu clase muestra necesito tu número de teléfono. "
                    "Envíamelo por aquí y continuamos enseguida."
                )
            ],
            "quick_replies": [],
        }

    if pending and pending.startswith("dob:trial:"):
        branch_key = pending.split(":", 2)[2]
        if (state.get("lead", {}).get("birth_date") or "").strip():
            return _deliver_trial_whatsapp(state, branch_key)
        return {
            "messages": [
                _text("Para agendar tu clase muestra necesito tu fecha de nacimiento antes de enviarte el WhatsApp.")
            ],
            "quick_replies": [],
        }

    branch_key = detect_branch(message)
    if branch_key:
        state["branch"] = branch_key

    intent = detect_intent(message)

    if wellness_context and _normalize(message) == _normalize(WELLNESS["label"]):
        return _show_wellness_menu(state)

    if intent == "greeting":
        return welcome()

    if intent == "location":
        if wellness_context:
            return _deliver_wellness_info(state, "location")
        if state.get("branch"):
            return _deliver_branch_info(state, "location", state["branch"])
        state["pending"] = "branch:location"
        return {
            "messages": [
                _text(
                    "Actualmente tenemos dos ubicaciones:\n\n"
                    "📍 Guadalupe\n\n"
                    "📍 Bosque Santa Anita\n\n"
                    "¿De cuál te gustaría más información?"
                )
            ],
            "quick_replies": BRANCH_QUICK_REPLIES,
        }

    if intent in {"schedules", "pricing", "trial"}:
        if wellness_context and intent in {"schedules", "pricing"}:
            return _deliver_wellness_info(state, intent)
        branch_key = detect_branch(message) or state.get("branch")
        if branch_key:
            return _deliver_branch_info(state, intent, branch_key)
        return _ask_branch(state, intent)

    if intent == "hyrox":
        return {
            "messages": [
                _text(
                    "HYROX es un programa de entrenamiento funcional que combina "
                    "ejercicios de resistencia y fuerza, diseñado para mejorar tu "
                    "rendimiento, condición física y acondicionamiento general. 💪"
                ),
                _text("¿Quieres ver horarios o probar una clase muestra?"),
            ],
            "quick_replies": MAIN_QUICK_REPLIES,
        }

    if intent == "lead":
        return _start_lead(state, message)

    if intent == "human":
        return _human_handoff(state)

    if intent == "thanks":
        return {
            "messages": [_text("¡Con mucho gusto! 🙌 Aquí estoy si necesitas algo más.")],
            "quick_replies": MAIN_QUICK_REPLIES,
        }

    if _is_data_update_only(message):
        return _acknowledge_lead_update()

    return _human_handoff(state)
