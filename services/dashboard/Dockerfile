# dashboard – kontrollrummet (komponent 14).
#
# BYGGKONTEXT: ./services – paketet gemensam/ (delade hjälpfunktioner)
# kopieras in i imagen. Katalogvalidering med SHACL ingår inte i Svada-mini.
#
# Basimage och beroendeversioner kommer som build-args ur .env (hård regel 4).
ARG PYTHON_IMAGE=python:3.12.15-slim
FROM ${PYTHON_IMAGE}

# Säkerhetsrättning: rätta perl-base m.fl. i basbilden (Trivy-kritiska).
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ARG FASTAPI_VERSION
ARG UVICORN_VERSION

# fastapi/uvicorn = vyn och API:t.
# INGET requests: alla anrop görs med urllib ur standardbiblioteket
# (kallor.py) – kontrollrummet ska vara billigt att köra.
RUN pip install --no-cache-dir \
      "fastapi==${FASTAPI_VERSION}" \
      "uvicorn==${UVICORN_VERSION}"

WORKDIR /app
COPY gemensam/ ./gemensam/
COPY dashboard/kallor.py dashboard/steg.py dashboard/kedjan.py dashboard/i18n.py dashboard/meddelanden.py \
     dashboard/audit.py dashboard/analys.py dashboard/jobb.py \
     dashboard/vy.py dashboard/main.py dashboard/skydd.py dashboard/statistiksida.py dashboard/sessioner.py dashboard/nyheter.py ./
COPY dashboard/statiskt/ ./statiskt/

ENV PYTHONUNBUFFERED=1
EXPOSE 8800

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8800", \
     "--log-level", "warning"]
