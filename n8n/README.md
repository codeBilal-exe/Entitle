# n8n workflows for ENTITLE

Import these JSON files into your Alternate Clouds n8n service after Core is reachable.

| File | Purpose |
|---|---|
| `w1_source_watcher.json` | Cron + "check now" webhook → Core `/api/internal/check-sources` |
| `w2_impact_fanout.json` | Webhook → Core `/api/internal/approve` (fan-out) |
| `w3_approved_send.json` | Webhook → Core `/api/internal/send` (retries on fail) |

## Environment in n8n

Set on the n8n service (and reference in nodes):

- `ENTITLE_BASE_URL` — public Core URL, e.g. `https://your-core-app.alternatefutures.ai`
- `ENTITLE_SHARED_SECRET` — same value as Core `N8N_SHARED_SECRET`
- Platform required: `N8N_ENCRYPTION_KEY`, `WEBHOOK_URL`

## Auth

Every Core call sends header:

```
x-entitle-secret: <N8N_SHARED_SECRET>
```

n8n must pass **IDs only** (job_id, application_id). Never profiles or documents.

## Local testing without n8n

Core already runs a background watcher (`ENABLE_SCHEDULER=true`) and exposes the same hooks:

```bash
curl -X POST http://127.0.0.1:8000/api/internal/check-sources?auto_ingest=true ^
  -H "x-entitle-secret: dev-shared-secret"
```

The UI **Check sources now** / **REPLAY tighten** buttons use the same Pulse path.
