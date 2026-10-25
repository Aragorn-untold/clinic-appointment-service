# clinic-appointment-service
Online appointment management system that allows patients to register, browse doctors and available time slots, book appointments, cancel or complete visits. Payments are processed via Stripe. Staff receive Telegram notifications about new bookings, cancellations, no-shows, and successful payments.

## Contributing rules

- **`develop` is the working branch.** All work is integrated there.
- **`main` is read-only.** Do not commit, push, or open Pull Requests into `main`.
- **Never commit or push directly to `develop`.**
- Each developer works on their own branch named `<username>-develop`, created from an up-to-date `develop`:
  ```bash
  git checkout develop
  git pull origin develop
  git checkout -b <username>-develop   # e.g. alex-develop
  ```
- Push your branch and open a Pull Request into `develop`.
- A PR can be merged only after **at least 2 approvals** from other developers.
- Keep your branch up to date with `develop` and resolve conflicts on your branch, not on `develop`:
  ```bash
  git checkout <username>-develop
  git pull origin develop
  ```
- Never commit `.env`, `db.sqlite3`, virtualenvs or `__pycache__` (they are in `.gitignore`).

## Requirements

- Python 3.12+ (Django 6 requires it)
- Optional for now: PostgreSQL and Redis. Without `POSTGRES_DB` set, the project uses SQLite.

## Local setup

```bash
git clone https://github.com/Aragorn-untold/clinic-appointment-service.git
cd clinic-appointment-service
git checkout develop
git checkout -b <username>-develop

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.sample .env                # then edit .env (see below)

python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser   # login is by email
python manage.py runserver
```

## Running in Docker

Runs the whole stack: PostgreSQL, Redis, the web app, a Celery worker and Celery beat.

```bash
cp .env.sample .env                # then edit .env (see below)
docker compose up --build          # add -d to run in the background
```

Migrations are applied when `web` starts. Then, in a second terminal:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py loaddata fixtures/initial_data.json   # optional demo data
```

- Swagger UI: http://localhost:8000/api/schema/swagger/
- Django admin: http://localhost:8000/admin/

Keep `localhost` in `.env`: `docker-compose.yml` points the containers at the `db` and `redis` services itself, so the same `.env` works with and without Docker.

| Service | What |
|---|---|
| `db`, `redis` | PostgreSQL and Redis. Ports 5432 and 6379 are also open on your machine, so `python manage.py runserver` outside Docker can use them. |
| `web` | Django dev server on port 8000. The project folder is mounted, so code changes reload automatically. |
| `celery_worker` | Runs background tasks (Telegram messages). |
| `celery_beat` | Schedules the NO_SHOW check (daily at 00:05, Kyiv time) and the Stripe payment check (every 30 minutes). |
| `bot` | Telegram bot that replies to `/start` with your `chat_id`. Off by default, start it with `docker compose --profile bot up bot`. |

Useful commands:

```bash
docker compose ps                  # what is running
docker compose logs -f celery_beat # follow one service's logs
docker compose down                # stop everything (data stays in volumes)
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
| `CACHE_REDIS_URL` | no | Cache for the doctors and specializations lists. Default `redis://localhost:6379/1`. |
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

- `users` contains the custom user model `users.UserPatient`, which uses email for authentication.
- `specializations`, `doctors`, `doctor_slots`, `appointments`, and `payments` contain the initial data models and Django admin registrations.
- Initial migrations are committed with the models.
- `fixtures/initial_data.json` contains shared test data for specializations, doctors, doctor slots, a test patient, an appointment, and a payment.
- `notifications.services.notify_admins()` is a stub: it only writes to the log. Celery tasks and the Telegram client are not implemented yet.
- Celery, Redis, Stripe, and psycopg are listed in `requirements.txt` but are not fully wired up yet.

## Loading Test Data

After setting up the environment and applying migrations, load the shared test data:

```bash
python manage.py migrate
python manage.py loaddata fixtures/initial_data.json
```

The fixture includes sample specializations, doctors, doctor slots, a test patient, an appointment, and a payment.

