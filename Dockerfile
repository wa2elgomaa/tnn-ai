# syntax=docker/dockerfile:1
# Base: small, stable, OpenMP (libgomp1) for faiss/torch wheels
FROM python:3.11-slim

# ---- System deps ----
# libgomp1: needed by faiss-cpu & some torch wheels
# curl: optional (health checks / debugging)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 curl && \
    rm -rf /var/lib/apt/lists/*


# ---- App setup ----
WORKDIR /app

# (Optional) If you have a separate constraints.txt, copy it first to improve caching
# COPY constraints.txt ./constraints.txt

# Install Python deps
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt
    # If you use constraints:
    # pip install --no-cache-dir -r requirements.txt -c constraints.txt

# Copy app code (adjust paths if your layout differs)
COPY app ./app
COPY data ./app/data
COPY .env ./app/.env
CMD ls ./app
# ENV PYTHONPATH=/app

# ---- Security: run as non-root ----
# RUN useradd -m appuser && chown -R appuser:appuser /app /opt/render
# USER appuser

EXPOSE 8000

# ---- Start command ----
# Tip: On Render, you can override the Start Command in the dashboard to:
#   python -m app.bootstrap && uvicorn app.main:app --host 0.0.0.0 --port $PORT
# if you add a bootstrap that snapshots models to the persistent disk.
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--log-level","debug"]