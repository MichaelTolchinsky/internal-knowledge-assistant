FROM python:3.14-slim

WORKDIR /app

# System deps needed to build psycopg[binary]'s optional native extras / future ML deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "knowledge_assistant.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
