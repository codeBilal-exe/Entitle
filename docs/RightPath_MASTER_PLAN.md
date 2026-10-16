# RightPath MASTER PLAN — Agentika 2.0 (NaSCon 2026)

**Status:** Authoritative build plan. Supersedes `RightPath_v2_Winning_Plan.md` for what you *build*. Keep v2 as reference for Q&A wording and long appendix detail.

**Clock:** ~17 hours from Fri 16 Oct ~19:20 PKT → **submit by 12:45 PM Sat 17 Oct**. Top-10 slides before 4:00 PM. Pitch: **5 minutes hard stop** (rehearse 4:30).

**Theme:** Human + AI: Better Together.  
**Stack allowed:** n8n, custom code, or both + AI models + MCP.  
**Host:** Alternate Clouds only. English only. LinkedIn written by humans.

---

## 0. One-sentence win condition

> A rule changes on a watched notice page → AI drafts with quote-checked conditions → a human curator approves → the right people are notified (good news auto, bad news via navigator) → the applicant consents and a **real email** leaves — all visible on a live timeline and an n8n canvas.

If that spine is not flawless live, you do not win. Everything else is decoration.

---

## 1. Why this beats the old v2 plan (honest delta)

| Gap in v2 | Master fix |
|---|---|
| Still ~15 “must” items for ~20h; you now have **~17h** | **9 musts**. Hard freeze. Sleep is optional, cut list is law. |
| Two services = demo fragility | **Core is the brain and can run the hero alone.** n8n is the *visible nervous system*. Same webhooks; Core has a fallback cron if n8n is down. |
| MCP + Deadline Guardian eat night | MCP is **post-hero polish**. Hero uses n8n HTTP → Core. |
| 8–10 programs / 2 countries / gold-set 5–8 | **6 programs, 1 primary country (+1 DEMO pack)**, gold-set **4** notices. |
| Wizard can steal the opening | Demo **opens on the Pulse** (rule change), wizard is minute 3. |
| Optimistic 65–84 with feature sprawl | Target **72–80** with a perfect spine. No fantasy 90. |
| Plan-heavy, seam-light | Five **deep test seams** (TDD). No shallow “agents” folder soup. |
| Generic SaaS UI risk | One **civic / notice-board** visual system (frontend-design). |
| Video / QA afterthought | **agent-browser** private-window judge pass; **HyperFrames** (or simple capture) only after G4+G5 green. |

**Keep from v2 (do not reinvent):** rules-as-code; quote check; curator; consent + approval hash; privacy delete; synthetic data; no CAPTCHA bypass; no fake “we submitted to government”; Human Decision cards; submission checklist; judge Q&A honesty.

---

## 2. Rubric map (build for points, not vibes)

| Criterion | Pts | How we earn them | Kill if failing |
|---|---|---|---|
| Technical execution & reliability | 25 | Deployed early, retries, guards, REPLAY mode, private-window tested | Broken live demo |
| Usefulness & real-world impact | 20 | Non-take-up + *living* rules; 2 sourced facts; navigator for bad news | Fake stats / wrong program rules |
| Theme alignment | 15 | ≥4 Human Decision cards on timeline | AI decides eligibility or auto-sends |
| Creativity & uniqueness | 15 | Living entitlements + quote-verified drafting | Opens as “benefit calculator” |
| Automation depth & integration | 15 | Cron/webhook n8n + Core + LLM + email; MCP optional | Click-only form + LLM |
| UX & presentation | 10 | Clean civic UI, 2–3 min video, 4:30 pitch | Clutter / overrun |

**Honest band if spine works:** ~72–80. Top-10 is realistic. Win needs flawless demo + crisp pitch + weaker rivals.

---

## 3. Product definition (narrow)

| | |
|---|---|
| **Name** | RightPath |
| **Pitch** | Rules change. RightPath tells the right people — with humans approving every consequential step. |
| **Category** | Human-supervised entitlement automation |
| **Not** | A benefit finder, a chatbot form, a fake government portal scraper |

### Three loops (demo order)

1. **Pulse (automation hero):** Source Watcher → Ingestion + QuoteGate → Curator approve → Impact Fan-out → Navigator for bad news.
2. **Consent:** Applicant sees exact packet → approve (hash) → Approved Send → real email.
3. **Explain (support):** Short wizard → Eligible / Likely / Not eligible with source quotes → privacy delete.

