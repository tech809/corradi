# CORRADI-BOT 2030 — hacia dónde podemos llegar

> "Ningún joven europeo se queda fuera de una oportunidad Erasmus+ porque no se enteró a tiempo, no entendió el papeleo, o llegó tarde a un formulario que se cerró en 48 horas."

Esa es la frase que debería poder decirse sin mentir dentro de cuatro años. Todo lo demás — el bot, el mapa, la app, el LLM — es infraestructura al servicio de esa frase. Este documento no es un backlog (para eso está [`ideas_futuras_web.md`](ideas_futuras_web.md), que es track técnico y a corto plazo del propio mapa web). Esto es la pregunta de fondo: **si nos tomáramos este proyecto tan en serio como SpaceX se toma llegar a Marte, o Apple se toma que un iPhone se sienta inevitable en la mano, ¿qué construiríamos?**

Documento vivo, escrito el 2026-07-29. Contexto real que lo ancla (no es ciencia ficción): CORRADI-BOT es un proyecto Erasmus+ KA210-YOU, 60.000 € lump sum, 14 meses (sep-2026 a oct-2027), con Proactive Future como solicitante y LIFE (Rumanía) y DreamTeam (Grecia) como socios. El compromiso de propuesta ya incluye RAG chatbot, app móvil React Native + Expo, y una meta de 500+ oportunidades verificadas y 150-200 usuarios beta en 3 países. Todo lo de aquí abajo, o encaja en esa hoja de ruta, o es la semilla de la fase 2 (post-KA210) que justifica seguir financiando esto.

**La métrica norte:** no "usuarios activos". Es **"plazas Erasmus+ ocupadas por alguien que sin esto no se habría enterado a tiempo"**. Cada decisión de producto se puede pesar contra esa única pregunta.

---

## 0. El problema de verdad (para no construir la solución equivocada)

No es "falta un catálogo". Catálogos hay — SALTO-YOUTH, decenas de páginas de socios, grupos de Facebook, el propio canal de WhatsApp actual. El problema real tiene cuatro capas, y cada una necesita una solución distinta:

1. **Descubrimiento**: la oportunidad correcta existe, pero el joven correcto nunca la ve (llega en un canal que no sigue, en un idioma que no domina, en un formato ilegible en el móvil a las 23h).
2. **Confianza**: cuando la ve, no sabe si es real, si el organizador es serio, si el "gratis" tiene letra pequeña.
3. **Fricción de entrada**: entender qué es un "training course" frente a un "youth exchange", si tiene la edad, si necesita algo que no tiene (pasaporte, cuenta bancaria, disponibilidad).
4. **Abandono en el camino**: se apunta, y luego el proceso real (visado, seguro, billetes, primera noche en un país desconocido) lo abruma y no llega a subirse al avión.

Casi todo lo que se ha construido hasta ahora (jul-2026) ataca la capa 1. Este documento intenta cubrir las cuatro.

---

## 1. Descubrimiento: de "buscar" a que te encuentre

Hoy el mapa es un catálogo con filtros — mejor que un canal de WhatsApp, pero sigue siendo el joven quien tiene que ir a buscar. La versión seria de esto invierte la dirección.

- **Una sola pregunta de entrada, no un formulario**: en vez de "elige país, tipo, fechas", el chatbot pregunta *"¿qué te gustaría vivir este año?"* en lenguaje natural — "quiero desconectar del móvil", "necesito algo para mi CV de cara a Erlasmus universitario", "me da miedo volar, algo en España" — y el matching semántico (ya tenemos embeddings en Postgres/pgvector) hace el resto. Los filtros siguen ahí para quien los prefiera, pero dejan de ser la puerta de entrada.
- **Alertas que se sienten escritas a mano**: no un boletín semanal genérico, sino "esto que llegó hace 20 minutos encaja con lo que dijiste en marzo y cierra el viernes" — urgencia real, no ruido. El coste marginal de una alerta mal dirigida no es cero: es un joven que deja de confiar en las alertas.
- **Radar de última hora**: un `is_last_minute` ya existe en el dominio — llevarlo a superficie: "quedan 3 días y 2 plazas, encaja con tu perfil, ¿te lo enseño?" como una notificación distinta a las demás, con su propio tono.
- **Comparador**: poner dos o tres oportunidades lado a lado (coste real, fechas, qué cubre la beca, testimonios) es una pantalla que Skyscanner resolvió hace una década y nosotros no tenemos todavía.
- **El "simulador de vida"**: antes de apuntarte, ver cómo sería — coste de vida real de esa ciudad, clima en esas fechas, 3 fotos del lugar real (no stock), qué dice alguien que ya fue. Reduce el miedo a lo desconocido, que es la razón real por la que muchas plazas se quedan sin cubrir aunque estén bien anunciadas.

