# SAMD_QMS application image: the same image runs the web app, the scheduler and one-off
# management commands, in development and production.
#
#   docker build --build-arg QMS_VERSION=1.0.0 --build-arg QMS_COMMIT=$(git rev-parse HEAD) \
#     -t samd_qms:1.0.0 .

ARG PYTHON_VERSION=3.13

# --- build stage: compile wheels so the runtime image needs no compilers ------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# --- runtime stage ---------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime
ARG QMS_VERSION=dev
# Full git commit the image was built from; shown at the top of every page and on /healthz.
ARG QMS_COMMIT=""
LABEL org.opencontainers.image.title="SAMD_QMS" \
      org.opencontainers.image.description="Quality management system for software medical devices" \
      org.opencontainers.image.version="${QMS_VERSION}" \
      org.opencontainers.image.revision="${QMS_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    QMS_VERSION=${QMS_VERSION} \
    QMS_COMMIT=${QMS_COMMIT} \
    DJANGO_MEDIA_ROOT=/data/media \
    DJANGO_STATIC_ROOT=/app/staticfiles \
    BACKUP_DIR=/backups

# postgresql-client: pg_dump / pg_restore for the backup and restore scripts.
# curl: container health checks.
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client curl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 qms \
 && useradd --system --uid 10001 --gid qms --home /app --shell /usr/sbin/nologin qms

COPY --from=build /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/* && rm -rf /wheels

WORKDIR /app
COPY --chown=qms:qms . /app

# Static files are collected at build time and served by WhiteNoise.
RUN DJANGO_SECRET_KEY=build-only DJANGO_DEBUG=0 DATABASE_URL=sqlite:////tmp/build.db \
    python manage.py collectstatic --noinput \
 && mkdir -p /data/media /backups \
 && chown -R qms:qms /data /backups /app/staticfiles \
 && chmod +x /app/deploy/scripts/*.sh

USER qms
EXPOSE 8000
VOLUME ["/data/media", "/backups"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

ENTRYPOINT ["/app/deploy/scripts/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "-c", "/app/deploy/gunicorn.conf.py"]
