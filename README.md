# clinic-appointment-service
Online appointment management system that allows patients to register, browse doctors and available time slots, book appointments, cancel or complete visits. Payments are processed via Stripe. Staff receive Telegram notifications about new bookings, cancellations, no-shows, and successful payments.

## Contributing rules

- **Never commit or push directly to `main`.**
- Create your own branch from an up-to-date `main` for every change:
  ```bash
  git checkout main
  git pull origin main
  git checkout -b <your-name>/<short-description>   # e.g. alex/booking-endpoint
  ```
- Push your branch and open a Pull Request into `main`.
- A PR can be merged only after **at least 2 approvals** from other developers.
- Keep your branch up to date with `main` and resolve conflicts on your branch, not on `main`.
- Never commit `.env`, `db.sqlite3`, virtualenvs or `__pycache__` (they are in `.gitignore`).

## Requirements

- Python 3.12+ (Django 6 requires it)
- Optional for now: PostgreSQL and Redis. Without `POSTGRES_DB` set, the project uses SQLite.

## Local setup

```bash
git clone https://github.com/Aragorn-untold/clinic-appointment-service.git
cd clinic-appointment-service

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.sample .env                # then edit .env (see below)

python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser   # login is by email
python manage.py runserver
```

## Environment variables

Settings load `.env` from the project root via `python-dotenv`. `.env.sample` lists every variable with comments.

| Variable | Required | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | yes (outside local dev) | Generate: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"` |
| `DEBUG` | no | `True` for local dev. Defaults to `False` when unset. |
| `ALLOWED_HOSTS` | no | Comma-separated, no spaces. Must be set when `DEBUG=False`. |
| `SITE_URL` | no | Base URL of the site. Default `http://localhost:8000`. |
| `POSTGRES_DB` | no | Empty = SQLite (`db.sqlite3`). Set it to switch to PostgreSQL. |
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | if `POSTGRES_DB` is set | |
| `POSTGRES_HOST`, `POSTGRES_PORT` | no | Default `localhost` / `5432`. |
| `REDIS_URL` | no | Celery broker. Default `redis://localhost:6379/0`. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | not yet | Admin notifications (Telegram sending is not implemented yet). |
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` | not yet | Use Stripe **test** keys. |
| `STRIPE_WEBHOOK_SECRET` | not yet | Read by settings; needed once Stripe webhooks are implemented. |

## Project layout

```
core/              settings, root urls, shared permissions (core/permissions.py)
users/             custom user model `users.UserPatient` (AUTH_USER_MODEL, email login)
specializations/   app stub
doctors/           app stub
doctor_slots/      app stub
appointments/      app stub + services.py
payments/          app stub + services.py
notifications/     services.py, messages.py, tasks.py, telegram.py (not in urls)
```

## Current state

- Only `users` has a model. The other apps contain empty models/views and placeholder `urls.py`.
- No migrations are committed yet. Run `makemigrations` locally. Whoever adds models should commit the migrations in their PR.
- `notifications.services.notify_admins()` is a stub: it only writes to the log. Celery tasks and the Telegram client are not implemented yet.
- Celery, Redis, Stripe and psycopg are in `requirements.txt` but not wired up yet. Their versions are not pinned yet.

## URLs

| Path | What |
|---|---|
| `/admin/` | Django admin |
| `/api/schema/` | OpenAPI schema (drf-spectacular) |
| `/api/schema/swagger/` | Swagger UI |
| `/api/token/` | Get JWT access/refresh pair |
| `/api/token/refresh/` | Refresh access token |
| `/users/`, `/specializations/`, `/doctors/`, `/slots/`, `/appointments/` | App routes |
| `/` | `payments.urls` is mounted at the root |

## Auth

- DRF uses JWT only (`rest_framework_simplejwt`). Send `Authorization: Bearer <access token>`.
- Token lifetimes are set in `SIMPLE_JWT` in `core/settings.py`.

## Logging

`LOGGING` in `core/settings.py` prints to the console:
- The `notifications` logger shows `DEBUG` and up when `DEBUG=True`, otherwise `INFO` and up.
- Everything else shows `WARNING` and up.

To see logs from another app, add it under `"loggers"` the same way and log with `logging.getLogger(__name__)`.
