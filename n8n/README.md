# n8n workflows for Entitle

Entitle runs on its own: a built-in watcher re-reads every official page on a timer. n8n is optional and adds outside triggers. It can start work, but it can never approve anything. Approval only happens on the Verification Desk, by a person.

| File | What it does |
|---|---|
| `w1_source_watcher.json` | Every 15 minutes, or when the `entitle-check-now` webhook is called, asks Entitle to re-read every watched page. A real rule change becomes a draft in the reviewer queue. |
| `w2_programme_intake.json` | The `entitle-intake` webhook takes `{"url": "https://..."}`, runs the full Entitle pipeline on that page, then returns what is waiting for a reviewer. |

## Setup

1. Import both JSON files into your n8n service.
2. Set these variables on the n8n service:
   - `ENTITLE_BASE_URL`: the public Entitle address, for example `https://entitle-app.alternatefutures.ai`
   - `ENTITLE_SHARED_SECRET`: the same value as `N8N_SHARED_SECRET` on Entitle
   - Required by n8n on Alternate Clouds: `N8N_ENCRYPTION_KEY` and `WEBHOOK_URL`
3. Activate the workflows.

## The API n8n calls

Every call sends the header `x-entitle-secret: <N8N_SHARED_SECRET>`. Only IDs and public URLs cross this API, never personal data.

| Method and path | Purpose |
|---|---|
| `POST /api/internal/check-sources` | Re-read all watched pages |
| `POST /api/internal/ingest` | Run the pipeline on `{"url": ...}` or on `{"program_id": ..., "notice_text": ...}` |
| `GET /api/internal/queue` | Drafts and held bad news waiting for a person |
