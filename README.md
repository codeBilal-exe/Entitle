# RightPath

RightPath watches real public programme notices (scholarships, jobs, health cover, cash support). When a notice changes, code re-checks who is affected. A person approves anything that changes a rule or takes support away. The applicant approves anything sent out. The language model may draft and explain. It never decides eligibility and it never sends on its own.

A person and a model work together. That shows up on the sign-in page, the home page, and every approval step.

## Three human stops

1. A person approves a rule change, and only if every quote is in the notice.
2. A person releases bad news. A loss of support stays held until then.
3. The applicant approves the exact packet before it is sent.

## Three roles

These are roles on the account, not a view switch.

| Role | Who | What they can do |
|---|---|---|
| Citizen | Signs up on the sign-in page | Own profile, matching programmes, own application, own alerts |
| Staff | Two accounts from the environment | Watch sources, approve or reject a draft, release or hold bad news |
| Admin | One account from the environment | Staff work, plus sources, the sending switch, and the activity log |

Staff and admin see a name and the eligibility change when they review a loss. They cannot open or edit a citizen's private profile. A citizen cannot open staff or admin tools. Hiding a link is not the check — the server refuses the request.

Passwords are hashed with bcrypt. Accounts, profiles, applications, and alerts live in the local SQLite file `data/rightpath.db`.

## Sign-in

The sign-in page is an empty email and password form, plus Sign up. No account is filled in. No premade citizen profiles.

After sign-up, the citizen lands on an empty profile and enters age, education, and any optional answers themselves.

Staff and admin passwords are set in the environment (see `.env.example`). They are not listed on the sign-in page.

## Programmes

The catalogue is official public pages, including HEC scholarships, Benazir Income Support / Kafaalat, PEEF, NAVTTC, Sehat Sahulat, the Ministry of Human Rights, the Prime Minister's Youth Programme, Pakistan Bait-ul-Mal, and provincial literacy departments.

A rule or quota is shown only as a verbatim quote from a page RightPath fetched, after a person approves the draft. If a number is not on that page, it is not shown. If a page cannot be read, the source is marked unreachable.

## Automation

A timer re-reads sources. **Check sources now** does the same thing. On a real text change, RightPath drafts a rule update, runs the quote check, and leaves the draft for staff. After approval, stored profiles are re-checked. Someone who newly qualifies gets an alert. Someone who may lose support is held until staff release it. Deadline reminders keep running. The app keeps working if n8n is not running.

## Alerts

Each alert names the programme, what changed, what it means, the quote, whether a person released it, the date, and one next step. "You may now qualify" and "You may no longer qualify" are separate. The navigation shows an unread count. Opening an alert marks it read.

## Stack

- Python, FastAPI, Jinja2, SQLAlchemy, SQLite
- Deterministic rule engine (eligibility is never decided by the model)
- Quote check before a rule can be approved
- Approval gate before a packet can be sent
- Optional n8n workflows and optional Groq drafting

## Quick start

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000 and sign up. To use staff or admin, set the emails and passwords in `.env` and restart.

## Tests

```bash
pytest
```

Critical seams: `RuleEngine`, `QuoteGate`, `CaseImpact`, `ApprovalGate`, plus role and ownership checks.

## Docker

```bash
docker build -t rightpath-core .
docker run --rm -p 8000:8000 --env-file .env rightpath-core
```

## Internal API

Header: `x-rightpath-secret` (your `N8N_SHARED_SECRET`).

```bash
curl -X POST "http://127.0.0.1:8000/api/internal/check-sources?auto_ingest=true" ^
  -H "x-rightpath-secret: dev-shared-secret"
```

## Layout

```
app/
  engine/          # RuleEngine, QuoteGate, CaseImpact, ApprovalGate
  services/        # watcher, deadlines, mail
  templates/
n8n/               # optional workflow JSON
tests/
docs/
```

## Licence

Hackathon project. Information only. Not legal or medical advice.
