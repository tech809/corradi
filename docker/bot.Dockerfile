FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
# fonts-dejavu-core: la imagen slim no trae ninguna fuente, y opportunity_card.py (Pillow,
# usado por pipeline.commit() para el banner del post) necesita un .ttf real.
# ffmpeg: codifica los Reels de Instagram (fotogramas de reel_video.py + audio generado de
# reel_audio.py -> mp4), ver app/publisher/reel_video.py.
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run_bot.py .

CMD ["python", "run_bot.py"]
