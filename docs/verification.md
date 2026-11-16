# Verification — September 14, 2026

The application uses Supabase PostgreSQL only.

| Check | Result |
| --- | --- |
| `python manage.py check --database default` | No issues |
| `python manage.py makemigrations` | Initial Home, Profile, and Settings migrations created |
| `python manage.py migrate` | All migrations applied to Supabase |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py test --noinput` | 7 tests passed in 86.700 seconds on PostgreSQL |
| Test isolation | Separate `test_projectx` database created and removed |
| `python manage.py collectstatic --noinput` | 143 static files collected, including Django admin assets |
| Database connection | PostgreSQL, TLS 1.3 |
| Desktop and mobile browser checks | All five screens passed; mobile width 375px |
| Asset checks | CSS and images loaded; no JavaScript errors |

Browser checks registered/logged in the `projectx_student` demonstration account,
saved its project draft and profile, reloaded both to verify persistence, saved
dark mode and project prompt preferences, and checked their effect on Home.
The checks also exercised password visibility, live character counts, logout,
and redirects protecting private pages.

Database verification after the browser run returned:

```text
PostgreSQL database: postgres; user: postgres; TLS: True
All migrations are applied.
auth_user: 2 row(s)
home_projectdraft: 1 row(s)
profile_profile: 1 row(s)
user_settings_usersettings: 1 row(s)
```

Counts can increase when more accounts use the app. Recheck with
`python -m config.verify_database`. The persisted demo draft is
**Campus study space finder**, and the profile's full name is **ProjectX Student**.

Screenshots are in `artifacts/screenshots/`: Login, Register, Home, Profile,
Settings, mobile variants, and dark mode variants. Demo login details are in
the ignored `artifacts/demo-account.json`; that file is excluded from submission.

Opening the Supabase Table Editor was requested in the desktop browser, but its
contents could not be visually confirmed. Signed-in confirmation and the Table
Editor screenshot are still pending; SQL verification above is complete and is
not a substitute for the guide's required dashboard screenshot.
