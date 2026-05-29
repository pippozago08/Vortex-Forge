#!/usr/bin/env python
import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vortexforge.settings")

    import django
    from django.db import connection

    django.setup()

    recipe_path = Path(sys.argv[1] if len(sys.argv) > 1 else "deploy/render_seed_super_admin.sql")
    if not recipe_path.is_absolute():
        recipe_path = BASE_DIR / recipe_path
    if not recipe_path.exists():
        raise SystemExit(f"SQL recipe not found: {recipe_path}")

    if connection.vendor != "postgresql":
        print(f"Skipping SQL recipe on non-PostgreSQL database: {connection.vendor}")
        return

    sql = recipe_path.read_text(encoding="utf-8")
    with connection.cursor() as cursor:
        cursor.execute(sql)

    print(f"Applied SQL recipe: {recipe_path}")


if __name__ == "__main__":
    main()