---

## 2. El bot como compañero de viaje, no como buzón de anuncios

El chatbot RAG comprometido en la propuesta puede ser un buscador con memoria, o puede ser la diferencia entre "encontré la plaza" y "llegué al aeropuerto sabiendo qué hacer". La ambición debería ser lo segundo.

- **Onboarding hablado, no rellenado**: el perfil (edad, país, intereses, disponibilidad) se construye charlando en los primeros mensajes, no en un formulario de diez campos. Cada dato que ya dijiste no se vuelve a pedir — regla de diseño, no sugerencia.
- **Acompañamiento post-inscripción**: el trabajo del bot no termina cuando alguien se apunta. Recordatorios de "tu visado debería estar en trámite ya", checklist de documentos por tipo de proyecto y país de destino, contacto de emergencia siempre a un mensaje de distancia.
- **Buddy matching**: conectar (con consentimiento explícito) a dos jóvenes que van al mismo proyecto antes de partir. El miedo a ir solo es una de las razones reales de abandono tardío — resolverlo con una intro de bot cuesta una consulta a la base de datos.
- **Modo "me acaban de aceptar y no sé qué hacer"**: un flujo específico, no un FAQ genérico, para el momento de mayor ansiedad y mayor valor (justo cuando el joven más necesita que el sistema no le falle).

---

## 3. Confianza: la variable que nadie mide y todos sienten

Con datos entrando de fuentes tan distintas (mensajes reenviados a mano, SALTO-YOUTH, comunidad), la confianza no es un "nice to have" — es lo que decide si alguien se atreve a rellenar un formulario con sus datos.

- **Verificación en capas, visible**: distinguir en la propia ficha "verificada automáticamente (SALTO-YOUTH)", "revisada por un coordinador humano", "confirmada por alguien que ya participó" — con un badge, no con letra pequeña.
- **Reseñas de quien fue, no solo de quien organiza**: después de una experiencia, un mensaje simple — "¿cómo fue?" — con opción de dejar 2 líneas y una nota. Esto es lo que Airbnb entendió antes que nadie: la confianza la construye el par, no la plataforma.
- **Detección de patrones sospechosos**: organizador nuevo + pide pago por adelantado + sin presencia en SALTO-YOUTH + urgencia artificial es una combinación que un modelo simple puede aprender a señalar antes de que un admin tenga que descubrirlo a mano.
- **Certificado digital de participación**: al final de la experiencia, un documento verificable (no necesita blockchain, necesita ser difícil de falsificar y fácil de enseñar) que sirve al joven para su CV/LinkedIn y a nosotros como dato de impacto real para el informe final del KA210 — dos problemas, una función.

---

## 4. Romper de verdad la jaula de WhatsApp

Ya sabemos —comprobado, no supuesto— que un Canal de difusión de WhatsApp no tiene API y la publicación es manual sí o sí. La respuesta seria a esa restricción no es "aceptarla", es multiplicar todas las demás bocas hasta que WhatsApp deje de ser el cuello de botella:

- **Difusión omnicanal de verdad**: Telegram automático (ya existe) + handoff a WhatsApp (ya existe) + Instagram (ya existe) + web con SEO (ya existe) + widget embebible para que los socios lo pongan en su propia web + RSS/JSON como dato abierto — cada canal nuevo no es trabajo extra si nace del mismo pipeline, es una boca más para la misma voz.
- **El "susurro"**: un deep link que abre el chat directamente con el contexto ya cargado ("te escribo por la plaza en Lisboa") — de un cartel físico, de un story de Instagram, de un mensaje reenviado por un amigo. La distancia entre "vi algo" y "puedo preguntar" debería ser un solo toque.
- **Notas de voz para quien no lee texto largo en el móvil**: parte del público objetivo no tiene el hábito (o el tiempo, o la comodidad lectora) de leer 200 palabras en una pantalla pequeña a las 23h. Una nota de audio de 20 segundos resumiendo una oportunidad es accesibilidad real, no un lujo.
- **Fallback por SMS en zonas de mal 4G**: para el segmento rural donde el smartphone con datos ilimitados no es algo que se dé por hecho, un aviso por SMS de "hay algo nuevo, entra al bot" cubre a quien la app móvil nunca alcanzaría.

