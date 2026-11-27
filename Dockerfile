FROM python:3.14-slim
LABEL org.opencontainers.image.source=https://github.com/romanzdk/fyzio-cviky
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/venv PATH="/venv/bin:$PATH" PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN DJANGO_DEBUG=0 DJANGO_SECRET_KEY=build VAPID_SUBJECT=mailto:build@example.com python manage.py collectstatic --noinput -v0
RUN useradd --create-home app
USER app
EXPOSE 8000
ENV WEB_CONCURRENCY=2 DJANGO_DEBUG=0
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi -b 0.0.0.0:8000 --timeout 60"]
