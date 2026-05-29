#!/usr/bin/env bash
set -o errexit

python manage.py migrate --noinput
python scripts/apply_sql_recipe.py deploy/render_seed_super_admin.sql

exec gunicorn vortexforge.wsgi:application --bind 0.0.0.0:${PORT:-8000}
