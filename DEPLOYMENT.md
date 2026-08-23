# Deployment Guide (Phase 9.5)

This document prepares the project for production deployment. **Nothing
here has actually been deployed** - no paid services were provisioned as
part of this work. This is configuration and documentation only; you
still need to create real accounts/services and follow these steps
yourself.

## Architecture

```
Frontend (static files)          Twilio
      |                             |
   HTTPS                         HTTPS webhook
      |                             |
      +----------> FastAPI backend <+
                          |
              +-----------+-----------+
              |                       |
        Managed MySQL              Redis
```

## 1. Backend deployment (Render or AWS)

The backend is already containerized (`backend/Dockerfile`), so any
platform that runs a Docker image works. Render is the simplest option
for this project's size.

### Render (recommended for simplicity)
1. Push this repo to GitHub/GitLab.
2. In Render: New -> Web Service -> connect the repo, root directory `backend/`.
3. Render auto-detects the `Dockerfile`. Set:
   - **Start command**: leave as the Dockerfile's `CMD` (already correct) -
     or, if deploying without Docker (Render's native Python runtime
     instead), Render will pick up `backend/Procfile` automatically,
     which binds to Render's injected `$PORT` correctly.
   - **Health check path**: `/health/db`.
4. Add all environment variables from the table below in Render's dashboard
   (never commit them - Render's env var UI is the right place).
5. Render provides HTTPS automatically on its `*.onrender.com` domain, or
   attach a custom domain with automatic TLS.

### AWS (more control, more setup)
- ECS Fargate or App Runner, both can run the existing Dockerfile directly.
- Use an Application Load Balancer with an ACM certificate for HTTPS.
- Store secrets in AWS Secrets Manager or Parameter Store, injected as
  container environment variables - not baked into the image.

## 2. Managed MySQL

Any managed MySQL 8.0-compatible service works (PlanetScale, AWS RDS,
Render's own managed Postgres/MySQL, DigitalOcean Managed Databases, etc.)
Point these at it:

```
MYSQL_HOST=<your managed database host>
MYSQL_PORT=3306
MYSQL_USER=<a dedicated app user, not root>
MYSQL_PASSWORD=<strong generated password>
MYSQL_DATABASE=hotel_ai
```

**Do not reuse the local dev database or its trivial password
(`hotel_pass_dev`) in production.** Create a fresh managed instance, run
the schema creation (`python -m app.database.seed` handles both
`Base.metadata.create_all()` and initial room/hotel_info seeding - see
`backend/app/database/seed.py`), and use strong, generated credentials
stored only in your platform's secret manager.

## 3. Redis

Any managed Redis works (Render Redis, AWS ElastiCache, Upstash, Redis
Cloud). Set:

```
REDIS_URL=redis://<user>:<password>@<host>:<port>/0
```

If this is left unset, the app automatically falls back to in-memory
storage (see `backend/app/storage.py`) - which technically "works" but
defeats the purpose of a production deployment (sessions/audio cache
won't be shared if you ever run more than one backend instance, and
they're lost on every restart). **Set REDIS_URL in production.**

## 4. Frontend deployment

The frontend is static files (`frontend/` and `frontend/admin/`) - no
build step, deployable to Vercel, Netlify, Cloudflare Pages, or even a
plain S3 bucket + CloudFront.

**The only change needed per environment** is `frontend/config.js` (and
`frontend/admin/config.js`):

```js
window.HOTEL_API_BASE = "https://api.yourhotel.com";  // your real backend URL
```

Deploy `frontend/` as the customer-facing site and `frontend/admin/` as a
separate deployment (or a subpath) for staff - keep in mind the admin
dashboard has **no authentication yet** (see Security section below) -
do not deploy it to a publicly discoverable URL without adding auth first.

## 5. HTTPS

- Backend: your hosting platform's HTTPS (Render/AWS both provide this
  automatically with a custom domain + managed certificate).
- Frontend: your static host's HTTPS (Vercel/Netlify/Cloudflare Pages all
  provide this by default).
- Twilio **requires** HTTPS for webhook URLs in production - a plain HTTP
  URL will not work for a real (non-trial-testing) Twilio configuration.

## 6. Twilio production webhook

Once the backend has a real HTTPS URL (not ngrok, not localhost):

1. Twilio Console -> Phone Numbers -> your number -> Voice Configuration.
2. "A call comes in" -> Webhook -> `https://api.yourhotel.com/telephony/incoming` -> HTTP POST.
3. Set `PUBLIC_BASE_URL=https://api.yourhotel.com` in the backend's env vars
   (this is what generates the `<Play>` URLs Twilio fetches audio from -
   see `backend/app/api/telephony.py`).
4. Set a real `TWILIO_AUTH_TOKEN` - this automatically turns ON signature
   validation (it's a no-op/open in dev when unset - see
   `_is_valid_twilio_request` in `telephony.py`). **Do not deploy publicly
   with this unset.**

### ngrok - local testing only, never production
ngrok remains useful for testing Twilio webhooks against your laptop
during development (see the Phase 7 section of the main README). It is
NOT a production architecture - ngrok URLs are temporary, change on
every restart (free tier), and route through a third-party tunnel. The
real backend URL from step 1-3 above is what production Twilio should
point at.

## 7. Complete environment variable reference

| Variable | Local dev default | Production guidance |
|---|---|---|
| `MYSQL_HOST` | `localhost` | Managed DB host |
| `MYSQL_PORT` | `3306` | Usually `3306` |
| `MYSQL_USER` | `hotel_user` | Dedicated app user |
| `MYSQL_PASSWORD` | `hotel_pass_dev` | Strong generated secret |
| `MYSQL_DATABASE` | `hotel_ai` | `hotel_ai` (or your choice) |
| `OPENAI_API_KEY` | (empty) | Real key - required for TTS always, and for chat if `LLM_PROVIDER=openai` |
| `LLM_PROVIDER` | `ollama` | `ollama` (if self-hosting Ollama) or `openai` |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Your Ollama server's URL if using it in production |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | Same |
| `TWILIO_ACCOUNT_SID` | (empty) | Real SID |
| `TWILIO_AUTH_TOKEN` | (empty) | Real token - **turns on signature validation** |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Your real HTTPS backend URL |
| `TWILIO_SMS_FROM_NUMBER` | (empty) | A Twilio number capable of SMS, for booking confirmations |
| `REDIS_URL` | (empty, falls back to in-memory) | Real managed Redis URL |
| `SESSION_TTL_SECONDS` | `3600` | Adjust as needed |
| `AUDIO_CACHE_TTL_SECONDS` | `300` | Adjust as needed |
| `CORS_ORIGINS` | local dev origins | Your real frontend domain(s), comma-separated - never `*` |
| `RATE_LIMIT_ENABLED` | `true` | Keep `true` in production |

## 8. Production readiness checklist

- [ ] Managed MySQL provisioned, schema created via `app/database/seed.py`, strong credentials
- [ ] Managed Redis provisioned, `REDIS_URL` set
- [ ] Backend deployed with HTTPS, health check on `/health/db`
- [ ] `CORS_ORIGINS` set to real frontend domain(s) only
- [ ] `TWILIO_AUTH_TOKEN` set (enables signature validation)
- [ ] `RATE_LIMIT_ENABLED=true`
- [ ] Frontend `config.js` files point at the real backend HTTPS URL
- [ ] Twilio webhook points at the real backend HTTPS URL, not ngrok
- [ ] Admin dashboard (`frontend/admin/`) is NOT deployed to a public,
      discoverable URL without adding authentication first (explicitly
      out of scope for Phase 8/9 - see `backend/app/api/admin.py`'s
      docstring)
- [ ] No `.env` file committed to version control
- [ ] All secrets live in the hosting platform's secret manager, not in code

## What was intentionally NOT done in this phase

- **No actual deployment.** No Render/AWS account was created, no managed
  MySQL/Redis was provisioned, nothing was pushed to any cloud service.
  This document is preparation, not execution, per the task's explicit
  scope.
- **No admin authentication.** Flagged repeatedly since Phase 8.1 - the
  admin dashboard has zero auth. This is real, necessary work before
  that dashboard should ever be reachable from a public URL, and it's
  outside what was asked for in Phase 8/9's defined scope.
- **Docker was not actually run.** `docker build`/`docker compose up`
  could not be executed in the sandbox this project was built in (no
  Docker daemon available). The Dockerfile and docker-compose.yml were
  validated for syntax/structure correctness, but you should run
  `docker compose up --build` yourself as the first real test.
