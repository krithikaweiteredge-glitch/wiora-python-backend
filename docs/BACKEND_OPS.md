# Backend ops — hardening, Redis, workflow, web search

What was added and how to turn each on. Everything is **optional and graceful** —
the API runs today with none of these configured.

## Production hardening (Phase 15)

- **Logging + request ids:** every request logs `rid=… METHOD path -> status (Nms)`
  (`app/middleware.py`). Set `LOG_LEVEL` (default INFO).
- **Security headers:** `X-Content-Type-Options`, `X-Frame-Options`, HSTS,
  `Referrer-Policy` on every response.
- **CORS:** set `ALLOWED_ORIGINS` (comma-separated) to lock down; default `*`
  (fine for the mobile client).
- **Sentry:** set `SENTRY_DSN` → auto-enables (`sentry-sdk` already in
  requirements). No DSN = no-op.
- **Alembic migrations:** infra in `alembic.ini` + `migrations/`. `create_all`
  still provisions fresh DBs. For a schema change going forward:
  ```
  alembic revision --autogenerate -m "add X"
  alembic upgrade head
  ```

## Web search tool (#5)

Set `SEARCH_API_KEY` (+ optional `SEARCH_PROVIDER=tavily|brave|serper`, default
tavily). Get a free key at tavily.com. Without a key the `search_web` tool politely
reports "not configured". Results are cached in Redis for 10 min.

## Redis (#10)

Set `REDIS_URL` (e.g. `redis://localhost:6379/0`). Enables: per-user rate limiting,
the search cache, and the **session store** (`cache.session_get/set/delete`) — the
mobile-native equivalent of web sessions (the app authenticates with a Firebase
bearer token, not a cookie). Empty `REDIS_URL` = all of this no-ops safely.

> Cookies note: browser cookies don't apply to the React Native client. If a **web**
> client is added later, layer cookie-based sessions on top of this same store.

## Celery + FCM push (#11)

Scheduled reminder delivery + daily briefing push. Needs a broker + a worker/beat
process + FCM credentials. The FastAPI app never imports Celery, so the API is
unaffected whether or not workers run.

1. **Broker:** `REDIS_URL` (or `CELERY_BROKER_URL`).
2. **FCM:** `pip install firebase-admin` + set `FCM_CREDENTIALS_PATH` to a Firebase
   service-account JSON.
3. **Device tokens:** the mobile app registers its FCM token by saving the
   preference `fcmToken` (existing `PUT /api/preferences` — no new endpoint).
4. **Run the workers:**
   ```
   celery -A app.workflow.celery_app.celery worker --loglevel=info
   celery -A app.workflow.celery_app.celery beat  --loglevel=info
   ```

Beat schedule: `deliver_due_reminders` (every 60s), `send_daily_briefings` (07:00
UTC). Reminder pushes are de-duped via a Redis key so each fires once.

**Still to wire for full push:** mobile side must obtain an FCM token
(`expo-notifications` getDevicePushTokenAsync) and save it as the `fcmToken`
preference; and `send_daily_briefings` should call the real briefing generator once
per-user timezones are persisted.
