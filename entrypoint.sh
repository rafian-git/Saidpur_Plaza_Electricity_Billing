#!/bin/sh
set -e

# Import the SQL dump into database.db on first start only
if [ ! -f database.db ]; then
    echo "[entrypoint] database.db not found, importing from database.db.sql..."
    python import_sql.py
else
    echo "[entrypoint] database.db already exists, skipping SQL import."
fi

exec /var/www/Saidpur_Plaza_Electricity_Billing/.venv/bin/python app.py
