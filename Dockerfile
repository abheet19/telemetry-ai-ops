FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy .env file
COPY .env /app/.env

# Ensure .env is readable
RUN chmod 644 /app/.env

# ---------- Test Stage ----------
FROM base AS test

# Run unit tests with Pytest
RUN pytest -v --disable-warnings || (echo "Tests failed!" && exit 1)

# ---------- Production Stage ----------
FROM base AS prod

EXPOSE 8000

# Set environment variable for safety fallback
ENV OPENAI_API_KEY=${OPENAI_API_KEY:-mock_key}

# Run the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]