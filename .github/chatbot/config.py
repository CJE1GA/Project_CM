"""Business configuration for the FULL fitness community chatbot."""

BRANCHES = {
    "guadalupe": {
        "name": "Guadalupe",
        "emoji": "\U0001F4CD",
        "pricing_image": "/static/images/precios_guadalupe.png",
        "whatsapp": "https://wa.me/528111111111?text=Hola%2C%20quiero%20mi%20clase%20muestra%20en%20Guadalupe",
    },
    "bosque": {
        "name": "Bosque Santa Anita",
        "emoji": "\U0001F4CD",
        "pricing_image": "/static/images/precios_bosque_santa_anita.png",
        "whatsapp": "https://wa.me/528122222222?text=Hola%2C%20quiero%20mi%20clase%20muestra%20en%20Bosque%20Santa%20Anita",
    },
}

WELLNESS = {
    "label": "Wellness",
    "pricing_image": "/static/images/precios_guadalupe.png",
    "location_branch": "guadalupe",
    "whatsapp": "https://wa.me/AQUI_VA_EL_NUMERO?text=Hola%2C%20quiero%20agendar%20mi%20cita%20de%20Wellness",
}

SCHEDULE_TEXT = (
    "Matutino:\n"
    "Lunes a Viernes: 6:00 - 9:00\n"
    "Sabados: 8:00 - 9:00\n\n"
    "Vaspertino:\n"
    "Lunes a Viernes: 17:00 - 20:00\n\n"
    "Animate a venir, te esperamos!!!\n"
    "A Full con Full"
)

PROGRAMS = ["HYROX", "Full Training", "Wellness", "Running"]

WELCOME_MESSAGE = (
    "¡Hola! 👋 Bienvenido a FULL.\n\n"
    "Aquí entrenamos, sudamos y cumplimos objetivos... aunque prometemos que "
    "las burpees no son obligatorias en esta conversación 😄.\n\n"
    "Estoy aquí para ayudarte con información sobre nuestras clases, horarios, "
    "costos, sucursales y clases muestra.\n\n"
    "¿En qué puedo ayudarte hoy?"
)

LEADS_FILE = "leads.xlsx"
LEAD_SOURCE = "Instagram"
