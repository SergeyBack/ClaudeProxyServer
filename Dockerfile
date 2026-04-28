FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.4

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --without dev

COPY . .

ENV WORKERS=4

CMD ["sh", "-c", "uvicorn src.main:app \
     --host 0.0.0.0 \
     --port 8000 \
     --workers ${WORKERS} \
     --loop uvloop \
     --http httptools \
     --timeout-graceful-shutdown 30"]
