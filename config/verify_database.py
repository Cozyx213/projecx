"""Run with: python -m config.verify_database (reads data; never creates test rows)."""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def main():
    connection.ensure_connection()
    if connection.vendor != "postgresql":
        raise SystemExit("Expected PostgreSQL.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user")
        database, user = cursor.fetchone()
        cursor.execute("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
        database_tls = cursor.fetchone()[0]
    client_tls = connection.connection.pgconn.ssl_in_use
    print(
        f"PostgreSQL database: {database}; user: {user}; "
        f"Django-to-Supabase TLS: {client_tls}; pooler-to-Postgres TLS: {database_tls}"
    )
    if not client_tls:
        raise SystemExit("Expected Django's database connection to use TLS.")
    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise SystemExit("Unapplied migrations. Run python manage.py migrate.")
    print("All migrations are applied.")
    for label in (
        "auth.User", "home.Project", "home.ProjectVersion", "home.SimilarityCheck",
        "home.SimilarityMatch", "home.Recommendation",
    ):
        model = apps.get_model(label)
        table = model._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT attname, format_type(atttypid, atttypmod), attnotnull
                   FROM pg_attribute
                   WHERE attrelid = to_regclass(%s)
                     AND attnum > 0 AND NOT attisdropped""",
                [f"public.{table}"],
            )
            columns = {name: (kind, not required) for name, kind, required in cursor.fetchall()}
            expected = {
                field.column: (
                    field.db_type(connection)
                    .replace("varchar(", "character varying(")
                    .replace(", ", ","),
                    field.null,
                )
                for field in model._meta.local_fields
            }
            if columns != expected:
                raise SystemExit(f"Column/type/nullability mismatch in {table}: {columns}")
            constraints = connection.introspection.get_constraints(cursor, table)
        for field in model._meta.local_fields:
            if field.primary_key and not any(
                item["primary_key"] and item["columns"] == [field.column]
                for item in constraints.values()
            ):
                raise SystemExit(f"Missing primary key: {table}.{field.column}")
            if field.unique and not field.primary_key and not any(
                item["unique"] and item["columns"] == [field.column]
                for item in constraints.values()
            ):
                raise SystemExit(f"Missing unique constraint: {table}.{field.column}")
            if field.many_to_one:
                target = (field.related_model._meta.db_table, field.target_field.column)
                if not any(
                    item["columns"] == [field.column] and item["foreign_key"] == target
                    for item in constraints.values()
                ):
                    raise SystemExit(f"Missing foreign key: {table}.{field.column}")
        for constraint in model._meta.constraints:
            if constraint.name not in constraints:
                raise SystemExit(f"Missing constraint: {constraint.name}")
        print(f"{table}: {model.objects.count()} row(s); columns, keys and constraints verified")
    connection.close()


if __name__ == "__main__":
    main()
