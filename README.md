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

## Screenshots
<img width="1920" height="969" alt="SS16" src="https://github.com/user-attachments/assets/4dfbbccf-2bcd-4de0-a101-e70eb902a6a3" />
<img width="1920" height="1024" alt="SS15" src="https://github.com/user-attachments/assets/77f02292-b886-4c29-be08-bdf711c2e9e2" />
<img width="1920" height="1025" alt="SS14" src="https://github.com/user-attachments/assets/4eafc3f4-803c-426c-9c45-555181c4872f" />
<img width="1920" height="1020" alt="SS13" src="https://github.com/user-attachments/assets/ade0d2ff-3caa-46e1-8faf-89809ab67db6" />
<img width="1920" height="1019" alt="SS12" src="https://github.com/user-attachments/assets/4fad83ae-7a5d-4c9e-b1d3-f8811edcdccd" />
<img width="1920" height="1022" alt="SS11" src="https://github.com/user-attachments/assets/5b9c1a30-2b7a-4e23-a265-b117fd2a05a9" />
<img width="1920" height="1027" alt="SS10" src="https://github.com/user-attachments/assets/1c61d76f-17ed-4c48-97b3-3aa56a53509d" />
<img width="1920" height="1022" alt="SS9" src="https://github.com/user-attachments/assets/cb569056-086e-48f2-b3f7-f0311d72b1ae" />
<img width="1920" height="1020" alt="SS8" src="https://github.com/user-attachments/assets/0ca8a145-d991-43f2-9a89-4923da8a2129" />
<img width="1920" height="1024" alt="SS7" src="https://github.com/user-attachments/assets/0dd1f29c-3abd-4ae7-859b-f364f874185b" />
<img width="1920" height="1024" alt="SS6" src="https://github.com/user-attachments/assets/0a1e7757-09f8-4334-a6c9-24e947a24433" />
<img width="1920" height="1017" alt="SS5" src="https://github.com/user-attachments/assets/3bf12fbd-28bc-4cba-93c4-cfc3c94cf6f5" />
<img width="1920" height="1017" alt="SS4" src="https://github.com/user-attachments/assets/38e24505-8e24-471d-81c4-0cba7d7f25ea" />
<img width="1920" height="1018" alt="SS3" src="https://github.com/user-attachments/assets/6bf5f609-9a26-4b65-b7f9-f522e7331b26" />
<img width="1920" height="1019" alt="SS2" src="https://github.com/user-attachments/assets/e67250a1-c44a-49cb-8c44-f4fa1f722a2f" />
<img width="1920" height="1024" alt="SS1" src="https://github.com/user-attachments/assets/13eda34e-e900-4cb3-a0a0-d2a542ac5b16" />
