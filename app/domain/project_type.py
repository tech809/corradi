from enum import Enum


class ProjectType(str, Enum):
    # Solo estos 3 formatos — los workshops se descartan explícitamente en la extracción
    # (ver EXTRACTION_PROMPT en app/llm/prompts.py), a petición expresa: nunca ha entrado
    # ninguno hasta ahora y no se quieren en el mapa.
    YOUTH_EXCHANGE = "YOUTH_EXCHANGE"
    TRAINING_COURSE = "TRAINING_COURSE"
    VOLUNTEERING = "VOLUNTEERING"


class ProjectStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"
