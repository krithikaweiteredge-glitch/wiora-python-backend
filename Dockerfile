# Wiora backend — container image for cloud deploy (Render / Railway / any host).
# The FastAPI app binds to $PORT, which the host injects at runtime.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code.
COPY app ./app

# Local docker default; the host overrides $PORT (Render/Railway set it).
ENV PORT=4000
EXPOSE 4000

# Shell form so ${PORT} expands at runtime.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-4000}