### Roles (demo switcher)

- **Applicant** — consent, packet, delete.
- **Navigator** — review “may no longer qualify”.
- **Curator** — approve AI-drafted rule versions.

---

## 4. Architecture (deep modules, few seams)

```
  Official / DEMO notice URL
           |
           v
  +---------------------+     HTTP (IDs + shared secret)     +---------------------------+
  | n8n (visible)       | <--------------------------------> | RightPath Core (FastAPI)  |
  | W1 Watcher (cron)   |                                    | RuleEngine (code)         |
  | W2 Fan-out (hook)   |                                    | QuoteGate (code)          |
  | W3 Approved Send    |                                    | CaseImpact (code)         |
  | (optional W4 later) |                                    | ApprovalGate (code)       |
  +---------------------+                                    | IngestAgent (LLM draft)   |
           |                                                 | Explainer (LLM text)      |
           |  fallback: Core cron mirrors W1/W2              | Vault/SQLite, Email, UI   |
           |  if n8n unreachable                             | Timeline + Human cards    |
           +------------------------------------------------>+---------------------------+
                                      |
                               Groq + SMTP/email API
```

### Design rules

1. **Eligibility is only `RuleEngine`.** LLM never decides Eligible / Not eligible.
2. **n8n never sees PII.** Only case IDs, program IDs, status codes.
3. **Sending only through `ApprovalGate`:** state `APPROVED` + payload hash match.
4. **Core works without n8n.** User loop + optional Core cron for Pulse.
5. **MCP is optional polish:** same HTTP tools, same guards. If n8n MCP node flakes → HTTP Request nodes. Do not burn the night.

### Deep modules (build these, not “5 agents”)

| Module | Job | Depth |
|---|---|---|
| `RuleEngine` | Evaluate conditions → Eligible / Likely / Not eligible + reasons | Deterministic, fully tested |
| `QuoteGate` | Every `source_quote` must be verbatim in notice text | Deterministic |
| `CaseImpact` | Diff rule versions → which cases flip and how | Deterministic |
| `ApprovalGate` | Hash + state machine for send / referral | Deterministic |
| `IngestAgent` | LLM drafts Rule Pack JSON only; then QuoteGate | Thin AI wrapper |
| `Timeline` | Append-only events; `human_decision` flag | Simple + visible |

---

## 5. Scope: Must / Should / Never

### MUST (9) — freeze when G4+G5 green

1. Deploy **Core + n8n** on Alternate Clouds (hour 0).
2. Seed **6 programs** (label unverified **DEMO sample**). Role switcher + demo users.
3. `RuleEngine` + adaptive **short** wizard + results with quotes.
4. `IngestAgent` + `QuoteGate` + curator split screen + **gold-set 4** with honest score.
5. **W1 Source Watcher** (cron + “Check now” webhook) + controllable **DEMO source** page.
6. Curator approve → **W2 Fan-out** + navigator queue for Not-eligible flips.
7. Consent screen + hash → **W3 Approved Send** → **real email** in demo inbox.
8. Live **timeline** with Human Decision cards.
9. Privacy: “Delete everything” + no secrets in repo/screenshots.

### SHOULD (only after G5)

- Deterministic deadline reminders (simple cron) — **not** an AI agent night.
- Document checklist with SAMPLE ONLY files.
- MCP tools (3–6) for the same HTTP endpoints.
- Manual ZIP pack on send failure.
- Second country as 1–2 DEMO programs only.

### NEVER (say on roadmap slide)

CAPTCHA solve, real portal submit, real IDs/immigration, OCR, Playwright mock portal, WhatsApp/voice, multi-language UI, helper marketplace, payments.

---

## 6. Test seams (TDD — agree once, then red→green)

Write tests **only** at these seams. Vertical slices: one failing test → minimal code → next.

| Seam | Spec examples |
|---|---|
| `RuleEngine.evaluate` | All true → Eligible; one false → Not eligible + which condition; unknowns → Likely |
| `QuoteGate.check` | Exact quote passes; invented quote fails; whitespace mismatch fails |
| `CaseImpact.diff` | Age band change flips Amina to Eligible; Mr Rao to Not eligible |
| `ApprovalGate.send` | Reject if not APPROVED; reject if hash mismatch; idempotent double-click |
| `FanOut.route` | Bad news → navigator queue; good news → pending_notify only if consent |

