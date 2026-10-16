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
2. Open **Curator** → edit the DEMO notice age band (for example change `18 and 45` to `18 and 35`) → Save
3. **Run ingest now** → confirm QuoteGate → **Approve and fan out**
4. Open **Navigator** — Amina’s lost eligibility is waiting for a human
5. Open **Timeline** — Human Decision cards are marked
6. As an applicant, prepare a packet, approve the exact payload, then send

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
