# ENTITLE

ENTITLE watches real public programme notices. When the text changes, code re-checks stored profiles. A person approves a rule change. A person releases bad news. The applicant approves the exact packet. The language model may draft and explain. It never decides eligibility and it never sends on its own.

This note replaces earlier plans that used premade citizens, a view switch, and a controllable demo notice.

## Roles

Stored on the account.

- **Citizen** signs up, fills in their own profile, sees matches, prepares an application, approves the packet, and reads their own alerts.
- **Staff** (two accounts, passwords in the environment) watch sources, review a draft against the quote check, and release or hold a loss of support. They see a name and the eligibility change, not the private profile.
- **Admin** (one account) can do the staff work and also manage sources, turn sending on or off, and read the activity log. Admin cannot open a citizen's private profile.

The server enforces this on every page and action.

## Data

Local SQLite at `data/entitle.db`. Passwords are hashed with bcrypt. A signed-in citizen can read and update only their own profile, applications, and alerts. No browser localStorage for profiles. No shared in-memory profile store.

## Sources

Official pages only. Pakistan pages in the catalogue include HEC scholarships, Benazir Income Support and Kafaalat (8171), PEEF, NAVTTC, Sehat Sahulat, the Ministry of Human Rights, the Prime Minister's Youth Programme, Pakistan Bait-ul-Mal, Punjab literacy, and the Sindh school education and literacy department.

Rules and quota text appear only as a verbatim quote from a fetched page. If the page cannot be read, the source is unreachable. Unapproved pages do not show a guessed eligibility result.

## Automation

The in-process timer re-reads sources. Check sources now uses the same path. A text change creates a draft, runs the quote check, and waits for staff. After approval, profiles are re-checked. A new qualification becomes an alert. A possible loss is held for staff. Deadline reminders still run. n8n is optional. The app works without it.

## Kept on purpose

- Rule engine: deterministic eligibility.
- Quote check: every `source_quote` must appear in the notice.
- Approval gate: the packet hash must match before send.

## Citizen path

Sign up → fill in your profile → see what matches → prepare an application → approve the packet → alerts.

## Staff path

Sign in → sources and drafts → approve only if the quotes match → release or hold bad news.

## Admin path

Staff work, plus sources and the sending switch, and the activity log.