**Minimum bar before demo:** ≥25 engine cases, quote invent/pass, one full Pulse integration (DEMO source edit → curator → two cases routed correctly), one real email in staging.

**Judge simulation:** `agent-browser` (or private window) against public URLs — no cookies from your session.

---

## 7. Visual system (frontend-design)

**Subject:** Official notices, rights, trust — not a startup dashboard.

| Token | Choice |
|---|---|
| Base | Warm off-white paper `#F7F4EE` |
| Ink | Near-black `#1A1A1A` |
| Accent | Deep teal `#0F5C5C` (official stamp, not purple SaaS) |
| Alert | Muted brick `#8B3A3A` for “needs human” |
| Type | One strong serif for product name / notices (e.g. Source Serif or Libre Baskerville); one clean sans for UI (e.g. IBM Plex Sans) |
| Layout | Single column for wizard; curator = **split notice | draft**; timeline = vertical spine, not card grid |
| Motion | One: timeline event appear. No hover-card circus |

Avoid: purple gradients, identical rounded cards everywhere, ALL-CAPS eyebrows, fake stats strips in the hero.

**Demo UI surfaces only:** Pulse board (curator), Navigator queue, Applicant packet + timeline, Privacy.

---

## 8. Clock from NOW (17 Oct 12:45 is hard)

Adjust start if you begin later; **never** slip Feature Freeze or Submit.

| Block | Clock (PKT) | Focus | Gate |
|---|---|---|---|
| **B0 Deploy** | Now → +60m | Dockerfile Core; n8n template; vars (`PORT`, `N8N_ENCRYPTION_KEY`, `WEBHOOK_URL`); Discord name; ask support about outbound LLM/SMTP/disk | **G1** both public URLs open |
| **B1 Brain** | +1h → +4h | Models, seed 6 programs, `RuleEngine` + tests, short wizard + results | **G2** engine tests green |
| **B2 Ingest** | +4h → +7h | IngestAgent, QuoteGate, curator UI, gold-set 4, DEMO source page | **G3** notice → draft → approve |
| **B3 Pulse** | +7h → +10h | W1 + W2 in n8n; CaseImpact; navigator queue; timeline | **G4** rule change reaches correct cases (**HERO**) |
| **B4 Sleep** | +10h → +14h | **Mandatory 3–4h sleep** if G4 green; if G4 red, one more hour then sleep anyway | — |
| **B5 Send** | +14h → +16h | ApprovalGate, W3, real email, privacy delete, polish | **G5** email arrives |
| **B6 Freeze** | ~10:30–11:30 AM | Feature freeze. Rebuild+Deploy. agent-browser private checks. Export n8n JSON. Video. README credits | **G6** release |
| **B7 Submit** | 11:30–12:45 | PDF, LinkedIn (human-written), every link, submit | **Submitted** |

### Cut order if behind (cut without guilt)

1. MCP / AI Deadline Guardian  
2. Encrypted vault polish (SAMPLE checklist text is enough)  
3. Second country  
4. Referral helpers  
5. Wizard “adaptive” cleverness → fixed short form  

### Never cut

G1 deploy, QuoteGate, curator, W1+W2 hero, consent hash, real email, timeline Human cards, delete button, REPLAY mode, submission PDF.

---

## 9. Deployment (troubleshooting guide baked in)

**Golden rule:** Variables → Rebuild → Deploy. Push alone does nothing.

| Symptom | Fix |
|---|---|
| 502 | `PORT` matches Dockerfile/uvicorn (8000) |
| Code pushed, site old | Rebuild then Deploy |
| Startup KeyError | Missing env; add, Rebuild, Deploy |
| `no active leases` | `npm i -g @alternatefutures/acc` then close + retry |
| n8n creds/webhooks dead | Fixed `N8N_ENCRYPTION_KEY` + exact `WEBHOOK_URL` |

Core env (dashboard only): `SECRET_KEY`, `VAULT_KEY`, `GROQ_API_KEY`, `LLM_MODEL`, mail vars, `DEMO_RECIPIENT`, `N8N_BASE_URL`, `N8N_SHARED_SECRET`, `BASE_URL`, `ADMIN_PASSWORD`, `PORT=8000`.

