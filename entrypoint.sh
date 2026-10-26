#!/bin/sh
set -e

echo "=========================================================="
echo " Starting QuantumDBA Multi-Database Management Platform"
echo "=========================================================="

# 1. Wait for database connectivity if configured
if [ -n "$DATABASE_URL" ] || [ -n "$POSTGRES_HOST" ]; then
    echo "==> Verifying PostgreSQL database readiness..."
    python - <<'EOF'
import os
import sys
import time
import psycopg2
from models import get_database_uri

db_url = get_database_uri()

max_retries = 35
for attempt in range(1, max_retries + 1):
    try:
        conn = psycopg2.connect(db_url, connect_timeout=3)
        conn.close()
        print("==> Database connection established successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"--> Waiting for database at '{db_url.split('@')[-1]}' to accept connections... ({attempt}/{max_retries})")
        time.sleep(1)

print("ERROR: Database connection timeout. Could not reach PostgreSQL.")
sys.exit(1)
EOF
fi

# 2. Initialize application database schema and seed default Super Admin
echo "==> Synchronizing tables and default credentials..."
python init_db.py

# 3. Start web application server
if [ "$FLASK_ENV" = "development" ]; then
    echo "==> Running in DEVELOPMENT mode on 0.0.0.0:5001..."
    exec python app.py
else
    echo "==> Running in PRODUCTION mode with Gunicorn WSGI on 0.0.0.0:5001 (4 workers)..."
    exec gunicorn \
        --bind 0.0.0.0:5001 \
        --workers 4 \
        --threads 2 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile - \
        app:app
fi
