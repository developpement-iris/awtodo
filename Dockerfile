# Image unique : Django sert l'API et le build Vite (WhiteNoise + config/spa.py),
# comme le service Render actuel. Base de données externe (DATABASE_URL).

# --- 1. Build du frontend ---------------------------------------------
FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build

# --- 2. Image finale Django -------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.staging \
    PORT=8080

# libpq : requis par psycopg 3 (installé sans l'extra [binary])
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/staging.txt

COPY . .
COPY --from=frontend /app/frontend/dist frontend/dist

# collectstatic ne touche pas la base : variables factices, au build seulement
RUN DJANGO_SECRET_KEY=build DJANGO_ALLOWED_HOSTS=localhost \
    DATABASE_URL=postgres://u:p@localhost:5432/db \
    python manage.py collectstatic --no-input

RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8080

# Le démarrage ne touche jamais au schéma ni aux comptes : chaque redémarrage
# de la plateforme rejouerait sinon ces commandes sur la base de production.
# Migrations et bootstrap_admin se lancent à la main, au moment voulu.
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 60"]
