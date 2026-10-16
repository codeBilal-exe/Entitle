# RightPath

Human-supervised entitlement automation. RightPath watches programme notices, drafts rule updates with source quotes, and notifies the people affected — with humans approving every consequential step.

> Information only. Not legal or medical advice. Demo data is synthetic. Unverified programmes are labelled **DEMO sample**.

## Stack

- Python 3.12, FastAPI, Jinja2, SQLAlchemy, SQLite
- Deterministic rule engine (eligibility is never decided by the LLM)
- Optional n8n workflows for scheduled watching and fan-out
- Groq for drafting / plain-language explanation when configured
- SMTP for consented application packets

## Quick start (local)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # or: cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000

### Demo accounts

Password for all seeded users: `demo1234`

| Email | Role |
|---|---|
| `amina@demo.rightpath` | applicant |
| `bilal@demo.rightpath` | applicant |
| `rao@demo.rightpath` | applicant |
| `nav@demo.rightpath` | navigator |
| `curator@demo.rightpath` | curator |
| `admin@demo.rightpath` | admin |

## Tests

```bash
pytest
```

Critical seams: `RuleEngine`, `QuoteGate`, `CaseImpact` / fan-out routing, `ApprovalGate`.

## Docker

```bash
docker build -t rightpath-core .
docker run --rm -p 8000:8000 --env-file .env rightpath-core
```

On Alternate Clouds: set Variables first, then **Rebuild**, then **Deploy**. `PORT` must match the container (default `8000`).

## Hero demo (Pulse)

1. Sign in as `curator@demo.rightpath`
2. Open **Curator** → edit the DEMO notice age band (`18 and 45` → `18 and 35`) → Save
3. Click **Check sources now** (or **Run ingest now**) → confirm QuoteGate → **Approve and fan out**
4. Open **Navigator** — Amina’s lost eligibility is waiting for a human
5. Open **Timeline** — Human Decision cards are marked
6. As an applicant, open **Alerts**, prepare a packet, approve the exact payload, then send

Core also runs an in-process source watcher every `WATCHER_INTERVAL_SECONDS` (default 120). n8n workflows in `n8n/` call the same `/api/internal/*` hooks.

### Curator controls

- **Gold-set score** on the curator desk (honest `N of M` before curator edits)
- **Reset demo** restores the DEMO notice and live rules to baseline
- **Kill switch** blocks outbound sends and builds a SAMPLE ONLY manual pack ZIP
- Optional `N8N_BASE_URL` — Core notifies n8n webhooks after approve/send

### Internal API (local)

Header: `x-rightpath-secret: dev-shared-secret` (or your `N8N_SHARED_SECRET`)

```bash
curl -X POST "http://127.0.0.1:8000/api/internal/check-sources?auto_ingest=true" ^
  -H "x-rightpath-secret: dev-shared-secret"
```

## Project layout

```
app/
  engine/          # RuleEngine, QuoteGate, CaseImpact, ApprovalGate
  services/        # questions, mailer, timeline
  templates/       # server-rendered UI
  static/
n8n/               # exported workflow JSON (add after building in n8n)
tests/
docs/              # planning and event reference material
```

## Environment

See `.env.example`. Never commit real API keys or passwords.

## Credits

- FastAPI, SQLAlchemy, Jinja2, uvicorn, passlib, cryptography, APScheduler, httpx, pydantic
- Optional: n8n, Groq API

## Licence

Demo project for Agentika 2.0 / NaSCon 2026.