---

## 5. Idioma y accesibilidad real, no solo interfaz traducida

Traducir los botones a rumano y griego (los idiomas de los socios) es el mínimo. Lo que de verdad cambia quién puede usar esto:

- **Traducir el contenido, no solo el chrome**: el resumen y la temática de cada oportunidad en el idioma nativo del usuario, con un toque para ver el original — el título del proyecto no siempre necesita traducirse, pero entender de qué va sí.
- **Modo simple para el argot**: "KA152", "ECS", "training course" son jerga que un recién llegado al ecosistema Erasmus+ no conoce. Un modo que explica en una frase qué es cada cosa la primera vez que aparece, sin que haga falta ir a buscarlo.
- **Lectura en voz alta y modo alto contraste/dislexia**: no como feature de accesibilidad aparte, sino como parte del mismo motor de notas de voz del punto anterior.

---

## 6. Comunidad: el efecto de red que todavía no existe

Hoy cada joven llega solo, mira, y se va solo. El salto de "catálogo" a "comunidad" es el que convierte a los primeros 200 usuarios beta en un crecimiento que ya no depende de que nosotros publiquemos más.

- **Mapa vivo de alumni**: dónde están ahora quienes ya hicieron un Erasmus+ con nosotros, dispuestos a responder una pregunta concreta de alguien que está pensando ir al mismo sitio. Convierte la app en algo que se visita después de haber ido, no solo antes.
- **Historias conectadas al dato**: cada "antes/después" enlazado a la ficha exacta de la oportunidad que lo originó — storytelling real con trazabilidad, útil tanto para inspirar como para el informe de impacto.
- **Grupos locales por ciudad**: encontrar a otros de tu propia ciudad que también están mirando irse — el primer paso suele ser más fácil acompañado, aunque sea solo en un grupo de chat antes de partir.

---

## 7. Para quien está al otro lado: coordinadores y organizaciones

Un marketplace tiene dos lados, y el lado de quien publica merece la misma obsesión de producto que el lado de quien busca.

- **Panel de impacto en tiempo real**: la semilla ya existe en `/estadisticas` — la versión ambiciosa es "mission control": qué se está moviendo ahora mismo, qué necesita atención, qué va a cerrar sin cubrirse si nadie hace nada.
- **Predicción antes de publicar**: con histórico suficiente, avisar a un coordinador "este tipo de proyecto en estas fechas suele tardar en llenarse, ¿quieres que lo empujemos más fuerte desde el arranque?" — convertir datos pasivos en decisiones activas.
- **Auto-relleno desde el cartel**: el coordinador sube una foto o un PDF del cartel oficial y el LLM extrae los campos — la misma extracción que ya hacemos desde texto libre, aplicada a lo que de verdad reciben las organizaciones a diario.

---

## 8. El flywheel de datos: cada interacción enseña al sistema

- **Demanda no cubierta como señal, no como pérdida**: cuando alguien busca algo que no existe ("quiero un training course de fotografía en Portugal en agosto" y no hay ninguno), eso no es un callejón sin salida — es una pieza de inteligencia de mercado que se puede compartir con LIFE y DreamTeam como socios: "esto es lo que los jóvenes están pidiendo y nadie está ofreciendo".
- **Calendario de necesidad**: el ciclo académico es predecible — quién va a necesitar qué tipo de oportunidad dentro de 2-3 meses se puede anticipar con los datos que ya tenemos, y empujar contenido relevante antes de que la propia persona sepa que lo va a buscar.
- **Catálogo federado con los socios**: LIFE (Rumanía) y DreamTeam (Grecia) tienen sus propios ecosistemas — un catálogo compartido entre los tres, con el mismo pipeline de verificación, multiplica el valor para cualquier joven sin multiplicar el trabajo de mantenimiento por tres.

---

## 9. La app móvil (ya comprometida) al nivel "esto se siente inevitable en la mano"

