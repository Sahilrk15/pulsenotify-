# PulseNotify - Flight Price Monitor & Alert System

Django + DRF + JWT backend. Users create price alerts for a route; **Celery Beat** runs `check_prices`
every 60 seconds, calls our own mock price feed with `requests.get()`, and fires `send_notification.delay()`
when the price is at or below the threshold. Redis is the broker, PostgreSQL the database.

## Stack
Django 6.1, DRF 3.18, SimpleJWT, Celery 5.6, Redis 7, PostgreSQL 16 (Docker Compose), PGAdmin 4.

## Project layout
```
pulsenotify/settings/{base,local,production}.py   split settings, all secrets from .env
pulsenotify/celery.py                             Celery app (loaded in pulsenotify/__init__.py)
pulse/models.py        UserProfile, PriceAlert, NotificationLog
pulse/signals.py       post_save on User -> auto-create UserProfile (connected in apps.py ready())
pulse/permissions.py   custom IsAdminUser (profile.role == ADMIN)
pulse/tasks.py         check_prices + send_notification (@shared_task)
pulse/views.py         7 endpoints
pulse/tests.py         unit tests
```

## Setup (Windows, run in the VS Code terminal from the folder that contains manage.py)
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose up -d          # PostgreSQL (5435), Redis (6379), PGAdmin (5050)
python manage.py migrate
python manage.py test         # 11 tests must pass
```

## Run - three terminals at the same time
```powershell
# Terminal 1 - API server
python manage.py runserver

# Terminal 2 - Celery worker   (--pool=solo is required on Windows)
celery -A pulsenotify worker --loglevel=info --pool=solo

# Terminal 3 - Celery beat (scheduler, fires check_prices every 60 s)
celery -A pulsenotify beat --loglevel=info
```
Activate the venv (`venv\Scripts\activate`) in each new terminal.

## Making a user an admin
Register the user first, then run `python manage.py make_admin <username>`
(or edit `role` to `admin` in the `pulse_userprofile` table in PGAdmin). Log in again to get a token.

## PGAdmin
Open http://localhost:5050 (login from `.env`: `PGADMIN_EMAIL` / `PGADMIN_PASSWORD`).
Register server -> Host `db`, Port `5432`, DB/user/password from `.env`.
Tables: `pulse_userprofile`, `pulse_pricealert`, `notification_logs`.

## Endpoints
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register/` | Public | Create user (+ profile via signal); role is always `user`; 400 on duplicate username |
| POST | `/api/auth/login/` | Public | Returns JWT; 401 on bad credentials |
| POST | `/api/alerts/` | JWT | Create alert; user comes from the token, never the body |
| GET | `/api/alerts/` | JWT | Only the caller's alerts (empty list, never 404) |
| DELETE | `/api/alerts/<id>/` | JWT | Soft delete -> `{"status": "inactive"}`; 404 for another user's alert |
| GET | `/api/flights/price/?route=DEL-BOM` | Public | Mock price feed; 404 for unknown route |
| GET | `/api/admin/summary/` | JWT, admin | Aggregated stats; 403 for regular users |

Mock routes: `DEL-BOM`, `BLR-HYD`, `DEL-BLR`, `BOM-GOA`.

## Postman
Import `pulsenotify.postman_collection.json` and run requests 00-13 in order. Run
`python manage.py make_admin pulse_admin` after request 00 and before request 12a.

## Design decisions
- `send_notification` is called with `.delay()` so `check_prices` never waits for the notification write.
- `send_notification` skips alerts that are no longer `active`, so a slow worker can never notify twice.
- `check_prices` clears the model's default ordering (`.order_by()`) before `.distinct()`, otherwise
  `created_at` would leak into the DISTINCT and the same route would be checked repeatedly.
- DELETE returns 404 (not 403) for someone else's alert so the existence of other users' alerts never leaks.
- Counting in the admin summary is done in the database (`aggregate`, `values().annotate(Count)`), no Python loops.
