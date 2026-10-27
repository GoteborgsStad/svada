# stad-gateway – åtkomstkontroll framför stadens CIP (åtgärd av gapanalysens
# G22). Samma mönster som ingest-service och publik-vy: bara fastapi/uvicorn,
# proxyanropen mot orion-stad görs med urllib ur standardbiblioteket.
# Basimage och versioner kommer som build-args ur .env (hård regel 4: inga
# rörliga taggar).
ARG PYTHON_IMAGE=python:3.12.15-slim
FROM ${PYTHON_IMAGE}

# Säkerhetsrättning: rätta perl-base m.fl. i basbilden (Trivy-kritiska).
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ARG FASTAPI_VERSION
ARG UVICORN_VERSION

RUN pip install --no-cache-dir \
      "fastapi==${FASTAPI_VERSION}" \
      "uvicorn==${UVICORN_VERSION}"

WORKDIR /app
COPY atkomst.py vy.py main.py ./

ENV PYTHONUNBUFFERED=1
EXPOSE 8086

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8086", \
     "--log-level", "warning"]
