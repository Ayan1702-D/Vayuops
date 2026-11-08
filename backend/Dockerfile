FROM python:3.11-slim AS builder

WORKDIR /build
RUN python -m venv /opt/venv
COPY pyproject.toml ./
COPY app ./app
RUN /opt/venv/bin/python -m pip install --no-cache-dir .

FROM python:3.11-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 vayuops

WORKDIR /srv/vayuops
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/app ./app

USER vayuops
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c 'import os, urllib.request; urllib.request.urlopen("http://127.0.0.1:" + os.environ["PORT"] + "/health", timeout=4).close()'
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\""]
