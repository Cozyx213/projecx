# ProjectX — Django vertical slicing + Supabase

A student project workspace with Login, Register, Home, Projects, Similarity
Checks, Profile, and Settings.
The layout follows `CSIT327_Python_Django_Vertical_Slicing_and_Supabase_Guide.pdf`.
Django handles authentication and migrations; Supabase PostgreSQL stores the data.

The approved six-table ERD is now mapped in `apps/home/models.py`, using Django's
existing `auth_user` for accounts. See [the ERD laboratory submission notes](docs/erd-lab.md)
for the mapping, migration, verification, and required Supabase screenshot.

## Structure

```text
apps/
  login/             # Django login/logout views and routes
  register/          # Account creation and validation
  home/              # ERD models, project draft form, views, migrations, tests
  projects/          # Project list, full proposal form, version history, status actions
  explore/           # Public project gallery with category filtering, search, and detail view
  similarity/        # Similarity engine, OpenAI LLM analysis, check runs, results, and history
  profile/           # Full name and bio, form, view, migration, tests
  user_settings/     # Display preferences, form, view, migration, tests
templates/
  base.html          # Shared navigation and layout
  login/login.html
  register/register.html
  home/home.html
  projects/          # projects.html, form.html, detail.html
  similarity/        # checks.html, detail.html
  profile/profile.html
  user_settings/settings.html
static/
  css/               # login/, register/, home/, profile/, user_settings/, shared/
  js/                # login/, register/, home/, profile/, user_settings/
  images/            # login/, register/, home/, profile/, user_settings/
config/              # Settings, root URLs, WSGI, ASGI, database verification
.env.example         # Configuration template without credentials
manage.py
requirements.txt
```

Each feature owns its models, validation, views, URLs, templates, CSS, JavaScript,
and images. Only the layout and common styling are shared. A context processor
owned by Settings supplies saved preferences to the layout; feature views do
not import each other. URL names are namespaced, such as `profile:profile`.

## Setup and run

Requires Python 3.10 or newer and a Supabase PostgreSQL project.

```sh
python -m venv .venv
```

Activate on Windows: `.venv\Scripts\activate`.
Activate on macOS/Linux: `source .venv/bin/activate`.

```sh
python -m pip install -r requirements.txt
```

1. Copy `.env.example` to `.env` if `.env` does not already exist.
2. In **Supabase → Connect**, copy the PostgreSQL connection URI into
   `DATABASE_URL`. Use the exact host, port, and username supplied by Supabase.
   The Session pooler on port 5432 is suitable for an IPv4-only network; a direct
   connection works where supported. URL-encode special characters in the password.
3. Set `DJANGO_SECRET_KEY` to the output of
   `python -c "import secrets; print(secrets.token_urlsafe(50))"`.
4. Keep `DJANGO_DEBUG=True` for the local classroom server.

The database is PostgreSQL only. Missing or invalid configuration fails explicitly.
`.env` is ignored by Git and must be excluded from submissions. The connection
requires TLS. No Supabase Auth SDK or API key is needed.

```sh
python manage.py check --database default
python manage.py makemigrations
python manage.py migrate
python -m config.verify_database
python manage.py runserver
```

Open http://127.0.0.1:8000/. Create an account at `/register/`, then log in at
`/login/`. Home, Profile, and Settings require login. Logout uses a CSRF-protected
POST. To access the optional Django admin at `/admin/`, create your own admin:

```sh
python manage.py createsuperuser
```

## Features to demonstrate

1. Register and log in. Invalid passwords and duplicate usernames display errors.
2. On **Home**, save a title, problem statement, and intended audience. Reload to
   confirm the draft persists. Saving again creates a new version of the same project.
3. On **Profile**, save a full name and bio. Reload to confirm the values persist.
4. On **Settings**, preview and save dark mode. It applies across the workspace.
   Turn project prompts off, save, and check that the prompt panel disappears on Home.
5. On **Projects**, create a project with the full proposal form. Each save adds a
   version; the project page lists every version and the sections that changed.
   Submit, publish, archive, and restore the project from its Status panel.
6. On **Checks**, run a similarity check. The latest version is compared with your
   other projects and with projects other accounts made public. Results show a
   score, the reason for each match, and recommendations.
7. Log out and verify private pages redirect to Login. Another account has its own
   draft, profile, and preferences.

Password visibility controls, live character counts, and the theme preview use
the feature JavaScript files. Forms also work without JavaScript. The SVG images
are local assets. Profile uses a default avatar; image uploads are not implemented.

## How similarity is scored

When `OPENAI_API_KEY` is configured in `.env`, `apps/similarity/llm.py` uses OpenAI
text embeddings (`text-embedding-3-small`) to shortlist semantically related proposals
and an OpenAI chat model (`gpt-6-luna`) to score conceptual overlap (0–100%), write
specific explanations for each match, and generate tailored recommendations.

If `OPENAI_API_KEY` is unset or the API is unavailable, `apps/similarity/engine.py`
automatically runs as a pure-Python fallback. It removes common words, reduces words
to a rough root, and measures cosine similarity of word counts (averaging whole-proposal
similarity with a weighted section average where problem statement and proposed solution
weigh the most). Matches below 10% are dropped and the five highest are stored. Scores
of 70% and above are labelled high, 40% and above moderate. Private and archived
projects of other accounts are never compared.

## Tests and database verification

```sh
python manage.py check --database default
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py showmigrations
python -m config.verify_database
python manage.py collectstatic --noinput
```

Django tests use a separate PostgreSQL database named `test_projectx`, which the
test runner creates and removes. Use a database role with `CREATEDB` permission.
The tests cover authentication, validation, saving and updating data, account
isolation, CSRF protection, escaped profile content, and asset discovery.
`config.verify_database` checks TLS, migration status, and the six ERD tables'
columns, types, nullability, keys, constraints, and row counts without modifying data.

## Supabase Table Editor and screenshots

After using the forms, open **Supabase → your project → Table Editor → public**.
Inspect these tables:

| Table | Data created by the app |
| --- | --- |
| `auth_user` | Registered accounts |
| `projects` | Project owner, status, visibility, and creation time |
| `project_versions` | Saved title, problem, audience, and other proposal sections per version |
| `similarity_checks` | Similarity check status and the version being checked |
| `similarity_matches` | Matched versions, scores, and explanations |
| `recommendations` | Suggestions associated with a similarity check |
| `profile_profile` | Saved full name, bio, and user ID |
| `user_settings_usersettings` | Saved dark mode, project prompts, and user ID |
| `django_session` | Django login sessions |

Match `projects.user_id` to `auth_user.id` and `project_versions.project_id` to
`projects.id`. Refresh after saving a form. Migrations create tables; submitting
the forms creates profile, preferences, project, and version rows. Running a
check on the Checks page creates the `similarity_checks`, `similarity_matches`,
and `recommendations` rows. The ERD laboratory requires evidence
of tables and relationships; the earlier application demonstration also required
saved form data.

Capture Home, Login, Register, Profile, Settings, and the Supabase Table Editor
showing real rows. Include the project tree if possible. Keep password hashes and
session contents out of screenshots. Include source and migration files in your
submission; exclude `.env`, virtual environments, caches, and database backups.

Connection reference: [Supabase PostgreSQL connections](https://supabase.com/docs/guides/database/connecting-to-postgres).
Driver reference: [Django 5.2 PostgreSQL support](https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes).
