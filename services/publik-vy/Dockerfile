# publik-vy – stadens publika representation av Distribution B (åtgärd av gapanalysens G9).
#
# Inga andra beroenden än fastapi/uvicorn: Mintaka nås med urllib ur
# standardbiblioteket. Basimage och versioner kommer som build-args ur .env
# (hård regel 4: inga rörliga taggar).
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
COPY vy.py main.py aterstall.py ./

ENV PYTHONUNBUFFERED=1
EXPOSE 8085

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8085", \
     "--log-level", "warning"]
