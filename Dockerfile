# Drift — visor SPHEREx. Imagen para despliegue público (Render, Fly.io, Railway, etc.)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CACHE_DIR=/data/cache \
    PORT=8000

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY frontend frontend

RUN mkdir -p /data/cache
EXPOSE 8000
# Un solo proceso (el progreso de descarga vive en memoria); las peticiones van en hilos
# y las descargas a IRSA ya se hacen en paralelo dentro de cada petición.
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT} --timeout-keep-alive 300"]
