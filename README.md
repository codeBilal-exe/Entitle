# Entitle

**Find out what you're owed. Every answer comes with a receipt.**

Around the world, scholarships, cash support and health cover go unclaimed because people don't know the rules, or the rules change and nobody tells them. A chatbot can't fix that, because it will confidently invent a rule, and on welfare a wrong answer costs a family its support.

Entitle is AI that has to show its receipts:

1. **AI reads** an official programme page from any country and drafts the eligibility rules. Every rule must quote the page.
2. **Code checks every quote** word for word against the page. A made-up quote is blocked and can never go live.
3. **A person approves.** A reviewer ticks the rules that are right and unticks optional or wrong ones. Only ticked, verified rules go live.
4. **Everyone is re-checked automatically.** People who may now qualify get an alert. People who may lose support are held until a reviewer releases the news. People who opt into email updates can receive those approved alerts by email too.
5. **The applicant approves** their own packet before using it, and submits it themselves on the official site.

The AI drafts and explains. It never decides who qualifies, and it never tells anyone bad news on its own.

## Two views

| View | Who | What they do |
|---|---|---|
| **Citizen view** | Anyone, no sign-up | Answer a short form built from the questions the approved rules ask, see programmes they qualify for with the official quote behind every rule, prepare and approve a packet, read alerts, edit or delete their answers |
| **Verification Desk** (admin) | The admin, via the Admin button in the top bar | Paste any official link and watch the pipeline run, review AI drafts with receipts highlighted in the page text, approve or reject, release or hold bad news, re-read watched pages, audit who did what |

Each view is one page with tabs. A citizen's answers are saved in the database and linked to their browser by a signed cookie. The admin credentials come from the environment (`ADMIN_USERNAME`, `ADMIN_PASSWORD`); repeated wrong passwords are locked out for a minute. Every desk action checks the admin session on the server, and nobody can touch another person's packet.

## The pipeline

```
fetch page -> AI drafts rules -> receipt check -> impact preview -> reviewer decides
           -> re-check everyone -> good news sent, bad news held for a person
```

Every step is timed and logged with its actor (AI, code or person) and shown live on the desk. It runs from the desk, from the built-in watcher every 30 minutes, or from n8n (see `n8n/`).

## Stack

- Python, FastAPI, Jinja2, SQLAlchemy (SQLite or Postgres)
- Groq (`openai/gpt-oss-120b`) for drafting rules from official pages, with a rotating key pool and a pattern-based fallback when the AI is unavailable
- Deterministic rule engine, receipt check, impact diff and approval gate in `app/engine/`
- Neon Postgres in production (pooled connection for the app, direct connection for creating tables); SQLite locally
- APScheduler watcher; optional n8n workflows

The starting catalogue (`app/catalogue.json`) holds real programmes from Pakistan, the UK, Canada and the US. Their rules were drafted by the same pipeline from the live official pages, receipt-checked, and approved by the Entitle team.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate        # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # then fill in the values below
uvicorn app.main:app --port 8000
```

Set in `.env`:

- `GROQ_API_KEYS`: one or more Groq keys, comma-separated
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_NAME`: the Verification Desk sign-in. It stays off while the password is empty
- `DATABASE_URL`, `DATABASE_URL_UNPOOLED`: Neon's pooled and direct connection strings (`neon env pull` writes both). Leave them out to use SQLite
- `BASE_URL`: the public address of the app, for example `http://127.0.0.1:8000`
- `SECRET_KEY`: a long random string
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, `SMTP_USE_TLS`: SMTP delivery for profile email updates. Leave SMTP unset to keep using in-app alerts only. Users choose email updates and save their address in their profile; new-opportunity emails go out after rules are approved, and potentially negative updates go out only after a reviewer releases them.

## Deploy (Alternate Clouds)

```bash
docker build -t entitle .
docker run --rm -p 3000:3000 --env-file .env -e PORT=3000 entitle
```

The container binds Uvicorn to `0.0.0.0:$PORT`, exposes port `3000`, and reports healthy at `/healthz` after it can reach the database. In Alternate Clouds, set the service's internal port and `PORT` to `3000`, set `BASE_URL` to the public HTTPS URL, then Rebuild and Deploy. A Git push alone does not publish the new image.

Set `SECRET_KEY` to a unique random value of at least 32 characters and set a strong `ADMIN_PASSWORD` before making the service public. The app fails startup with a clear log message if the HTTPS deployment still has a placeholder session key. The Verification Desk stays disabled when `ADMIN_PASSWORD` is empty. `GROQ_API_KEYS` is optional for startup; the app has a local drafting fallback when no Groq key is configured. Do not put `.env` or local database files in the image; `.dockerignore` excludes them.

Use a managed PostgreSQL database for deployment and set `DATABASE_URL` to its application/pool URL. If the provider gives you a separate direct URL for schema changes, set `DATABASE_URL_UNPOOLED` too. The sample SQLite URL is only for local use: container files are temporary and do not survive a rebuild. SMTP and the app-to-n8n integration are optional. If you deploy n8n as a separate service, follow its own guide for `N8N_ENCRYPTION_KEY` and `WEBHOOK_URL`; those are not Entitle app variables.

After deploy, check the container logs for `Application startup complete`, then open `https://<your-service>/healthz` and the home page. A non-200 health response means the app cannot reach its configured database; a connection error at startup usually means the database URL, network access, or schema connection settings need correction. For a 502, verify that the dashboard target port and `PORT` are both `3000`, then rebuild and deploy the latest image.

If the Alternate Clouds CLI reports `no active leases`, update it with `npm i -g @alternatefutures/acc` and retry the deployment. For a successful build followed by a startup crash, inspect the Logs tab for the first Python error; check required secrets and database connectivity before changing application code.

## Tests

```bash
pytest
```

The tests cover both views, the question form, admin sign-in and lockout, ownership checks, the full pipeline from link to alert, a made-up quote being blocked, bad news being held until release, and the rule engine, receipt check, impact diff and approval gate.

## Licence

Hackathon project for Agentika 2.0. Information only, not legal advice.