Create your own administrator account separately:

```bash
python manage.py createsuperuser
```

**Note:** The fixture uses fixed primary keys for its sample records. Load it into a fresh local database after migrations. Avoid loading it repeatedly into a database that already contains conflicting records.

## Tests

Tests use Django's built-in test runner (`unittest`), no pytest.

```bash
python manage.py test                    # all tests
python manage.py test appointments       # one app
python manage.py test users.tests.test_models.UserPatientTests  # one class
```

Tests run against a temporary test database created from your current DB settings. To use SQLite even when `POSTGRES_DB` is set in `.env` (e.g. Postgres is not running):

```bash
POSTGRES_DB= python manage.py test
```

### Writing tests

- Put tests in `<app>/tests/test_*.py` (the `tests/` folder needs an `__init__.py`).
- Inherit from `core.tests.base.BaseTestCase` to get shared data instead of creating it in every file:

  | Attribute | What |
  |---|---|
  | `self.user` / `self.admin_user` | Regular patient / superuser (password: `core.tests.base.PASSWORD`) |
  | `self.specialization`, `self.doctor` | Cardiology, doctor linked to it, price `800.00` |
  | `self.slot` | 30-minute slot tomorrow for `self.doctor` |
  | `self.appointment` | `BOOKED` appointment of `self.user` on `self.slot` |
  | `self.client` / `self.auth_client` / `self.admin_client` | `APIClient`: anonymous / logged in as `user` / as `admin_user` |

  ```python
  # example: once the appointments endpoints exist
  from core.tests.base import BaseTestCase


  class AppointmentApiTests(BaseTestCase):
      def test_patient_sees_own_appointments(self):
          response = self.auth_client.get("/appointments/")
          self.assertEqual(response.status_code, 200)
  ```

  Shared data is created once per test class and rolled back after it. `self.slot` is already booked, so create a new slot when a test needs a free one.
- Never call Stripe or Telegram from tests: replace them with `unittest.mock.patch`. Run Celery tasks inline with `@override_settings(CELERY_TASK_ALWAYS_EAGER=True)`.
- A PR that adds code without tests for it is not approved.

## Coverage

Settings are in `.coveragerc` (migrations, tests, `manage.py`, `asgi.py`, `wsgi.py` are excluded).

```bash
coverage run manage.py test
coverage report        # table in the terminal, fails if total coverage < 60%
coverage html          # detailed report in htmlcov/index.html
```

## Code style (ruff)

[ruff](https://docs.astral.sh/ruff/) is both the linter and the formatter. Settings are in `ruff.toml`: line length 120, migrations are skipped, imports are sorted (stdlib → third-party → project apps). The version is pinned in `requirements.txt` so everyone gets the same results.

```bash
ruff check .               # find problems
ruff check --fix .         # fix what can be fixed automatically (unused/unsorted imports, ...)
ruff format .              # format code
ruff format --check .      # only check formatting (what CI runs)
```

## Before opening a PR

```bash
ruff check . && ruff format --check .
coverage run manage.py test && coverage report
```

All of them must pass.


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

- DRF uses JWT only (`rest_framework_simplejwt`). Get a token pair from `POST /api/token/` (email + password).
- Send the access token in the **`Authorize`** header (not `Authorization`), with the `Bearer` prefix:
  ```
  Authorize: Bearer <access token>
  ```
  The header name is set by `SIMPLE_JWT["AUTH_HEADER_NAME"] = "HTTP_AUTHORIZE"` in `core/settings.py`.
- In Swagger UI, click **Authorize** and enter `Bearer <access token>`, including the word `Bearer` and a space. Swagger does not add the prefix for you.
- Token lifetimes are set in `SIMPLE_JWT` in `core/settings.py`.

## Logging

`LOGGING` in `core/settings.py` prints to the console:
- The `notifications` logger shows `DEBUG` and up when `DEBUG=True`, otherwise `INFO` and up.
- Everything else shows `WARNING` and up.

To see logs from another app, add it under `"loggers"` the same way and log with `logging.getLogger(__name__)`.