On boot: create tables, seed if empty, start Core fallback cron. Export `/n8n/*.json` after every workflow change.

---

## 10. Demo spine (video 2–3 min + live 5 min)

### Video order (record on final build)

1. Problem + **one sourced fact** (15s)  
2. Edit DEMO notice (age band) → Watcher → draft + QuoteGate → curator approve (40s)  
3. Fan-out: Amina Eligible notified; Mr Rao → navigator not inbox (30s)  
4. Amina consents → timeline → **email arrives** second window (35s)  
5. 20s wizard quotes + Delete everything  
6. Human Decisions + SDGs + honest limits (15s)

### Live pitch 4:30 + buffer

Open on Pulse with n8n canvas visible. Cut wizard first if over time.

### Fallbacks

Labeled **REPLAY**; pre-signed tabs; recorded hero; hotspot. After 12:45: **no code/deploy changes**.

---

## 11. Submission PDF (fill as you go — one PDF)

1. Team name, both names/emails/Discord, one WhatsApp  
2. Pitch, 2–3 line problem, where humans decide, stack (n8n + FastAPI + Groq + MCP-or-HTTP + email)  
3. Links: live deploy, GitHub + n8n JSON, 2–3 min video, LinkedIn + reshare  
4. Screenshots: both in Discord; Alternate Clouds services live  
5. Demo logins per role  
6. Confirmations: human LinkedIn; Alternate Clouds; no keys; credits; freeze after deadline  

Hashtags: `#AgentikaAIHackathon #AIAutomation #AIHackathon #BuildInPublic`

**Before submit:** two real sourced non-take-up facts (OECD / World Bank / ILO / national stats). Do not invent numbers.

---

## 12. How the 6 skills are used on this build

| Skill | Use |
|---|---|
| `improve-codebase-architecture` | Keep modules deep (`RuleEngine`, `QuoteGate`, …). Deletion test on any new “helper” file. |
| `tdd` | Only the five seams above; red→green vertical slices. |
| `frontend-design` | Civic notice-board UI tokens; no generic SaaS kit. |
| `agent-browser` | Final judge simulation on public URLs (private window path). |
| `hyperframes-cli` | Optional polished demo video **after** G5; skip if time-poor — clean screen capture wins over broken fancy video. |
| `find-skills` | Only if a concrete gap appears; do not skill-shop during build hours. |

---

## 13. Risks that actually kill you

| Risk | Counter |
|---|---|
| Scope creep after G4 | Freeze. Cut list. |
| n8n down in pitch | Core fallback cron + REPLAY + recording |
| LLM/SMTP blocked | Hour-0 support ask; cached draft; email API |
| Wrong “real” program data | Official links + dates; else **DEMO sample** |
| Looks like benefit finder | Open with Pulse, not wizard |
| Overrun pitch | 4:30 rehearsal; cut wizard |
| AI-written LinkedIn | Humans write; grammar tools only |

---

## 14. Agent rules (put in `AGENTS.md` when repo exists)

```
Project: RightPath MASTER. Read RightPath_MASTER_PLAN.md first.
1. One task per session. Plan → approve → implement.
2. Run app + seam tests before claiming done.
3. No secrets in git. Synthetic data only.
4. RuleEngine decides eligibility. LLM drafts/explains only.
5. ApprovalGate checks APPROVED + hash before any send.
6. n8n gets IDs only.
7. Every step logs timeline; human steps flagged.
8. English UI. Small diffs. Stop and ask if unclear.
```

---

## 15. Immediate next actions (do in order)

1. Confirm team Discord names + Alternate Clouds credits.  
2. Create GitHub repo (not this empty GitHappens docs folder alone).  
3. Execute **B0 Deploy** until G1.  
4. Seed programs + RuleEngine tests until G2.  
5. Protect G4 as sacred.  

---

## Appendix — Verdict

RightPath remains a credible **top-10 / potential win** *if* the Pulse is live, humans are visible, automation is event-driven, and you refuse scope. v2 was the right *idea*; this master plan is the right *war plan* for ~17 hours: fewer features, deeper modules, dual-path reliability, demo-first storytelling, and skills used as discipline — not as distractions.

**What would make you lose:** crash on Pulse, fake data, missing submission item, late submit, AI LinkedIn.  
**What would make you win:** flawless “rule changed → right person knew”, humans in charge, honest numbers, 4:30 pitch.
