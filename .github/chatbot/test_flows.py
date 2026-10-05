"""Console smoke test for the chatbot flows (no Flask/browser required)."""

import bot

SCRIPTS = [
    ["Wellness", "precios", "sucursales", "horarios"],
    ["hola", "donde estan ubicados", "Guadalupe"],
    ["horarios", "bosque santa anita"],
    ["que es hyrox"],
    ["cuanto cuesta la mensualidad", "guadalupe"],
    ["quiero una clase muestra", "Bosque Santa Anita"],
    ["quiero inscribirme"],
    ["quiero inscribirme en running en guadalupe"],
    ["hola", "mi numero es 8112345678", "running guadalupe"],
    ["hola", "me llamo Juan Perez", "mi nombre es Juan Perez", "mi numero es 8112223344", "wellness bosque santa anita"],
    ["horarios", "guadalupe", "precios", "clase muestra", "quiero inscribirme en running"],
    ["horarios", "guadalupe", "quiero otra sucursal", "bosque", "precios"],
    ["tienen alberca olimpica?"],
]


def render(reply):
    for msg in reply["messages"]:
        if msg["type"] == "text":
            print("BOT:", msg["content"].replace("\n", "\n     "))
        elif msg["type"] == "image":
            print("BOT: [imagen]", msg["url"])
        else:
            print("BOT: [link]", msg["label"], "->", msg["url"])
    if reply["quick_replies"]:
        print("     opciones:", " | ".join(reply["quick_replies"]))


for script in SCRIPTS:
    print("=" * 60)
    state = bot.new_state()
    bot.set_instagram_username(state, "@prueba_full")
    for message in script:
        print("YO :", message)
        render(bot.handle_message(message, state))
