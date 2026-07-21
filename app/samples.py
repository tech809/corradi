"""Mensajes de ejemplo (reales) para demo, seed y tests.

Subconjunto curado del corpus de docs/mensajes_ejemplo.md. Incluye a propósito:
- un mensaje que NO es oportunidad (saludo) → debe clasificarse is_opportunity=false
- un repost EXACTO del primero → debe deduplicarse por hash
"""

SAMPLE_MESSAGES: list[str] = [
    # 1) Intercambio juvenil — Polonia
    """🚨URGENTE! 🚨 Estamos buscando líder del grupo para:
Proyecto: "DIGITAL DETOX" 📱
✨Tipo del proyecto: Intercambio juvenil
📍Lugar: Piotrków Trybunalski, Poland
📅 Fechas: 23/06/2026 - 30/06/2026
🕵️‍♀️ Plazas disponibles: 1 líder del grupo
💰 Reembolso de los gastos de viaje: Hasta 395 EUR
❓INFO PACK: https://www.canva.com/design/DAHEBpmiRJY/edit
❓APPLICATION FORM: https://docs.google.com/forms/d/e/1FAIpQLSdiFork734aZpl18hsT-1aEdszFnEQNM9SF1PVsxcv76PjIqw/viewform
Deadline: lo antes posible!
Para más información: info.culturacreativa@gmail.com""",

    # 2) Training course — Alemania
    """🇩🇪🇩🇪 TRAINING: TOOLS FOR CHANGE
📅 Fechas:  22-31 de julio de 2026
📍 Lugar: Alemania
🍁 Tema: Enfrentando los desafíos actuales tanto internos como externos
👥 Participantes: (mayores de 18 años)
✈️ Viaje: financiado por el programa Erasmus+.
Info pack: https://drive.proton.me/urls/E30RG22M5G
Solicitud: https://docs.google.com/forms/d/e/1FAIpQLSeTMsSW7sdNBlM6N4s7v4oi4ai1iqNmfLucrgBsp3HRryuyPg/viewform
Contacto: tools-for-change@protonmail.com""",

    # 3) Youth Exchange — Letonia
    """🇱🇻 YOUTH EXCHANGE "Where Words Wander" 🇱🇻
📅 Fechas: 10 - 20 de agosto de 2026
📍 Lugar: Letonia
🍁 Tema: Senderismo y storytelling
👥 Participantes: 2 (>18 años)
✈️ Viaje: se cubre hasta 395 euros
Infopack https://canva.link/1vj09z4lel85j4n
Una vez seleccionad@, habrá que abonar una cuota de 20€
Solicitudes: https://forms.gle/DoaPRZBKL5CgyZsSA
Contacto asoc.talasa@gmail.com""",

    # 4) Training Course — Italia (plaza de última hora; empieza con tono informal)
    """📢 LLAMADA URGENTE A PARTICIPANTES QUE RESIDAN EN ESPAÑA 🇪🇸
🌿 The Sound of Silence – Training Course
Por caída de una participante, la asociación Kunstant busca 1 persona de última hora para una movilidad Erasmus+ en Italia.
📅 Fechas: 7 – 15 de julio de 2026
📍 Lugar: Cesi, Terni, Umbría, Italia 🇮🇹
🗣️ Idioma de trabajo: Inglés
💰 Alojamiento, comida y actividades cubiertas por Erasmus+. Reembolso de viaje hasta 259 € desde España. Cuota de 30 €.
📄 Infopack: https://www.canva.com/design/DAG_OmWmSGo/view
📝 Email a kunstant.erasmusplus@gmail.com y formulario: https://forms.gle/YvcGpXEsPRdQd5TM8
⏰ Convocatoria abierta hasta cubrir la plaza.""",

    # 5) Youth Exchange — Eslovaquia (Wearwise; intro tipo "pausa de hidratación")
    """PAUSA DE HIDRATACIÓN‼️
Tanto si te dejas 100€ en una camiseta como si compras falsificaciones, este proyecto te interesa. 😎
Wearwise es un proyecto sobre los desafíos de la "fast fashion" y el consumo ético y responsable de moda. 👕
📍 Banska Stiavnica, Eslovaquia
📆 22 - 31 Julio 2026
👥 4 participantes
https://forms.gle/sCZ2nnq4nriLFjS96
Aplica rápido que te vas en un mes! 🚀""",

    # 6) NO es oportunidad (saludo) → is_opportunity=false
    """Hola a todos!! gracias por el finde, lo pasé genial 🙌 nos vemos en el próximo""",

    # 7) Repost EXACTO del 1 → se deduplica por hash
    """🚨URGENTE! 🚨 Estamos buscando líder del grupo para:
Proyecto: "DIGITAL DETOX" 📱
✨Tipo del proyecto: Intercambio juvenil
📍Lugar: Piotrków Trybunalski, Poland
📅 Fechas: 23/06/2026 - 30/06/2026
🕵️‍♀️ Plazas disponibles: 1 líder del grupo
💰 Reembolso de los gastos de viaje: Hasta 395 EUR
❓INFO PACK: https://www.canva.com/design/DAHEBpmiRJY/edit
❓APPLICATION FORM: https://docs.google.com/forms/d/e/1FAIpQLSdiFork734aZpl18hsT-1aEdszFnEQNM9SF1PVsxcv76PjIqw/viewform
Deadline: lo antes posible!
Para más información: info.culturacreativa@gmail.com""",
]
