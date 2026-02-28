FROM python:3.12-slim

WORKDIR /app

# Install system deps if needed (e.g. for matplotlib)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src ./src

RUN pip install --no-cache-dir -e '.[dev]'

VOLUME ["/app/runs", "/app/benchmarks"]

CMD ["make", "bench-all"]