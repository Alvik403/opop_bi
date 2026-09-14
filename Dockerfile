FROM node:24-slim@sha256:2fe369e969550cde8e867afc3fe370b260140cab4a23d467074295b42163d553 AS frontend

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY assets ./assets
COPY templates ./templates
COPY tailwind.config.js vite.config.js ./
RUN npm run build

FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home /app app

COPY requirements.lock .
RUN pip install --require-hashes --no-cache-dir -r requirements.lock

COPY --chown=app:app . .
COPY --chown=app:app --from=frontend /app/static/dist ./static/dist

RUN mkdir -p /app/data /app/uploads /app/runtime /app/logs \
    && chown -R app:app /app

EXPOSE 8000

USER 10001:10001

CMD ["python", "app.py"]
