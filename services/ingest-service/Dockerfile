# ingest-service – stadens mottagning av EDC-transfern (komponent 8).
# Basimage och beroendeversioner kommer som build-args ur .env (hård regel 4:
# inga rörliga taggar). Samma mönster som fcf-sim.
ARG PYTHON_IMAGE=python:3.12.15-slim
FROM ${PYTHON_IMAGE}

# Säkerhetsrättning: rätta perl-base m.fl. i basbilden (Trivy-kritiska).
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ARG FASTAPI_VERSION
ARG UVICORN_VERSION

# Endast FastAPI + uvicorn. Anropen mot orion-stad och stadens EDC görs med
# urllib ur standardbiblioteket – inga fler beroenden behövs.
RUN pip install --no-cache-dir \
      "fastapi==${FASTAPI_VERSION}" \
      "uvicorn==${UVICORN_VERSION}"

WORKDIR /app
COPY auktorisation.py avtalsregister.py validering.py ngsild.py main.py ./

ENV PYTHONUNBUFFERED=1
EXPOSE 8060

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8060", \
     "--log-level", "info"]
