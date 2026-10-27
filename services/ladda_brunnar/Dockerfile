# Engångsjobbet som laddar de 91 bräddbrunnarna i orion-stad.
# Basimage låses via .env (hård regel 4) och skickas in som build-arg.
ARG PYTHON_IMAGE=python:3.12.15-slim
FROM ${PYTHON_IMAGE}

# Säkerhetsrättning: rätta perl-base m.fl. i basbilden (Trivy-kritiska).
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Inga pip-beroenden: gpkg läses med stdlib:ets sqlite3 + struct.
WORKDIR /app
COPY ladda_brunnar.py /app/ladda_brunnar.py

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "/app/ladda_brunnar.py"]
