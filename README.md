# clinic-appointment-service
Online appointment management system that allows patients to register, browse doctors and available time slots, book appointments, cancel or complete visits. Payments are processed via Stripe. Staff receive Telegram notifications about new bookings, cancellations, no-shows, and successful payments.

**Stack:** Django 6, Django REST Framework, JWT (simplejwt), PostgreSQL, Redis, Celery + Celery beat, Stripe Checkout, Telegram Bot API, drf-spectacular (Swagger), Docker Compose.

## Contents

- [Contributing rules](#contributing-rules)
- [Requirements](#requirements)
- [Running in Docker](#running-in-docker) (fastest way to start)
- [Local setup](#local-setup)
- [Environment variables](#environment-variables)
- [API overview](#api-overview)
- [Request examples](#request-examples)
- [Paying with a test card](#paying-with-a-test-card)
- [Demo scenario](#demo-scenario)
- [Loading test data](#loading-test-data)
- [Tests](#tests)

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
- **After your PR is squash-merged**, `git pull origin develop` fails with "divergent branches": GitHub replaced your commits with one new commit. If you have no uncommitted work, reset your branch to `develop`:
  ```bash
  git fetch origin
  git reset --hard origin/develop
  git push --force-with-lease
  ```
- Never commit `.env`, `db.sqlite3`, virtualenvs or `__pycache__` (they are in `.gitignore`).

## Requirements

- Python 3.12+ (Django 6 requires it)
- **Redis** — required. It caches the doctors and specializations lists (without it those endpoints and the tests fail) and is the Celery broker.
- PostgreSQL — optional for local development. Without `POSTGRES_DB` set, the project uses SQLite.
- Docker with Docker Compose — the easiest way to get PostgreSQL and Redis, or to run everything.

## Running in Docker

Runs the whole stack: PostgreSQL, Redis, the web app, a Celery worker and Celery beat.

```bash
cp .env.sample .env                # then edit .env (see Environment variables)
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

## Local setup

Runs Django on your machine. PostgreSQL and Redis come from Docker.

```bash
git clone https://github.com/Aragorn-untold/clinic-appointment-service.git
cd clinic-appointment-service
git checkout develop
git checkout -b <username>-develop

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.sample .env                # then edit .env (see Environment variables)
docker compose up -d db redis      # PostgreSQL and Redis only

python manage.py migrate
python manage.py createsuperuser   # login is by email
python manage.py runserver
```

Telegram messages are sent by Celery. To get them locally, run a worker in a second terminal (and beat in a third if you need the scheduled tasks):

```bash
celery -A core worker -l info
celery -A core beat -l info
```

Without a worker, notifications wait in Redis and are sent once a worker starts.

## Environment variables

Settings load `.env` from the project root via `python-dotenv`. `.env.sample` lists every variable with comments.

| Variable | Required | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | yes (outside local dev) | Generate: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"` |
| `DEBUG` | no | `True` for local dev. Defaults to `False` when unset. |
| `ALLOWED_HOSTS` | no | Comma-separated, no spaces. Must be set when `DEBUG=False`. |
| `SITE_URL` | no | Base URL of the site. Default `http://localhost:8000`. Used for Stripe redirect links when there is no request (Celery tasks). |
| `POSTGRES_DB` | no | Empty = SQLite (`db.sqlite3`). Set it to switch to PostgreSQL. |
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | if `POSTGRES_DB` is set | |
| `POSTGRES_HOST`, `POSTGRES_PORT` | no | Default `localhost` / `5432`. |
| `REDIS_URL` | no | Celery broker. Default `redis://localhost:6379/0`. |
| `CACHE_REDIS_URL` | no | Cache for the doctors and specializations lists. Default `redis://localhost:6379/1`. |
| `TELEGRAM_BOT_TOKEN` | for notifications | Create a bot with [@BotFather](https://t.me/BotFather) and copy its token. |
| `TELEGRAM_CHAT_ID` | for notifications | Chat that receives admin messages. To find it, add the bot to the chat, run `python manage.py run_bot` (or `docker compose --profile bot up bot`) and send `/start`: the bot replies with the `chat_id`. |
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` | for payments | **Test** keys only (`sk_test_...`, `pk_test_...`): Stripe Dashboard → Developers → API keys, with "Test mode" on. |
| `STRIPE_WEBHOOK_SECRET` | no | Not used yet: payments are confirmed on the success page and by a Celery task, not by webhooks. |

## Project layout

```
core/              settings, root urls, Celery app, shared permissions, middleware, BaseTestCase
users/             custom user model `users.UserPatient` (email login), registration, profile
specializations/   specializations CRUD
doctors/           doctors CRUD, bulk slot creation, slot list per doctor
doctor_slots/      doctor time slots: view and delete
appointments/      booking, cancel / complete / no-show (services.py), nightly NO_SHOW task
payments/          Stripe Checkout sessions (services.py), success / cancel pages, renew, sync task
notifications/     Telegram messages (messages.py), sending via Celery (tasks.py), run_bot command
fixtures/          initial_data.json with demo data
```

## API overview

Full, interactive documentation is in Swagger UI at `/api/schema/swagger/`. Prices are charged in **USD**.

Rate limits: anonymous users 300 requests/day, logged-in users 1000/day.

<!-- Section for Q.3 / D.2: users and auth. Owner to review: aragorn-untold -->
### Users and auth

| Method | Path | Who | What |
|---|---|---|---|
| POST | `/users/` | anyone | Register: `email`, `password`, `first_name`, `last_name` |
| POST | `/api/token/` | anyone | Get `access` and `refresh` tokens (email + password) |
| POST | `/api/token/refresh/` | anyone | Get a new `access` token |
| GET, PUT, PATCH | `/users/me/` | logged in | Your profile (email and `is_staff` are read-only) |

Admins are created with `python manage.py createsuperuser`. See [Auth](#auth) for the header format.

<!-- Section for Q.1: doctors and slots. Owner to review: fedirkiiko -->
### Specializations, doctors and slots

Everyone can read; only admins can create, change or delete.

| Method | Path | What |
|---|---|---|
| GET, POST | `/specializations/` | List / create (`name`, `code`, `description`). `name` and `code` are unique. |
| GET, PUT, PATCH, DELETE | `/specializations/<id>/` | One specialization |
| GET, POST | `/doctors/` | List / create. Filter: `?specialization=<id or code>`. Doctors are linked to specializations by `code`. |
| GET, PUT, PATCH, DELETE | `/doctors/<id>/` | One doctor |
| POST | `/doctors/<id>/slots/` | Admin: create many slots at once (see below) |
| GET | `/doctors/<id>/slots/` | A doctor's slots. Filters: `from`, `to` (ISO datetime), `available_only=true` |
| GET, DELETE | `/slots/<id>/` | One slot. A slot with any appointment (even cancelled) can't be deleted. |

Bulk slot creation splits a time range into slots of equal length. Times are in the project time zone (Europe/Kyiv). Slots that overlap existing ones are skipped, and a remainder shorter than one slot is dropped:

```json
{"date": "2026-11-02", "start_time": "09:00", "end_time": "13:00", "slot_length_minutes": 30}
```

The specializations and doctors lists are cached in Redis for 15 minutes. The cache is cleared automatically whenever a doctor or specialization changes.

<!-- Section for Q.2: appointments. Owner to review: andriikinash127 -->
### Appointments

All endpoints need a logged-in user. Patients see and change only their own appointments (someone else's returns 404); admins see all.

| Method | Path | Who | What |
|---|---|---|---|
| GET | `/appointments/` | patient / admin | List. Filters: `status`, `doctor_id`, `patient_id` (admin), `from`, `to` (`YYYY-MM-DD` or ISO datetime) |
| POST | `/appointments/` | patient | Book: `{"doctor_slot": <id>}` |
| GET | `/appointments/<id>/` | patient / admin | Details, including the slot and all payments |
| POST | `/appointments/<id>/cancel/` | owner / admin | Cancel |
| POST | `/appointments/<id>/complete/` | admin | Mark as completed |
| POST | `/appointments/<id>/no-show/` | admin | Mark as no-show |

Rules:
- **Booking:** the slot must be in the future and not already booked. The price is copied from the doctor. A patient with a `PENDING` or `EXPIRED` payment can't book until it is paid.
- **Status:** every appointment starts as `BOOKED`. Cancel, complete and no-show only work on `BOOKED` appointments; otherwise the API returns 400.
- **Payments created on status change:**

  | Action | Payment | Amount |
  |---|---|---|
  | Complete | `CONSULTATION` | 100% of the price |
  | Cancel less than 24 hours before the start | `CANCELLATION_FEE` | 50% |
  | Cancel 24 hours or more before the start | none | free |
  | No-show | `NO_SHOW_FEE` | 120% |
- **Nightly task:** every day at 00:05 (Kyiv time) Celery beat marks all `BOOKED` appointments whose slot has ended as `NO_SHOW`. If there are none, admins get "No missed appointments today!".
- If Stripe is unavailable, the API returns 502 and the appointment stays `BOOKED`.

<!-- Section for Q.4: payments. Owner to review: vlad-krivospitsky, argus20 -->
### Payments

| Method | Path | Who | What |
|---|---|---|---|
| GET | `/payments/` | logged in | List: patients see their own, admins see all |
| GET | `/payments/<id>/` | logged in | One payment, including `session_url` (the Stripe payment page) |
| POST | `/payments/<id>/renew/` | owner | New Stripe session for an `EXPIRED` payment |
| GET | `/success/?session_id=...` | anyone | Stripe sends the patient here after paying. Checks the session with Stripe and marks the payment `PAID`. |
| GET | `/cancel/` | anyone | Stripe sends the patient here if they leave the payment page |

Payment statuses: `PENDING` → `PAID`, or `PENDING` → `EXPIRED` when the Stripe session expires (after 24 hours).

Every 30 minutes Celery beat checks `PENDING` payments with Stripe: expired sessions become `EXPIRED`, and paid ones become `PAID`. This covers a patient who paid but closed the tab before returning to the success page.

### Telegram notifications

Admins get a message in `TELEGRAM_CHAT_ID` when an appointment is booked, cancelled, completed or marked as no-show, and when a payment succeeds. Messages are sent by the Celery worker, so it must be running.

## Request examples

<!-- Section for Q.5: request examples. Owner to review: argus20 -->
Examples use `curl` against http://localhost:8000. Replace `<...>` with real values.

Register and log in:

```bash
curl -X POST http://localhost:8000/users/ -H "Content-Type: application/json" \
  -d '{"email": "anna@example.com", "password": "Strong-pass-123", "first_name": "Anna", "last_name": "Bondar"}'

curl -X POST http://localhost:8000/api/token/ -H "Content-Type: application/json" \
  -d '{"email": "anna@example.com", "password": "Strong-pass-123"}'
# {"refresh": "...", "access": "<ACCESS>"}
```

Find a doctor and a free slot (no login needed):

```bash
curl "http://localhost:8000/doctors/?specialization=cardiology"
curl "http://localhost:8000/doctors/<doctor_id>/slots/?available_only=true"
```

Book, view and cancel an appointment:

```bash
curl -X POST http://localhost:8000/appointments/ -H "Authorize: Bearer <ACCESS>" \
  -H "Content-Type: application/json" -d '{"doctor_slot": <slot_id>}'

curl http://localhost:8000/appointments/<id>/ -H "Authorize: Bearer <ACCESS>"

curl -X POST http://localhost:8000/appointments/<id>/cancel/ -H "Authorize: Bearer <ACCESS>"
```

Admin: create slots and complete an appointment:

```bash
curl -X POST http://localhost:8000/doctors/<doctor_id>/slots/ -H "Authorize: Bearer <ADMIN_ACCESS>" \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-11-02", "start_time": "09:00", "end_time": "13:00", "slot_length_minutes": 30}'

curl -X POST http://localhost:8000/appointments/<id>/complete/ -H "Authorize: Bearer <ADMIN_ACCESS>"
# "payments": [{"type": "CONSULTATION", "status": "PENDING", "session_url": "https://checkout.stripe.com/...", ...}]
```

## Paying with a test card

Payments use Stripe Checkout in **test mode**: no real money moves. You need Stripe test keys in `.env` (see [Environment variables](#environment-variables)).

1. Get a payment link: complete an appointment as admin (or cancel one less than 24 hours ahead). The response contains `payments[].session_url`. You can also find it later in `GET /appointments/<id>/` or `GET /payments/`.
2. Open `session_url` in a browser and pay with the test card:

   | Field | Value |
   |---|---|
   | Card number | `4242 4242 4242 4242` |
   | Expiry | any future date, e.g. `12/34` |
   | CVC | any 3 digits |
   | Name, email, ZIP | anything |

   To test a declined payment, use `4000 0000 0000 0002`. More cards: https://docs.stripe.com/testing
3. Stripe redirects you to `/success/?session_id=...`, which returns `{"status": "PAID"}`. The payment is now `PAID` in `GET /appointments/<id>/`, and admins get a Telegram message.

If you close the tab before the redirect, the payment still becomes `PAID` within 30 minutes (the Celery beat check).

If a session expires unpaid, the payment becomes `EXPIRED` and the patient can't book until they renew it: `POST /payments/<id>/renew/` returns a new `session_url`.

## Demo scenario

The full flow, about 5 minutes. Start the stack with `docker compose up --build` and fill in Stripe test keys and Telegram settings in `.env` first.

1. **Admin setup** (Swagger or Django admin, logged in as a superuser): create a specialization and a doctor, then create slots with `POST /doctors/<id>/slots/`. Or load the demo data with `loaddata fixtures/initial_data.json`: 3 doctors with one slot each on 2027-01-10 (Olena Kovalenko's is already booked), which is enough for a short demo.
2. **Patient registers and logs in:** `POST /users/`, then `POST /api/token/`. In Swagger, click **Authorize** and enter `Bearer <access>`.
3. **Patient browses:** `GET /doctors/?specialization=<code>`, then `GET /doctors/<id>/slots/?available_only=true`.
4. **Patient books:** `POST /appointments/` with a free slot → status `BOOKED`. Admins get a "New appointment" message in Telegram.
5. **Admin completes the visit:** `POST /appointments/<id>/complete/` → status `COMPLETED`, a `CONSULTATION` payment with a `session_url`. Telegram: "Appointment completed".
6. **Patient pays:** open `session_url`, pay with `4242 4242 4242 4242` (see [Paying with a test card](#paying-with-a-test-card)). The success page returns `PAID`. Telegram: "Payment succeeded".
7. **Check:** `GET /appointments/<id>/` shows the payment as `PAID`.

Optional extras: cancel a booking less than 24 hours ahead to show the 50% fee, or try `POST /appointments/<id>/complete/` as a patient to show the 403.

Don't use the fixture's `patient@example.com` for the demo: it has no usable password and already has a `PENDING` payment, so it can't book. Register a new patient instead.

## Loading test data

After applying migrations, load the shared demo data:

```bash
python manage.py loaddata fixtures/initial_data.json
```

The fixture contains 3 specializations, 3 doctors with one slot each on 2027-01-10, a test patient (`patient@example.com`, no usable password), one `BOOKED` appointment and its `PENDING` payment.

Create your own administrator account separately:

```bash
python manage.py createsuperuser
```

**Note:** The fixture uses fixed primary keys for its sample records. Load it into a fresh local database after migrations. Avoid loading it repeatedly into a database that already contains conflicting records.

## Tests

Tests use Django's built-in test runner (`unittest`), no pytest. **Redis must be running** (`docker compose up -d redis`): the tests use the cache.

```bash
python manage.py test                    # all tests
python manage.py test appointments       # one app
python manage.py test users.tests.test_models.UserPatientTests  # one class
```

Tests run against a temporary test database created from your current DB settings. To use SQLite even when `POSTGRES_DB` is set in `.env` (e.g. Postgres is not running):

```bash
POSTGRES_DB= python manage.py test
```

Tests based on `BaseTestCase` clear the Redis cache (`CACHE_REDIS_URL`) before each test, so your local list cache is emptied when you run them.

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
  from core.tests.base import BaseTestCase


  class AppointmentApiTests(BaseTestCase):
      def test_patient_sees_own_appointments(self):
          response = self.auth_client.get("/appointments/")
          self.assertEqual(response.status_code, 200)
  ```

  Shared data is created once per test class and rolled back after it. `self.slot` is already booked, so create a new slot when a test needs a free one.
- Never call Stripe or Telegram from tests: replace them with `unittest.mock.patch`. For Telegram, patch `notify_admins` where it is used (e.g. `payments.views.notify_admins`); otherwise the test queues a real message in Redis. Run Celery tasks inline with `@override_settings(CELERY_TASK_ALWAYS_EAGER=True)`.
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
python manage.py makemigrations --check --dry-run   # fails if a model change has no migration
coverage run manage.py test && coverage report
```

All of them must pass; CI runs the same checks. Remember to `git add` new files, including migrations.

## URLs

| Path | What |
|---|---|
| `/admin/` | Django admin |
| `/api/schema/` | OpenAPI schema (drf-spectacular) |
| `/api/schema/swagger/` | Swagger UI |
| `/api/token/`, `/api/token/refresh/` | JWT tokens (also at `/users/token/`) |
| `/users/`, `/specializations/`, `/doctors/`, `/slots/`, `/appointments/`, `/payments/` | API, see [API overview](#api-overview) |
| `/success/`, `/cancel/` | Stripe redirect pages |

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
