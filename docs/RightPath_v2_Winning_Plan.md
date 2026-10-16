# RightPath v2: Living Entitlements

**Audited, refined and rebuilt for Agentika 2.0 (NaSCon 2026)**
Theme: Human + AI: Better Together. Team of 2. Deploy on Alternate Clouds.
Deadline: 12:45 PM PKT, 17 October 2026. Top 10 slides PDF due before 4:00 PM. Final pitch: **5 minutes, hard stop** (the handbook says 6, the organizers' latest message says exactly 5; plan for 5).

---

## PART 0. THE AUDIT (read this first)

This audit checks the previous RightPath draft against the handbook, the rubric, the troubleshooting guide and the organizers' latest message. It also asks what a skeptical judge will say.

### What the old draft got right (keep)

1. Rules are code, the AI only explains and drafts. Judges respect this.
2. AI-drafted rules must carry source quotes, checked by code, then approved by a human curator.
3. Consent-gated sending with approval hash, and privacy-by-design (minimum data, delete button).
4. Honest limits: no CAPTCHA bypass, no real portal submission, synthetic data only.
5. Clear rules-compliance table and submission checklist.

### Brutal findings

| # | Finding | Severity | Why a judge will care | Fix in v2 |
|---|---|---|---|---|
| 1 | **Scope is far too big for about 20 hours.** 15 must-build features, 5 agents, 3 pipelines, 4 roles, a mock portal, helper network, MCP server. | Critical | Reliability is 25 points. One crash in the live demo costs more than any missing feature. | Cut to one hero flow plus two supporting flows. Mock portal, Playwright, helper verification assistant and OCR are cut. |
| 2 | **The automation is mostly request/response.** A user clicks, the app responds. Nothing happens without a click. | Critical | "Automation depth" (15) and the whole hackathon premise is automation. A form app with an LLM is not automation. | v2 is **event- and time-driven**: a source watcher, impact fan-out, deadline guardian and approval-gated sending run on their own, orchestrated by **n8n**. |
| 3 | **The mock portal automates a website we built ourselves.** | High | A sharp judge will say: "You automated your own fake page." It also eats hours. | Cut. Replace with something real: real email with attachments, plus a "Your turn" handover checklist with prefilled data. |
| 4 | **Own MCP server consumed by our own orchestrator** looks decorative. | High | Judges can tell MCP used to tick a box. | MCP stays but has a real job: the **n8n AI agent calls our guarded tools** through MCP. If that fails on the platform, plain HTTP nodes call the same endpoints. |
| 5 | **No n8n at all**, despite the user's priority and a judging line for "automation tools and MCP". | High | The best-supported stack on Alternate Clouds is n8n, and visible workflow canvases demo well. | Hybrid: custom FastAPI "brain" plus n8n "nervous system". The submission allows "n8n, custom code or both". |
| 6 | **Category is crowded.** Benefit calculators and rules-as-code projects exist. The old plan admitted this. | High | Creativity is 15 points. "Another benefit finder" scores low. | Reframe the product around the real unsolved problem: **rules change and nobody tells the people affected**. We call this *living entitlements*. |
| 7 | **Quote check proves the quote exists, not that the rule means what the AI says.** | Medium | A judge will ask "what if the AI picks a real sentence but the wrong condition?" | Say so openly. Mitigate with the curator step, a small gold-set accuracy test we actually run, and show the number honestly. |
| 8 | **Data verification load** (15 programs, 3 countries) is heavy, and one wrong rule destroys credibility. | Medium | Wrong eligibility on real programs is the fastest way to lose trust. | 8 to 10 programs, 2 countries. Anything unverified is labeled **DEMO sample**. |
| 9 | **Self-estimated score of 76 to 87 was optimistic.** | Medium | False confidence leads to bad trade-offs. | Realistic estimate in Part 12. |
| 10 | **Demo depends on live LLM calls and live email.** | Medium | Network or rate-limit failure in front of judges. | Cached-run mode (clearly labeled), recorded fallback video, pre-signed-in tabs. |
| 11 | **Helper network is a second product.** | Medium | It splits the story. | Reduced to "referral with consent" using 3 DEMO helpers. It is a Should-have, not core. |
| 12 | **Sensitive groups (disabled, migrants, women).** | Medium | Judges worry about harm and privacy. | Sensitive answers optional, no immigration status, IDs never go through n8n, synthetic data only. |
| 13 | **5 versus 6 minute pitch conflict.** | Low | Overrunning a "not a second more" slot is a visible failure. | Rehearse a 4:30 version. |
| 14 | **Two services double the deployment risk** (n8n plus Core). | Medium (new risk created by v2) | The troubleshooting guide shows port, variable and rebuild mistakes are the common failures. | Deploy both in hour 1. Core works standalone if n8n is down. Export n8n workflows as JSON backup. |

### The one-paragraph verdict

The old RightPath was a competent, honest *application*. It was not yet a strong *automation* project, and its differentiator (rule drafting with quotes) was invisible unless the demo hit it early. v2 keeps every good safety idea and puts the automation where judges will see it: **a rule changes on an official page, and within minutes the right people are told, with humans approving every consequential step.**

---

## PART 1. NAME, PITCH, PROMISE

- **Name:** RightPath
- **One-line pitch:** RightPath keeps people's entitlements *alive*: it watches the official rules, tells people when something changes for them, prepares their application, and hands every important decision to a human.
- **Tagline:** Rules change. Your rights shouldn't slip away.
- **Product category:** Human-supervised entitlement automation.

---

## PART 2. THE PROBLEM

People who are older, disabled, migrants, women, minorities or on low incomes often miss support they are entitled to (scholarships, job programs, health support, income support, language classes, legal aid). Researchers call it *non-take-up*.

Four failures cause it, and existing tools fix only the first:

1. **Finding:** rules are scattered and hard to read.
2. **Preparing:** people don't know which documents are needed.
3. **Acting:** a missing paper or missed deadline ends the application.
4. **Keeping up (nobody solves this):** eligibility rules, deadlines and forms change, but static calculators go stale and nobody tells the people affected.

> **Before submitting:** add two sourced facts about non-take-up from a trusted organization (OECD, World Bank, ILO, a national statistics office). Do not invent numbers. I could not verify specific statistics for you.
> Fact 1: [add with source]
> Fact 2: [add with source]

**Problem statement for the PDF (2 to 3 lines, rewrite in your own words):**
Across the world, eligible people miss support because rules are scattered, hard to read and constantly changing, and nobody tells them when a rule changes in their favor or a deadline moves. The human helpers who could guide them are overloaded.

---

## PART 3. THE CORE IDEA: THREE LOOPS

**Loop 1: Find and prepare (the user loop).**
The person answers as few questions as possible. A deterministic engine returns entitlements as Eligible, Likely or Not eligible, each with a plain reason and a source quote. RightPath prepares a document checklist and an application packet.

**Loop 2: Keep rules alive (the curator loop).**
An n8n workflow watches official notice pages. When a page changes, the AI drafts a new rule version with source quotes, code verifies each quote, and a human curator approves. Nothing goes live without that approval.

**Loop 3: Keep cases moving (the follow-through loop).**
When a rule is approved, RightPath re-evaluates every stored case, finds who is affected, and prepares notifications. Bad news ("you may no longer qualify") goes to a navigator first. A deadline guardian watches open cases and nudges, escalates or proposes a helper referral. Sending anything outside the app always needs the person's approval.

### Why this is not a generic benefit finder (honest)

| Typical benefit finder | RightPath |
|---|---|
| Static rules, updated by hand | Rules watched and updated by a human-approved pipeline |
| Answers when you ask | Tells you when something changes for you |
| Ends at "you may qualify" | Prepares, gets approval, sends, tracks |
| One country, one team | Country Rule Packs that volunteers can extend with AI help |
| AI decides or hides reasoning | Code decides, AI explains, every rule shows a source quote |

**Honest note:** benefit calculators and "rules as code" projects exist. Our edge is the *living* part and the human-gated follow-through. If the demo does not show a rule change flowing to affected people, this will look generic. **That moment is the demo.**

---

## PART 4. HUMAN + AI: WHERE THE HUMAN COMES IN AND WHY

| Human step | Who | Why it must stay human |
|---|---|---|
| Approve every AI-drafted rule change | Curator | Rules affect people's rights. AI can misread legal text. |
| Review "you may no longer qualify" messages before they are sent | Navigator | Bad news about someone's support needs judgment and care. |
| Approve exactly what is sent, and to whom | Applicant | Their identity, documents and consent. |
| Complete CAPTCHA, one-time codes, identity checks, payment | Applicant | Identity and money stay human. |
| Decide whether to take a case or give advice | Helper or lawyer | The app never gives legal advice. |
| Verify a helper organization before it is shown | Admin | Legitimacy decisions affect vulnerable people. |

**AI does:** reads long notices, drafts rules with quotes, explains results in plain language, writes application text, prioritizes follow-ups among a small set of safe actions.
**AI never:** decides eligibility, gives legal or medical advice, solves CAPTCHAs, sends without approval, ranks helpers by payment, or sees immigration status.

Each human step appears as a visible **Human Decision** card in the live timeline and in the video.

---

## PART 5. ARCHITECTURE

Two services on Alternate Clouds:

```
                 +------------------------------+
  Official       |  n8n  (service 1)            |
  notice pages-->|  W1 Source Watcher           |
                 |  W2 Impact Fan-out           |
                 |  W3 Approved Send            |
                 |  W4 Deadline Guardian        |
                 |  W5 Referral                 |
                 |  W6 Housekeeping             |
                 +---------+--------+-----------+
                           |  HTTP / MCP (IDs only, shared secret)
                           v
                 +------------------------------+
                 |  RightPath Core (service 2)  |
                 |  FastAPI + Jinja/HTMX UI     |
                 |  Rule engine (code)          |
                 |  Question engine (code)      |
                 |  Ingestion + quote check     |
                 |  Explainer / Mapper (LLM)    |
                 |  Encrypted vault (SQLite)    |
                 |  Email sender, state machine |
                 |  MCP server (guarded tools)  |
                 +------------------------------+
                           |
                 Groq LLM API, SMTP/email API
```

### The key design rule: **n8n passes IDs, not personal data**

n8n stores execution data, and the documents and profiles are sensitive. So n8n only sees case IDs and status. The Core holds profiles and documents and does the sending. Set n8n to avoid saving execution payloads (verify the exact setting names in your n8n version).

### Core works without n8n

The eligibility flow (wizard, results, application prep, send) runs in Core alone. If n8n has a bad moment, the user loop still works. Loops 2 and 3 are the automation showcase.

---

## PART 6. ROLES: WHAT n8n, MCP AND FASTN DO

### n8n (the orchestrator)

n8n runs everything that is **time-driven, event-driven or multi-step with waiting**: scheduled watching, fan-out over many cases, retries with backoff, escalation timers, notifications. That is exactly what n8n is good at, and judges can see the workflow canvas.

### MCP (the safe tool layer)

Core exposes a small set of **guarded tools** through MCP. The n8n AI Agent node uses them in the Deadline Guardian. Each tool enforces its own guard in code (state check, approval hash, consent flag), so the AI cannot bypass it even if it tries.

| MCP tool | What it does | Guard in code |
|---|---|---|
| `list_due_cases` | Cases with approaching deadlines or no progress | Read-only |
| `get_case_summary` | Case status, missing documents (no document contents) | Read-only, IDs only |
| `send_reminder` | Reminder to the applicant | Rate limit, consent to reminders |
| `request_navigator_review` | Opens a review task | None needed |
| `propose_helper_referral` | Creates a referral *proposal* | Cannot send; needs applicant approval |
| `log_event` | Writes a timeline event | None needed |

**Honest note:** if the n8n MCP client node does not work in the deployed template within an hour, switch to plain HTTP Request nodes calling the same endpoints. The logic and guards do not change. Do not burn the night on it.

### FastN MCP

I cannot verify what the FastN MCP exposes or how it deploys, so this plan does not depend on it. If it gives you a ready connector that saves real time (for example calendar or sheets), you may add it. Claiming it in the PDF without using it would be worse than leaving it out.

### Custom code (Core)

Everything that must be correct or private: the rule engine, question selection, quote check, vault, approvals, state machine, sending.

---

## PART 7. AUTOMATION FEATURES (EVERY WORKFLOW, A TO Z)

### W1. Source Watcher (scheduled)

- **Trigger:** Cron (every 15 minutes during the demo; hourly otherwise) plus a **"Check now"** webhook button for the live demo.
- **Steps:** get the watched-source list from Core, fetch each page, send text to Core's `/ingest/check` which stores a content hash and compares with the last one. If changed, Core runs the Ingestion Agent: draft rule version, quote check, diff against the live version.
- **Human gate:** curator gets a review task (email or Telegram ping). Nothing goes live until approved.
- **Failure handling:** fetch fails, so retry 3 times then mark the source "unreachable" (shown on the curator screen). A changed page that yields no changed conditions is logged as "no rule impact".
- **Honest limits:** scanned PDFs and messy pages are hard. Demo with text pages. One real public notice URL is watched as proof it works on real pages, plus one DEMO source we control (clearly labeled) so the rule change can be shown on cue.

### W2. Impact Fan-out (event: curator approves a rule change)

- **Trigger:** Core calls the n8n webhook with the rule-change ID.
- **Steps:** Core computes (in code) which cases flip status: newly eligible, newly not eligible, deadline moved, documents newly required. n8n loops over affected case IDs and requests an Explainer message for each.
- **Human gate:** any change that flips someone to **Not eligible** or removes support goes to the **navigator review queue** before the user hears it. Good news is sent automatically (to a consented email only).
- **Output:** each notification is logged with the reason and source quote.

### W3. Approved Send (event: applicant approves)

- **Trigger:** applicant approves the exact packet (approval stores a payload hash).
- **Steps:** n8n calls Core `send_packet(application_id)`. Core checks state APPROVED and the hash, then sends the email with attachments. n8n records the result, schedules a follow-up check, and retries on failure.
- **Failure handling:** 3 retries with backoff, then FAILED plus a **Manual pack** (ZIP of documents and a checklist) and a notification to the applicant.
- **Proof stored:** message ID, time, attachment list (not contents).

### W4. Deadline Guardian (scheduled, with an AI agent)

- **Trigger:** Cron (hourly; demo button for instant run).
- **Steps:** `list_due_cases`. For each, the n8n AI Agent chooses **one of four safe actions**: remind, ask for a missing document, request navigator review, or propose a helper referral.
- **Human gate:** anything that shares data with a third party is only a *proposal* until the applicant approves.
- **Limit:** simple cases use deterministic rules (for example, 3 days left means remind), and the agent handles only ambiguous ones. This keeps behavior predictable.

### W5. Helper Referral (event: applicant approves referral)

- **Trigger:** applicant approves a referral screen that shows exactly what is shared.
- **Steps:** n8n triggers Core to send the referral packet to the helper's intake email, logs it, and schedules a "did the helper respond?" check after a set time.
- **Scope:** 3 fictional DEMO helper organizations, clearly labeled. No abuse-survivor services in the demo (they need special safety design). Listing is never an endorsement and never ranked by payment.

### W6. Housekeeping (scheduled)

- **Purge expired documents** (default 24 hours after the last application, 7 days idle maximum) and write an audit line (no contents).
- **Kill switch:** an admin toggle that makes every sending tool refuse to run.

### Cross-cutting automation features

- **Live timeline:** every agent step, tool call and human decision appears in real time.
- **Idempotency:** one application per user and program. A second click returns the existing run.
- **Audit log:** who, what, when. Never document contents, file names or ID numbers.
- **Replay mode:** a cached run of the rule-change scenario, labeled "REPLAY", for when the network fails.

---

## PART 8. FEATURE SCOPE

### Must build (the hero flow)

1. Demo accounts with 3 roles: applicant, navigator, curator/admin (role switcher for the demo).
2. Rule Pack engine with Eligible / Likely / Not eligible, plain reasons and source quotes.
3. 8 to 10 programs in 2 countries, each with source link and last-verified date. Unverified ones are labeled **DEMO sample**.
4. Adaptive wizard (fewest questions, sensitive ones optional).
5. Ingestion Agent with code quote check and curator split screen.
6. **W1 Source Watcher** and **W2 Impact Fan-out** in n8n (the demo hero).
7. Approval screen showing exactly what is sent, with payload hash.
8. **W3 Approved Send** with a real email to a demo inbox.
9. Live timeline with Human Decision cards.
10. Privacy center: see what is stored, delete everything.

### Should build (only after the must list works)

11. **W4 Deadline Guardian** with MCP tools and the AI agent.
12. Document checklist and encrypted vault with SAMPLE ONLY files.
13. Navigator caseload screen.
14. **W5 Referral** with 3 DEMO helpers.
15. Manual pack ZIP.

### Will not build (and we say so)

CAPTCHA solving, auto-submission to real portals, identity checks against government databases, storing real IDs or immigration status, payments, OCR, Playwright, mock portal, other languages (English only per event rules), WhatsApp or voice, mobile apps. These go on the roadmap slide.

---

## PART 9. CORE ENGINE DETAILS

### Rule Pack format

Every condition carries a quote from the official notice.

```json
{
  "id": "demo_xx_work_01",
  "version": 3,
  "country": "XX",
  "domain": "work",
  "title": "DEMO: Inclusive Hiring Programme (sample)",
  "provider": "Sample Public Body",
  "source_url": "https://example.org/notice",
  "last_verified": "2026-10-16",
  "deadline": "2026-12-01",
  "channel": "email",
  "apply_email": "intake@example.org",
  "conditions": [
    {"id": "c1", "attr": "disability", "op": "is_true",
     "source_quote": "persons with disabilities"},
    {"id": "c2", "attr": "age", "op": "between", "value": [18, 45],
     "source_quote": "aged between 18 and 45 years"}
  ],
  "required_docs": ["id_document", "disability_certificate", "education_certificate"],
  "form_schema": {"fields": ["full_name", "age", "education_level", "contact_email"]}
}
```

Allowed ops: `eq`, `in`, `gte`, `lte`, `between`, `is_true`, `any_of`.
Each condition evaluates to **true, false or unknown**.

- **Eligible:** all true.
- **Likely:** none false, some unknown (the reply names the missing answer).
- **Not eligible:** at least one false (shows which rule and its quote).

### Rule diff (what makes W2 possible)

Comparing version N and N+1 is plain code: changed values, added or removed conditions, moved deadline, changed documents. The diff is shown to the curator and drives the fan-out.

### Fewest-questions engine

```
for each unanswered attribute:
    impact = number of programs whose result is "unknown" and depend on it
    cost   = 0 normal, penalty for sensitive
    score  = impact - cost
ask the highest score
```

Sensitive questions have "Prefer not to say" and show "Answering may unlock N programs". The wizard can stop any time. Plain code, easy to test.

### Ingestion Agent and its honest accuracy

1. LLM drafts a Rule Pack from pasted notice text. Prompt rules: use only the text, copy exact sentences into `source_quote`, `null` if not stated, never guess.
2. **Code check:** each quote must appear word for word in the notice, otherwise the condition is flagged red.
3. Curator sees the notice with quotes highlighted next to the draft rules and the diff against the live version.
4. **Gold-set test (do this, it is a differentiator):** prepare 5 to 8 notices where you wrote the correct rules by hand. Run the agent and report the real score in the video and PDF ("X of Y conditions correct before curator edits"). Report whatever number you get. An honest 80% with a human catching the rest is more convincing than a claimed 100%.
5. **Known limit:** the quote check catches invented quotes, not wrong readings of real sentences. That is why the curator exists.

---

## PART 10. DATA MODEL

| Table | Main fields |
|---|---|
| users | id, role, email, password_hash |
| profiles | user_id, attributes (JSON), sensitive_keys, consent_flags |
| documents | id, user_id, doc_type, storage_key, checksum, expires_at (encrypted at rest) |
| programs | id, country, domain, current_version_id, status |
| program_versions | id, program_id, version, rules (JSON), source_url, last_verified, approved_by, approved_at |
| sources | id, program_id, url, last_hash, last_checked, status |
| ingestion_jobs | id, source_id, notice_text, draft (JSON), quote_check (JSON), diff (JSON), status, reviewed_by |
| applications | id, user_id, program_id, state, idempotency_key, approval_hash |
| approvals | id, application_id, payload_hash, approved_at |
| notifications | id, user_id, kind, rule_change_id, status (pending_review, approved, sent), reviewed_by |
| referrals | id, application_id, helper_id, packet_hash, status |
| events | id, case_id, stage, status, detail, human_decision (bool), at |
| audit_log | id, actor, action, target, at |

Data rules: never store immigration status, never store real ID numbers, never log document contents or file names.

---

## PART 11. PRIVACY AND SECURITY

- Minimum data, sensitive answers optional and explained.
- Documents encrypted (AES-256-GCM via `cryptography`), key in an environment variable.
- n8n receives IDs only. Disable saving of execution payloads where the setting exists.
- Signed session cookies, hashed passwords, role-limited pages.
- Auto-delete job plus a "Delete everything" button.
- "Information, not legal or medical advice" on screen.
- All demo documents are generated and watermarked **SAMPLE ONLY**. Never create realistic fake IDs.
- Before any real launch: data-protection review per country, user testing with the communities served, accessibility testing with real users.

---

## PART 12. HONEST RUBRIC ESTIMATE

My earlier draft estimated 76 to 87. That was optimistic. This is more realistic *if the hero flow works live*.

| Criterion | Pts | What earns it | Realistic range |
|---|---|---|---|
| Technical execution and reliability | 25 | Deterministic engine, guards, retries, tested, deployed early. Loses points if n8n and Core integration flakes. | 15 to 20 |
| Usefulness and real-world impact | 20 | Real, international problem, living rules, navigator view, two sourced facts | 13 to 17 |
| Theme alignment | 15 | Six human decisions visible as cards; human owns rules, bad news, consent | 12 to 14 |
| Creativity and uniqueness | 15 | Living rules, quote-verified AI drafting. Category is crowded. | 9 to 12 |
| Automation depth and integration | 15 | n8n event/time-driven workflows, MCP tools, LLM, email, fan-out | 10 to 13 |
| User experience and presentation | 10 | Clean UI, strong video, rehearsed 5 minutes | 6 to 8 |
| **Total** | 100 | | **about 65 to 84** |

This is a credible top-10 candidate. It wins only if the live demo is flawless, the pitch is crisp, and another team does not have a more novel idea. **No plan guarantees a win.**

---

## PART 13. SDG ALIGNMENT

| SDG | Target | How RightPath helps |
|---|---|---|
| 1 No Poverty | 1.3 social protection | Helps people find and claim support |
| 3 Good Health | 3.8 access to health services | Surfaces health coverage programs |
| 4 Quality Education | 4.5, 4.b scholarships | Surfaces scholarships and admission support |
| 8 Decent Work | 8.5 | Surfaces inclusive job programs |
| 10 Reduced Inequalities | 10.2, 10.3 | Closes the gap between rights on paper and in practice |
| 16 Strong Institutions | 16.3, 16.10 | Legal aid referrals, readable public information |
| 17 Partnerships | 17.17 | Helper and NGO network |

Measures (demo values only, never claim real results): entitlements surfaced per person, documents ready, applications completed, **time from rule change to affected person informed**.

---

## PART 14. RULES AND RESTRICTIONS CHECK

| Rule | How we comply |
|---|---|
| Deploy on Alternate Clouds | Core and n8n both deployed there from hour 1 |
| No local-only or outside hosting | Nothing hosted elsewhere. Watched sources are external *inputs*, not hosting. |
| English only | English UI, pitch, video, chat |
| LinkedIn post by us | We write it ourselves. Grammar tools only. One posts, the other reshares. |
| Demo accounts only | Seeded demo users listed in the PDF |
| No keys in repo, video, screenshots | Environment variables, `.env` in `.gitignore`, check every screenshot |
| Credit third-party code | Credits in README |
| No changes after 12:45 PM | Feature freeze at hour 19 |
| Keep deployment running until closing | Do not stop or delete either service |
| Judges can open every link | Test each in a private window |
| Real-world safety | Information only, no CAPTCHA bypass, synthetic data only |

---

## PART 15. DEPLOYMENT ON ALTERNATE CLOUDS

### Hour-1 checklist (before any feature)

1. Sign in at clouds.alternatefutures.ai and confirm event credits with organizers.
2. Deploy the **n8n template** and a **hello-world FastAPI container**. Open both public URLs.
3. Ask technical support right away:
   - Can the services reach each other and the outside (LLM API, SMTP or HTTPS email, public notice pages)?
   - Is disk permanent or does it reset on redeploy? (seed on boot either way)
   - Does the n8n template include the MCP Client Tool node and which version?
   - Memory and CPU limits?
4. Join the Alternate Futures Discord. Display name: `Your First Name [Participant/Team Name]`. Post progress in #hackathon-build-in-public.

### n8n required variables (from the troubleshooting guide)

```
N8N_ENCRYPTION_KEY=<32 characters; generate once, never change>
WEBHOOK_URL=https://<your-n8n-service-name>-app.alternatefutures.ai
```

Generate the key: PowerShell `[System.Guid]::NewGuid().ToString("N")`, or Mac/Linux `openssl rand -hex 16`. **Changing the key later means n8n cannot read saved credentials.** Make the service name exactly match the URL.

### Core Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Core environment variables (dashboard only, never in code)

```
SECRET_KEY=
VAULT_KEY=                 # 32 random bytes, base64
GROQ_API_KEY=
LLM_MODEL=                 # check the Groq console for a current tool-calling model
MAIL_HOST= MAIL_PORT= MAIL_USER= MAIL_PASS= MAIL_FROM=
DEMO_RECIPIENT=            # your own test inbox
N8N_BASE_URL=              # your n8n public URL
N8N_SHARED_SECRET=         # header secret between n8n and Core
BASE_URL=
ADMIN_PASSWORD=            # demo account only
PORT=8000
```

### The golden rule

Set variables first, then **Rebuild**, then **Deploy**. Building and going live are two separate steps.

| If you see | Do this |
|---|---|
| 502 Bad Gateway | PORT in the dashboard must match the Dockerfile and uvicorn (8000) |
| Pushed to GitHub, app unchanged | Source tab, Rebuild, wait for success, then Deploy |
| Crash on startup (KeyError) | A variable is missing. Add it in the Variables tab, Rebuild, Deploy |
| `Error: no active leases found` | `npm i -g @alternatefutures/acc`, close the failed service with `acc services close <id>`, rerun |
| n8n credentials or webhooks broken | Check `N8N_ENCRYPTION_KEY` and `WEBHOOK_URL` |
| Anything else | Read the Logs tab first. Healthy logs show "Application startup complete" |

Asking for help: #support on Discord, in English, with repo link, the error pasted as text in a code block, and your steps. Remove keys and passwords first.

### Startup behavior (Core)

On every start create tables if missing, load seed data (programs, demo sources, helpers, users, SAMPLE documents) if missing, and start the scheduler. This keeps the demo alive if the disk resets.

### Backups

Export every n8n workflow as JSON into the repo's `/n8n` folder after each change. If n8n data is lost, import and re-attach credentials.

---

## PART 16. BUILD SCHEDULE (about 20 hours, adjust to your real start)

Deadline is 12:45 PM PKT on 17 October. Count backwards from that, not forwards from when you feel ready.

| Hours | Developer | AI / Automation Engineer | Gate |
|---|---|---|---|
| H0 to H1 | Repo, Dockerfile, hello world live | Deploy n8n, set variables, ask support the questions, LLM and email accounts | **G1:** both URLs work |
| H1 to H5 | Models, seed loader, wizard and results pages | Rule engine with tests, question logic, seed 8 to 10 programs with sources | **G2:** engine tests pass |
| H5 to H9 | Approval screen, timeline page, curator split screen | Ingestion Agent, quote check, rule diff, gold-set test | **G3:** notice to approved Rule Pack works |
| H9 to H12 | Notification review queue (navigator) | **W1 Source Watcher and W2 Fan-out in n8n**, DEMO source page | **G4: rule change reaches affected case (the hero)** |
| H12 to H16 | Sleep (at least 4 hours each) | Sleep | |
| H16 to H18 | Email sending, W3 Approved Send, privacy center | W3 workflow, retries, event logging | **G5:** real email arrives |
| H18 to H19 | Bug fixing, UI polish | W4 Guardian (if G4 and G5 are solid), otherwise stop and test | **FEATURE FREEZE at H19** |
| H19 to H20 | Final deploy, test every link in a private window, record the video on the final build | Run tests, README, credits, export n8n JSON | **G6:** release ready |
| H20 | Screenshots, LinkedIn post (your own words) | Submission PDF | |
| Last 45 min | Open every link as a judge would. Submit. | | Submitted before 12:45 PM |

### Cut list (cut in this order if behind)

1. W4 Deadline Guardian AI agent (keep a simple rule-based reminder).
2. Helper referral (W5).
3. Navigator caseload screen polish.
4. Encrypted vault (use SAMPLE checklists only).
5. Second country.

### Never cut

The curator approval, the source watcher plus fan-out hero flow, the consent screen, the live timeline with Human Decision cards, the real email, the deployment, the delete button.

---

## PART 17. TESTING PLAN

- **Engine:** at least 30 cases: each result type, unknown answers, boundary ages, optional answers skipped.
- **Rule diff:** changed value, removed condition, moved deadline.
- **Quote check:** invented quote flagged red, correct draft passes.
- **Gold-set:** record real accuracy numbers.
- **State guards:** send before approval fails; changed payload cancels approval; double click does not duplicate.
- **Fan-out:** exactly the right cases are flagged. Not-eligible flips go to navigator review, never straight to the user.
- **n8n:** run W1 to W3 end to end 10 times. Include a forced failure that ends in the Manual pack.
- **Privacy:** delete everything leaves nothing, purge job works, logs contain no contents.
- **Deployment:** after every Rebuild and Deploy, open the public URL in a private window and run the hero flow.

---

## PART 18. DEMO PLAN

### Video (2 to 3 minutes; judges see this first, record on the final build)

| Time | Show | Message |
|---|---|---|
| 0:00 to 0:20 | One sourced fact and the problem: rules change, nobody tells you | Why it matters |
| 0:20 to 0:55 | **The rule change:** DEMO source edited (age limit moves). n8n Watcher fires, draft shown with quote check, curator approves | AI drafts, human verifies |
| 0:55 to 1:25 | Fan-out: Amina flips to Eligible and is notified. Mr. Rao's lost eligibility lands in the navigator queue, not his inbox | Good news is automatic, bad news is human |
| 1:25 to 2:00 | Amina approves the exact packet, timeline runs, **real email arrives** in a second window | Real automation with consent |
| 2:00 to 2:25 | Wizard: fewest questions, results with source quotes | Code decides, AI explains |
| 2:25 to 2:45 | Delete everything | Privacy |
| 2:45 to 3:00 | Human Decisions slide, SDGs, global Rule Packs | Impact and scale |

### Live pitch: 5 minutes, hard stop

1. 0:00 to 0:30 Problem and one sourced fact. No long intro.
2. 0:30 to 1:45 **Live rule change** with n8n canvas visible, curator approval, fan-out.
3. 1:45 to 3:00 Applicant approval, timeline, email arrives.
4. 3:00 to 3:45 Wizard and results with source quotes (fewest questions).
5. 3:45 to 4:15 Human Decisions slide and privacy delete.
6. 4:15 to 4:45 Gold-set accuracy, honest limits, roadmap, SDGs.
7. 4:45 to 5:00 Buffer. If you run over, cut item 4 first.

### Slides PDF (top 10, due before 4:00 PM)

Prepare **now**, before the shortlist. Include everything in the handoff doc: team, idea and problem, how implemented, what you are proud of. Suggested 7 slides: problem, idea (three loops), architecture, human decisions, live demo screenshots, honest limits and numbers, roadmap and SDGs.

### Fallbacks

- Recorded perfect run of the hero flow, ready to play.
- REPLAY mode (cached, labeled honestly).
- Pre-signed-in tabs for curator, navigator and applicant.
- Mobile hotspot.
- No changes to the deployment after 12:45 PM. If something breaks, say what happened and show the recording.

---

## PART 19. JUDGE Q&A (BRUTALLY HONEST ANSWERS)

| Likely question | Honest answer |
|---|---|
| Isn't this just a benefit finder? | Finders exist. Ours keeps rules *alive*: watches sources, drafts changes with verified quotes, tells affected people. A human approves every rule and every bad-news message. |
| What stops the AI from inventing a rule? | The AI never decides eligibility. It drafts, code checks that each quote exists, and a human curator approves. Remaining risk: a real sentence read wrongly. That is why the curator exists, and we measured accuracy on a gold set. |
| Why n8n and custom code? | n8n for time- and event-driven orchestration and visible workflows. Code for correctness and privacy. n8n only handles IDs. |
| What is MCP doing here? | The n8n agent calls our guarded tools through MCP. The guards live in the tools, so a bad model output cannot send anything. |
| Is it really automated, or a form with an LLM? | Rule watching, fan-out, reminders and sending run without anyone clicking. Humans sit at consequential decision points. |
| Where is the human? | Curator for rules, navigator for bad news, applicant for consent and identity steps. Each shows as a Human Decision card. |
| Are the programs real? | Some are, verified with source links and dates. Anything unverified is labeled DEMO. We don't claim real coverage. |
| Does the watcher work on real sites? | On one real public notice page we watch, and on a DEMO source we control so the change can be shown on cue. Messy or scanned pages are a known limit. |
| What about privacy for vulnerable users? | Minimum data, sensitive answers optional, no immigration status, encrypted documents, n8n sees IDs only, delete button. All demo data is synthetic. |
| Does it submit to real government portals? | No. We email real packets to a demo inbox and hand off CAPTCHA, codes and payment to the person. Bypassing those would be wrong. |
| What if the AI service is down? | The engine, wizard and results are code and still work. Drafting waits. |
| How would this scale? | Country Rule Packs added by volunteer curators with AI help; the curator step scales the trust, not the code. |
| Who pays? | Free for individuals; grants, development partners and institutions that want to reach eligible people. Not validated yet. |
| What is *not* done? | Real partner pilots, user testing, legal review, languages, real portals. |

---

## PART 20. SUBMISSION CHECKLIST (one PDF per team)

1. **Team details:** team name, both members' full names, emails, registered Discord usernames, one WhatsApp number.
2. **About the project:** name, one-line pitch, problem (2 to 3 lines), where the human comes in (Part 4, in your own words), what we built with: n8n plus custom Python (FastAPI), Groq LLM, MCP tools, email, SQLite. Credit all third-party code.
3. **Required links:** live deployment (keep it running until the closing ceremony), GitHub repo (public or accessible) plus exported n8n JSON, 2 to 3 minute demo video (unlisted YouTube or Google Drive, anyone with the link), original LinkedIn post and the teammate's reshare, X post (optional).
4. **Proof screenshots:** both teammates in the Alternate Futures Discord; Alternate Clouds dashboard showing both services and deployment status. Check for keys before posting.
5. **Judge access:** test username and password per role (demo accounts only). Test every link in a private window.

**Final confirmations:** LinkedIn post written by us (grammar-only tools); deployed on Alternate Clouds; no keys or real passwords anywhere; third-party code credited; no changes after 12:45 PM PKT.

Hashtags: #AgentikaAIHackathon #AIAutomation #AIHackathon #BuildInPublic. The post covers project name and problem, what you built and your part, how you used Alternate Clouds and what you learned, plus a screenshot or demo and link. **Write it yourselves. AI-written posts lead to disqualification.**

---

## PART 21. RISKS

| Risk | Handling |
|---|---|
| Two services doubles deployment risk | Deploy both in hour 1; Core works alone; n8n JSON in repo |
| n8n MCP node not available or flaky | Use HTTP Request nodes to the same endpoints |
| Outbound network blocked (LLM, email, source pages) | Ask support in hour 1; email API fallback; REPLAY mode |
| Scope creep | Hero flow first, freeze at H19, cut list |
| Wrong program data | Official sources only; label DEMO; never invent quotas |
| AI misreads a notice | Quote check, curator, gold-set accuracy |
| Privacy of sensitive users | Minimum data, IDs-only to n8n, synthetic data, delete button |
| Legal advice risk | Information only, accredited humans for legal matters |
| Demo failure | Recording, REPLAY, pre-signed-in tabs |
| Looks generic | Open the demo with the rule change, not the wizard |
| Team fatigue | One sleep block, agreed cut list |

**What would make us lose:** a crash in the hero flow, promising more than we show, unverified data presented as real, a missing submission item, or a late submission.
**What would make us win:** a flawless "rule changed, the right person knew" moment, humans visibly in charge, honest numbers, and a tight 5 minutes.

---

## PART 22. ROADMAP (a slide, not code)

| Phase | Goal |
|---|---|
| Now | Prove living entitlements at Agentika 2.0 |
| 3 months | Pilot with NGO and clinic partners; user testing with each community; legal review per country; accessibility testing with real users |
| 6 to 12 months | More countries via volunteer curators, more languages, WhatsApp and voice access, official data feeds |
| Later | Aggregate "gap reports" showing funders where eligible people are being missed |

---

## PART 23. THINGS I COULD NOT VERIFY (you must)

1. That your team is registered and confirmed.
2. Alternate Clouds credits, memory, disk permanence, service-to-service and outbound network access.
3. Whether the n8n template has the MCP Client Tool node, and the exact n8n setting names for not saving execution data.
4. Whether SMTP works from the platform, or you need an email API.
5. The current Groq model name and limits.
6. Every program and rule you use: copy from official sources with links and dates.
7. What the FastN MCP offers and whether it deploys there. This plan does not depend on it.
8. Two sourced non-take-up facts.
9. Whether organizers apply the English rule to product text. Keep everything English to be safe.

---

## APPENDIX A. BUILD ORDER IN ONE LIST

1. Deploy n8n and hello-world Core. 2. Models and seed. 3. Engine with tests. 4. Wizard and results. 5. Ingestion with quote check, diff, gold set. 6. Curator screen. 7. W1 Watcher and W2 Fan-out (**hero flow**). 8. Navigator review queue. 9. Approval screen and W3 Approved Send with a real email. 10. Timeline with Human Decision cards. 11. Privacy center. 12. If time: Guardian, helper referral, vault. 13. Freeze, record, submit.

## APPENDIX B. RULES FOR THE CURSOR AGENT (AGENTS.md)

```
Project: RightPath v2. Read docs/BUILDPLAN.md before any task.
1. One task per session. Plan first, wait for approval, then implement.
2. Run the app and the tests before saying a task is finished.
3. Never commit secrets. Use environment variables. Keep .env out of git.
4. Synthetic data only. No real names, ID numbers or documents.
5. Eligibility is decided only by app/engine. The LLM never decides eligibility.
6. Sending tools must check state APPROVED and the approval hash in code.
7. n8n receives IDs only, never profiles or documents.
8. Every workflow step writes an event; human decisions are flagged.
9. Never log document contents, file names or ID numbers.
10. All interface text is English and simple.
11. Keep diffs small. Commit after each task.
12. If something is unclear, stop and ask.
```

## APPENDIX C. HONEST FINAL VIEW

RightPath v2 is a real, international problem with a human-centered solution and a clear automation story. It is still not a unique category, and 20 hours is tight. The version that can win is the narrow one: a flawless hero flow where a rule changes, a human verifies it, and the right person is told, plus honest limits and rehearsed delivery. Build the hero flow first, protect it, and cut everything else without guilt.
