# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.9.*
WORKDIR /srv
COPY backend/requirements.lock .
RUN uv venv /opt/venv && uv pip install --python /opt/venv/bin/python -r requirements.lock

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-freefont-ttf postgresql-client \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --home /srv appuser
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MEDIA_ROOT=/srv/var/media
WORKDIR /srv/backend
COPY backend/ /srv/backend/
COPY evals/ /srv/evals/
COPY infra/postgres/post-migrate-grants.sql /srv/infra/postgres/post-migrate-grants.sql
RUN mkdir -p /srv/var/media && chown -R appuser /srv/var
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=4).status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "::", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--workers", "2"]
