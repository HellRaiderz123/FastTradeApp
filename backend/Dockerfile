FROM python:3.11-slim

WORKDIR /app

# Install system deps needed by some Python packages (lightgbm, psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create data directory for SQLite persistence
RUN mkdir -p /data

# Default DB path inside container (overridable via env)
ENV DATABASE_URL=sqlite:////data/trading.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
