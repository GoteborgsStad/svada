# fcf-sim – "Future City Flow" (komponent 5).
# Basimage och beroendeversioner kommer som build-args ur .env (hård regel 4:
# inga rörliga taggar).
ARG PYTHON_IMAGE=python:3.12.15-slim
FROM ${PYTHON_IMAGE}

# Säkerhetsrättning: rätta perl-base m.fl. i basbilden (Trivy-kritiska).
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ARG FASTAPI_VERSION
ARG UVICORN_VERSION

# Endast FastAPI + uvicorn. gpkg-läsningen använder sqlite3/struct och
# Orion-läsningen urllib – båda i standardbiblioteket, inget GDAL behövs.
RUN pip install --no-cache-dir \
      "fastapi==${FASTAPI_VERSION}" \
      "uvicorn==${UVICORN_VERSION}"

WORKDIR /app
COPY brunnar.py matvarden.py modell.py distributioner.py main.py ./

ENV PYTHONUNBUFFERED=1
EXPOSE 8050

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8050", \
     "--log-level", "info"]
