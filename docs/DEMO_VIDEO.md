# Walkthrough

Use the premade accounts in [DEMO_ACCOUNTS.md](DEMO_ACCOUNTS.md). Follow the short script in [DEMO_FLOW.md](DEMO_FLOW.md).

## Before you start

1. Start the app (`uvicorn app.main:app --reload --port 8000`). n8n can be off.
2. Confirm `.env` has the demo passwords (copy from `.env.example` if needed).
3. Restart once so startup recreates the premade citizen and staff/admin accounts.

## What to show

| Time | Screen | What the viewer should see |
|---|---|---|
| 0:00–0:20 | Sign in | Empty form. Human stops. Sign in as the premade citizen. |
| 0:20–0:50 | Programmes + profile | Filled profile already matching. Official programme links. |
| 0:50–1:20 | Staff desk | Sources. Check sources now. |
| 1:20–1:50 | Draft | Quote check. A person approves or rejects. |
| 1:50–2:15 | Reviews | Name and eligibility change only. Release or hold. |
| 2:15–2:40 | Citizen alerts | Unread count. Next step. Packet approval if you prepared one. |

If a source cannot be read, say so. Do not invent a quota or age band that was not on the page.

## After

Admin **Activity** should show human decisions. Keep **Sending** off unless mail is configured.
