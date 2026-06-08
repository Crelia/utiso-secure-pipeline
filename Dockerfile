# Pin the base by tag here for readability; the pipeline + Dependabot keep it
# current, and you'd pin by sha256 digest in production (see README "Looking ahead").
FROM python:3.12-slim AS build

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# Install runtime deps into an isolated prefix we can copy into the final stage.
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ---- Final stage: no build tooling, no pip, runs as an unprivileged user ----
FROM python:3.12-slim AS runtime

# Drop privileges: create a dedicated non-root user.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app
COPY --from=build /install /usr/local
COPY app ./app

ENV APP_VERSION=0.1.0 PYTHONUNBUFFERED=1
EXPOSE 8000
USER appuser

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
