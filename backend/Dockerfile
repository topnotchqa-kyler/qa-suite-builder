FROM python:3.12-slim-bookworm

# Install system dependencies for Playwright/Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium
RUN python -m playwright install chromium --with-deps

# Copy application code
COPY . .

# Expose port (Railway uses $PORT env var)
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