React Native + Expo ya está en la hoja de ruta de la propuesta. La diferencia entre una app que cumple el compromiso y una que la gente recomienda a un amigo está en el detalle:

- **Widget de pantalla de inicio**: countdown de tu plaza favorita sin abrir la app — el mismo principio que hace que la gente mire el tiempo sin pensarlo.
- **Notificación viva del último día**: no un mensaje más entre cien, sino algo que se siente distinto cuando quedan horas de verdad para una plaza que le importa a esa persona.
- **"Apunta y descubre"**: la cámara reconoce un cartel físico o un QR y trae la ficha digital al instante — el puente entre el mundo físico (donde de verdad se enteran muchos jóvenes, en el instituto, en la calle) y el catálogo digital.

---

## 10. Medir el impacto como quien enseña el trabajo, no como quien rellena un informe

- **Dashboard público de impacto**: transparencia radical, al estilo de un webcast de lanzamiento — cuántas plazas, cuántos países, cuántas vidas que de otra forma no habrían tenido esa experiencia. No solo para el informe final del KA210: para que cualquiera pueda ver que esto funciona, incluido el propio joven que todavía duda si merece la pena.
- **El resumen anual se escribe solo**: con los datos, fotos (con permiso) y testimonios ya recogidos durante el año, generar automáticamente el borrador del informe de impacto — lo que hoy es semanas de trabajo manual de cara al cierre del proyecto.

---

## 11. Moonshots — las ideas que dan un poco de vértigo

Esta sección es a propósito la más especulativa. No todo tiene que sobrevivir al primer contacto con la realidad, pero vale la pena escribirlo para no autocensurar la ambición desde el minuto uno.

- **API pública abierta**: no solo RSS/JSON como dato de difusión — una API real, documentada, con límites de uso razonables, para que cualquier desarrollador (una asociación local, un instituto, otro proyecto Erasmus+) construya sobre nuestro catálogo sin pedirnos permiso.
- **Open Badges verificables**: certificación de participación en un formato estándar reconocido (Open Badges / similar), sin necesidad de blockchain, que se pueda enseñar en un CV o LinkedIn con un clic de verificación.
- **Asistente por llamada telefónica real**: para el joven sin smartphone, sin datos, o simplemente que prefiere hablar — un número al que llamar y preguntar en voz alta "¿hay algo para mí este verano?" con el mismo motor RAG por detrás.
- **Un "Erasmus+ para toda Europa" federado**: si el modelo funciona con LIFE y DreamTeam, no hay razón técnica para que no funcione con veinte socios más — el mismo pipeline, verificado, multiplicado.

---

## 12. Principios de cómo se construye esto (la cultura, no solo la lista)

Una lista de features sin una forma de decidir entre ellas es solo una lista de deseos. Estos son los criterios con los que se prioriza:

1. **Cada fricción que se quita es una plaza que no se pierde.** Es la única métrica que de verdad importa, y toda decisión de producto se puede medir contra ella.
2. **Nunca pedir un dato dos veces.** Si el sistema ya lo sabe, no se vuelve a preguntar — regla dura, no aspiración.
3. **Nunca un formulario cuando una conversación basta.** El chatbot existe precisamente para esto: no reconstruir un formulario dentro del chat.
4. **Mejor no mostrar un botón que mostrar uno roto.** Ya es la filosofía real del código (`_clean_url`, validación defensiva) — se mantiene como principio, no como excepción puntual.
5. **Se despliega y se verifica en producción, no se da por hecho.** Cada feature de esta lista, el día que se construya, se prueba contra datos reales antes de darla por terminada.
6. **Simple primero, inteligente después.** El heatmap, el matcher de 4 preguntas, el filtro de edad — la versión sin LLM que ya aporta el 80% del valor siempre va antes que la versión con IA que aporta el último 20%.
7. **Transparencia radical con los datos de impacto.** Si el proyecto funciona, that hay que poder demostrarlo sin maquillaje — y si no funciona en algún punto, hay que poder verlo también, porque es la única forma de arreglarlo a tiempo.

---

*Este documento se revisa, no se congela. Cuando algo de aquí se construya, se mueve a [`ideas_futuras_web.md`](ideas_futuras_web.md) como "hecho" o se descarta con motivo — igual que se ha hecho ya con el resto del backlog táctico.*
