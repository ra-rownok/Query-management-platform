# Multi-Database Query Management Platform (QuantumDBA)
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1 \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5001

# Install system dependencies for database drivers and container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first (leveraging Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure entrypoint script has executable permissions
RUN chmod +x entrypoint.sh

# Expose web application port
EXPOSE 5001

# Container healthcheck verifying HTTP responsiveness
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:5001/login || exit 1

# Launch container via entrypoint
ENTRYPOINT ["./entrypoint.sh"]
