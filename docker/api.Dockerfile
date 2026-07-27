FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
# fonts-dejavu-core: la imagen slim no trae ninguna fuente, y los endpoints /ig/{id}/*.png
# (Pillow, vía instagram_card.py) necesitan un .ttf real — sin esto cae al bitmap por
# defecto de Pillow, que no tiene glifos para tildes (Í, Á...) y salen como "tofu".
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
# app/api/static/ lleva la página del mapa (se sirve en GET /mapa)

EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
