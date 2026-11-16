# Approved ERD laboratory submission

Source: `/home/jake/Downloads/BAJENTING_ERD 1.pdf` (two pages showing the same ERD).
This six-table diagram is the authority for this activity, including revision
history. The later suggestion to simplify the proposal does not replace it.

## Submission file and entity mapping

Submit [`apps/home/models.py`](../apps/home/models.py) as `models.py`.

| ERD table | Django model |
| --- | --- |
| `auth_user` | Built-in `django.contrib.auth.models.User` |
| `projects` | `Project` |
| `project_versions` | `ProjectVersion` |
| `similarity_checks` | `SimilarityCheck` |
| `similarity_matches` | `SimilarityMatch` |
| `recommendations` | `Recommendation` |

`auth_user` already exists through `django.contrib.auth` and its migrations.
It provides exactly the diagram's account columns: `id`, `username`, `password`,
`first_name`, `last_name`, `email`, `is_active`, `is_staff`, `is_superuser`,
`last_login`, and `date_joined`. Its password column stores password hashes.
It must not be recreated as a second model in this app.

The five application models explicitly set `db_table` to the diagram's names.
Django adds `_id` to each foreign-key column. The six relationships are:

1. `projects.user_id` → `auth_user.id`
2. `project_versions.project_id` → `projects.id`
3. `similarity_checks.project_version_id` → `project_versions.id`
4. `similarity_matches.similarity_check_id` → `similarity_checks.id`
5. `similarity_matches.matched_version_id` → `project_versions.id`
6. `recommendations.similarity_check_id` → `similarity_checks.id`

All are many-to-one foreign keys. Application IDs use `BigAutoField` (`bigint`);
the built-in user ID and its foreign key use `integer`. Score precision is
`numeric(5,2)`. PostgreSQL timestamps use `timestamp with time zone`, equivalent
to `timestamptz`. Optional fields in the PDF use `null=True, blank=True`.
The status, positive-version, score-range, and composite uniqueness constraints
from the original DBML are also enforced in the database.

## Migration

The generated migration is `apps/home/migrations/0002_approved_erd.py`.
It creates the five ERD tables, copies every old `home_projectdraft` row into a
project and version 1, then removes the old draft table in the same transaction.
Titles, problems, audiences, account ownership, and the last-save timestamp are
preserved. It deliberately has no reverse data operation: multiple project
versions cannot be restored losslessly into one old draft per user.
Existing profile/settings and Django framework tables remain in place.

The migration has been applied to the configured Supabase project. To recheck it
from the project root, run:

```sh
.venv/bin/python manage.py migrate --plan
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py showmigrations home
.venv/bin/python -m config.verify_database
```

The last command reads the live PostgreSQL catalog and checks all six tables'
column names, types, nullability, primary keys, foreign keys, unique constraints,
and named checks against the models. It also verifies TLS on Django's connection
to Supabase; `pg_stat_ssl` alone reports the separate pooler-to-PostgreSQL link.
It does not create sample data.

## Verification status — September 28, 2026

- Django system checks: passed.
- Migration/model drift check: no changes detected.
- All nine tests passed using an isolated in-memory SQLite test database,
  including migration execution, draft-data preservation, revision saving,
  account isolation, relationship traversal, and invalid-row rejection.
- PostgreSQL model metadata was compared with the PDF: six tables, 43 columns,
  and six foreign keys match the diagram's structure.
- Supabase migration: applied using the supplied IPv4 Session pooler.
- Live verification: all six model tables and their columns, types, nullability,
  primary keys, foreign keys, unique constraints, and named checks passed.
- TLS: Django-to-Supabase connection verified as encrypted. The verifier also
  reports the separate pooler-to-PostgreSQL connection.
- Supabase dashboard screenshot: pending.

## Required screenshot

After migration, open the actual Supabase project and show the `public` schema
in its database schema visualizer. Arrange the six ERD tables so their columns
and all six relationship lines are readable, then capture that view. If needed,
include a second screenshot to keep the text legible.

Save the capture as `artifacts/screenshots/supabase-approved-erd.png` and submit
it with `models.py`. A screenshot of dbdiagram.io or a locally generated diagram
does not demonstrate that the tables exist in Supabase. The old September 14
screenshots do not show this migration.

This task maps and migrates the schema. It does not implement the similarity
algorithm or generate recommendation content. The existing home form saves
versions through the new schema; those additional features can use the models
later.
